"""Event translation.

Satori delivers one flat event object per protocol event: a ``type`` plus whatever
resources the event carries, all promoted to the top level. This module maps those
onto the V2 event model, following the resource list of the specification
(``protocol/events.md`` and the per-resource pages).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from hyperot.v2.common import MemberRole, ReactionKind, ReactionValue, SceneType, UserSnapshot
from hyperot.v2.events import (
    BotOfflineEvent,
    BotOnlineEvent,
    Event,
    FriendRequestedEvent,
    GroupInvitationReceivedEvent,
    GroupJoinRequestedEvent,
    GroupNameChangedEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MemberRoleChangedEvent,
    MessageReactionChangedEvent,
    MessageRecalledEvent,
    MessageReceivedEvent,
    SceneEvent,
)
from hyperot.v2.hyperogger import Logger

from .ids import (
    encode_friend_request_id,
    encode_guild_member_request_id,
    encode_guild_request_id,
    encode_message_id,
)
from .segments import DIRECT_CHANNEL, SatoriSegmentCodec

logger = Logger.fetch("hyperot.v2.events")

ONLINE = 1


class SatoriMessageReceivedEvent(MessageReceivedEvent):
    platform: str
    self_id: str
    channel_id: str
    guild_id: str | None = None


class SatoriMessageUpdatedEvent(SatoriMessageReceivedEvent):
    """A message the protocol end reports as edited."""


class SatoriLoginChangedEvent(Event):
    platform: str
    self_id: str
    status: int
    adapter: str = ""
    features: list[str] = Field(default_factory=list)


class SatoriBotOnlineEvent(BotOnlineEvent):
    platform: str
    self_id: str
    status: int = ONLINE


class SatoriBotOfflineEvent(BotOfflineEvent):
    platform: str
    self_id: str
    status: int
    adapter: str = ""
    features: list[str] = Field(default_factory=list)


class SatoriGuildChangedEvent(SceneEvent):
    change: str
    guild_name: str = ""


class SatoriChannelChangedEvent(SceneEvent):
    change: str
    channel_type: int = 0
    channel_name: str = ""
    guild_id: str | None = None


class SatoriGuildRoleChangedEvent(SceneEvent):
    change: str
    role_id: str
    role_name: str = ""


class SatoriGuildEmojiChangedEvent(SceneEvent):
    change: str
    emoji_id: str
    emoji_name: str = ""


class SatoriButtonInteractionEvent(SceneEvent):
    platform: str
    self_id: str
    button_id: str


class SatoriCommandInteractionEvent(SceneEvent):
    platform: str
    self_id: str
    name: str = ""
    arguments: list[Any] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class SatoriInternalEvent(Event):
    platform: str
    self_id: str
    event_type: str
    data: Any = None


def _id(value: object) -> str:
    return str(value) if value is not None else ""


def _timestamp(value: object) -> datetime:
    if isinstance(value, int | float):
        # Satori timestamps are milliseconds since the epoch.
        return datetime.fromtimestamp(value / 1000, UTC)
    return datetime.now(UTC)


def _login_of(data: dict[str, Any]) -> tuple[str, str]:
    login = data.get("login") or {}
    user = login.get("user") or {}
    return _id(login.get("platform")), _id(user.get("id"))


def _scene(channel: dict[str, Any] | None, guild: dict[str, Any] | None, user_id: str) -> tuple[SceneType, str]:
    """Pick the scene an event belongs to.

    A private channel is a user scene addressed by the peer id. A text channel inside a
    guild is a guild scene addressed by the channel id, which keeps every channel of a
    multi-channel guild reachable; guild-wide events address the guild itself.
    """
    if channel is None:
        return SceneType.USER, user_id
    channel_id = _id(channel.get("id"))
    if _is_direct(channel) or guild is None:
        return SceneType.USER, user_id or channel_id
    return SceneType.GUILD, channel_id


def _is_direct(channel: dict[str, Any]) -> bool:
    try:
        return int(channel.get("type", 0)) == DIRECT_CHANNEL
    except (TypeError, ValueError):
        return False


def _guild_scene(guild: dict[str, Any] | None, fallback: str) -> tuple[SceneType, str]:
    if guild is None:
        return SceneType.USER, fallback
    return SceneType.GROUP, _id(guild.get("id"))


def _user_snapshot(data: dict[str, Any], user_id: str) -> UserSnapshot:
    user = data.get("user") or {}
    member = data.get("member") or {}
    nick = user.get("nick") or user.get("name")
    card = member.get("nick") or member.get("name")
    return UserSnapshot(
        user_id=_id(user.get("id")) or user_id,
        nick_name=nick,
        display_name=card or nick,
        role=_role_from_member(member),
    )


def _role_from_member(member: dict[str, Any]) -> MemberRole | None:
    roles = member.get("roles")
    if not isinstance(roles, list):
        return None
    names = {str((role or {}).get("name", "")).lower() for role in roles if isinstance(role, dict)}
    if any("owner" in name or "群主" in name for name in names):
        return MemberRole.OWNER
    if any("admin" in name or "管理" in name for name in names):
        return MemberRole.ADMIN
    return MemberRole.MEMBER if names else None


def _is_mentioned(message: Any, self_id: str) -> bool:
    from hyperot.v2.messages import Mention, MentionAll

    for segment in message:
        if isinstance(segment, MentionAll):
            return True
        if isinstance(segment, Mention) and str(segment.user_id) == str(self_id):
            return True
    return False


def _message_of(data: dict[str, Any], codec: SatoriSegmentCodec) -> Any:
    message = data.get("message") or {}
    # The channel is what makes the ids inside the content addressable.
    return codec.decode_message(message.get("content"), channel_id=_channel_id_of(data))


def _channel_id_of(data: dict[str, Any]) -> str:
    channel = data.get("channel") or {}
    return _id(channel.get("id"))


def _packed_message_id(data: dict[str, Any]) -> str:
    message = data.get("message") or {}
    return encode_message_id(_channel_id_of(data), message.get("id"))


def translate_event(data: dict[str, Any], codec: SatoriSegmentCodec) -> Event | None:
    event_type = str(data.get("type", ""))
    timestamp = _timestamp(data.get("timestamp"))
    platform, self_id = _login_of(data)

    if event_type == "message-created":
        return _message_event(data, codec, timestamp, platform, self_id, SatoriMessageReceivedEvent)
    if event_type == "message-updated":
        return _message_event(data, codec, timestamp, platform, self_id, SatoriMessageUpdatedEvent)
    if event_type == "message-deleted":
        scene_type, scene_id = _scene(data.get("channel"), data.get("guild"), _operator_id(data))
        operator = data.get("operator") or {}
        return MessageRecalledEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_id(operator.get("id")) or _event_user_id(data),
            message_id=_packed_message_id(data),
            operator_id=_id(operator.get("id")) or None,
        )
    if event_type in ("reaction-added", "reaction-removed"):
        emoji = data.get("emoji") or {}
        scene_type, scene_id = _scene(data.get("channel"), data.get("guild"), _event_user_id(data))
        return MessageReactionChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            message_id=_packed_message_id(data),
            reaction=ReactionValue(kind=ReactionKind.EMOJI, value=str(emoji.get("name") or emoji.get("id") or "")),
            added=event_type == "reaction-added",
        )
    if event_type == "guild-member-added":
        scene_type, scene_id = _guild_scene(data.get("guild"), _event_user_id(data))
        operator = data.get("operator") or {}
        return MemberJoinedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            member_id=_event_user_id(data),
            operator_id=_id(operator.get("id")) or None,
        )
    if event_type == "guild-member-removed":
        scene_type, scene_id = _guild_scene(data.get("guild"), _event_user_id(data))
        operator = data.get("operator") or {}
        operator_id = _id(operator.get("id")) or None
        return MemberLeftEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            member_id=_event_user_id(data),
            operator_id=operator_id,
            kicked=operator_id is not None,
        )
    if event_type == "guild-member-updated":
        scene_type, scene_id = _guild_scene(data.get("guild"), _event_user_id(data))
        operator = data.get("operator") or {}
        member = data.get("member") or {}
        return MemberRoleChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            member_id=_event_user_id(data),
            operator_id=_id(operator.get("id")) or None,
            # The protocol reports the roles a member has now, not the change itself.
            old_role=None,
            new_role=_role_from_member(member) or MemberRole.MEMBER,
        )
    if event_type == "guild-member-request":
        guild = data.get("guild") or {}
        scene_type, scene_id = _guild_scene(guild, _event_user_id(data))
        return GroupJoinRequestedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            request_id=encode_guild_member_request_id(guild.get("id"), (data.get("message") or {}).get("id")),
            comment=_content_of(data),
        )
    if event_type == "guild-request":
        guild = data.get("guild") or {}
        scene_type, scene_id = _guild_scene(guild, _event_user_id(data))
        return GroupInvitationReceivedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            request_id=encode_guild_request_id(guild.get("id"), (data.get("message") or {}).get("id")),
            inviter_id=_event_user_id(data),
        )
    if event_type == "friend-request":
        return FriendRequestedEvent(
            timestamp=timestamp,
            request_id=encode_friend_request_id((data.get("message") or {}).get("id")),
            user_id=_event_user_id(data),
            comment=_content_of(data),
        )
    if event_type == "guild-updated":
        guild = data.get("guild") or {}
        scene_type, scene_id = _guild_scene(guild, _event_user_id(data))
        operator = data.get("operator") or {}
        return GroupNameChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            # The protocol sends the new name only.
            old_name=None,
            new_name=str(guild.get("name") or ""),
            operator_id=_id(operator.get("id")) or None,
        )
    if event_type in ("guild-added", "guild-removed"):
        guild = data.get("guild") or {}
        scene_type, scene_id = _guild_scene(guild, _event_user_id(data))
        return SatoriGuildChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            change="added" if event_type == "guild-added" else "removed",
            guild_name=str(guild.get("name") or ""),
        )
    if event_type in ("channel-added", "channel-updated", "channel-removed"):
        channel = data.get("channel") or {}
        scene_type, scene_id = _scene(channel, data.get("guild"), _event_user_id(data))
        try:
            channel_type = int(channel.get("type", 0))
        except (TypeError, ValueError):
            channel_type = 0
        return SatoriChannelChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            change=event_type.removeprefix("channel-"),
            channel_type=channel_type,
            channel_name=str(channel.get("name") or ""),
            guild_id=_id((data.get("guild") or {}).get("id")) or None,
        )
    if event_type in ("guild-role-created", "guild-role-updated", "guild-role-deleted"):
        role = data.get("role") or {}
        scene_type, scene_id = _guild_scene(data.get("guild"), _event_user_id(data))
        return SatoriGuildRoleChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            change=event_type.removeprefix("guild-role-"),
            role_id=_id(role.get("id")),
            role_name=str(role.get("name") or ""),
        )
    if event_type in ("guild-emoji-added", "guild-emoji-updated", "guild-emoji-deleted"):
        emoji = data.get("emoji") or {}
        scene_type, scene_id = _guild_scene(data.get("guild"), _event_user_id(data))
        return SatoriGuildEmojiChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            change=event_type.removeprefix("guild-emoji-"),
            emoji_id=_id(emoji.get("id")),
            emoji_name=str(emoji.get("name") or ""),
        )
    if event_type == "login-added":
        return _login_event(data, timestamp, online=True)
    if event_type == "login-removed":
        return _login_event(data, timestamp, online=False)
    if event_type == "login-updated":
        return _login_changed_event(data, timestamp)
    if event_type == "interaction/button":
        button = data.get("button") or {}
        scene_type, scene_id = _scene(data.get("channel"), data.get("guild"), _event_user_id(data))
        return SatoriButtonInteractionEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            platform=platform,
            self_id=self_id,
            button_id=_id(button.get("id")),
        )
    if event_type == "interaction/command":
        argv = data.get("argv") or {}
        scene_type, scene_id = _scene(data.get("channel"), data.get("guild"), _event_user_id(data))
        return SatoriCommandInteractionEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=_event_user_id(data),
            platform=platform,
            self_id=self_id,
            name=str(argv.get("name") or ""),
            arguments=list(argv.get("arguments") or []),
            options=dict(argv.get("options") or {}),
        )
    if event_type == "internal":
        return SatoriInternalEvent(
            timestamp=timestamp,
            platform=platform,
            self_id=self_id,
            event_type=str(data.get("_type") or ""),
            data=data.get("_data"),
        )

    # The specification asks application ends to ignore event types they do not know.
    logger.warning(f"忽略未知的 Satori 事件类型：{event_type}")
    return None


def _message_event(
    data: dict[str, Any],
    codec: SatoriSegmentCodec,
    timestamp: datetime,
    platform: str,
    self_id: str,
    event_type: type[SatoriMessageReceivedEvent],
) -> SatoriMessageReceivedEvent:
    channel = data.get("channel") or {}
    guild = data.get("guild")
    user_id = _event_user_id(data)
    scene_type, scene_id = _scene(channel, guild, user_id)
    message = _message_of(data, codec)
    return event_type(
        timestamp=timestamp,
        scene_type=scene_type,
        scene_id=scene_id,
        user_id=user_id,
        message_id=_packed_message_id(data),
        message=message,
        sender=_user_snapshot(data, user_id),
        is_mentioned=_is_mentioned(message, self_id),
        platform=platform,
        self_id=self_id,
        channel_id=_id(channel.get("id")),
        guild_id=_id((guild or {}).get("id")) or None,
    )


def _event_user_id(data: dict[str, Any]) -> str:
    user = data.get("user") or {}
    return _id(user.get("id"))


def _operator_id(data: dict[str, Any]) -> str:
    operator = data.get("operator") or {}
    return _id(operator.get("id")) or _event_user_id(data)


def _content_of(data: dict[str, Any]) -> str | None:
    content = (data.get("message") or {}).get("content")
    return str(content) if content else None


def _login_status(data: dict[str, Any]) -> int:
    login = data.get("login") or {}
    try:
        return int(login.get("status", 0))
    except (TypeError, ValueError):
        return 0


def _login_changed_event(data: dict[str, Any], timestamp: datetime) -> SatoriLoginChangedEvent:
    platform, self_id = _login_of(data)
    login = data.get("login") or {}
    return SatoriLoginChangedEvent(
        timestamp=timestamp,
        platform=platform,
        self_id=self_id,
        status=_login_status(data),
        adapter=str(login.get("adapter") or ""),
        features=[str(feature) for feature in (login.get("features") or [])],
    )


def _login_event(data: dict[str, Any], timestamp: datetime, *, online: bool) -> Event:
    if not online:
        return SatoriBotOfflineEvent(timestamp=timestamp, **_login_fields(data))
    if _login_status(data) != ONLINE:
        return _login_changed_event(data, timestamp)
    return SatoriBotOnlineEvent(timestamp=timestamp, **_login_fields(data))


def _login_fields(data: dict[str, Any]) -> dict[str, Any]:
    platform, self_id = _login_of(data)
    return {"platform": platform, "self_id": self_id, "status": _login_status(data)}


__all__ = [
    "ONLINE",
    "SatoriBotOfflineEvent",
    "SatoriBotOnlineEvent",
    "SatoriButtonInteractionEvent",
    "SatoriChannelChangedEvent",
    "SatoriCommandInteractionEvent",
    "SatoriGuildChangedEvent",
    "SatoriGuildEmojiChangedEvent",
    "SatoriGuildRoleChangedEvent",
    "SatoriInternalEvent",
    "SatoriLoginChangedEvent",
    "SatoriMessageReceivedEvent",
    "SatoriMessageUpdatedEvent",
    "translate_event",
]
