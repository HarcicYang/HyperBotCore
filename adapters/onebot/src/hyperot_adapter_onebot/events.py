from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from hyperot.v2.common import (
    FileId,
    FileInfo,
    GroupId,
    MemberRole,
    MessageId,
    ReactionKind,
    ReactionValue,
    RequestId,
    SceneId,
    SceneType,
    UserId,
    UserSex,
    UserSnapshot,
)
from hyperot.v2.events import (
    EssenceChangedEvent,
    Event,
    FileUploadedEvent,
    FriendAddedEvent,
    FriendRequestedEvent,
    GroupInvitationReceivedEvent,
    GroupJoinRequestedEvent,
    GroupMuteChangedEvent,
    GroupNameChangedEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MemberMuteChangedEvent,
    MemberRoleChangedEvent,
    MessageReactionChangedEvent,
    MessageRecalledEvent,
    MessageReceivedEvent,
    PokeReceivedEvent,
    SceneEvent,
)
from hyperot.v2.hyperogger import Logger
from hyperot.v2.messages import Mention, MentionAll, Message

from .segments import OneBotSegmentCodec

logger = Logger.fetch("hyperot.v2.events")
MessageGroupLookup = Callable[[MessageId], GroupId | None]


def _id(value: object) -> str:
    return str(value)


def _has_group(value: object) -> bool:
    return value not in (None, 0, "0", "")


def _timestamp(value: object) -> datetime:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return datetime.now(UTC)


def _role(value: object) -> MemberRole:
    match value:
        case "owner":
            return MemberRole.OWNER
        case "admin":
            return MemberRole.ADMIN
        case _:
            return MemberRole.MEMBER


def _member_role_or_none(value: object) -> MemberRole | None:
    if value is None:
        return None
    return _role(value)


def _sex(value: object) -> UserSex | None:
    match value:
        case "male":
            return UserSex.MALE
        case "female":
            return UserSex.FEMALE
        case "unknown":
            return UserSex.UNKNOWN
        case _:
            return None


def _is_mentioned(message: Message, self_id: UserId) -> bool:
    for segment in message:
        if isinstance(segment, MentionAll):
            return True
        if isinstance(segment, Mention) and str(segment.user_id) == str(self_id):
            return True
    return False


class OneBotAnonymousInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    flag: str


class OneBotMessageReceivedEvent(MessageReceivedEvent):
    self_id: UserId
    sub_type: str | None = None
    raw_message: str | None = None
    font: int | None = None
    anonymous: OneBotAnonymousInfo | None = None
    sender_age: int | None = None
    sender_area: str | None = None
    sender_level: str | None = None


class OneBotFileUploadedEvent(FileUploadedEvent):
    busid: int | None = None
    file_hash: str | None = None


class OneBotGroupCardChangedEvent(SceneEvent):
    member_id: UserId
    old_card: str | None = None
    new_card: str


class OneBotMemberLeftEvent(MemberLeftEvent):
    sub_type: str | None = None
    self_kicked: bool = False


class OneBotPokeReceivedEvent(PokeReceivedEvent):
    poke_type: str | None = None
    poke_id: str | None = None


class OneBotLuckyKingEvent(SceneEvent):
    sender_id: UserId
    target_id: UserId


class OneBotHonorEvent(SceneEvent):
    member_id: UserId
    honor_type: str


class OneBotLifecycleEvent(Event):
    sub_type: str


class OneBotHeartbeatStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    online: bool = False
    good: bool = False


class OneBotHeartbeatEvent(Event):
    log_enabled: ClassVar[bool] = False

    interval: int
    status: OneBotHeartbeatStatus


class OneBotReactionEvent(Event):
    log_enabled: ClassVar[bool] = False

    message_id: MessageId
    operator_id: UserId
    reaction: ReactionValue
    added: bool
    count: int | None = None
    group_id: GroupId | None = None


def translate_event(
    data: dict[str, Any],
    codec: OneBotSegmentCodec,
    message_group_lookup: MessageGroupLookup | None = None,
) -> Event | None:
    post_type = data.get("post_type")
    if post_type == "meta_event":
        timestamp = _timestamp(data.get("time"))
        meta_event_type = data.get("meta_event_type")
        if meta_event_type == "lifecycle":
            return OneBotLifecycleEvent(timestamp=timestamp, sub_type=str(data.get("sub_type", "")))
        if meta_event_type == "heartbeat":
            status = data.get("status") or {}
            return OneBotHeartbeatEvent(
                timestamp=timestamp,
                interval=int(data.get("interval", 0)),
                status=OneBotHeartbeatStatus(
                    online=bool(status.get("online", False)),
                    good=bool(status.get("good", False)),
                ),
            )
        return None

    if post_type == "message":
        message_type = data.get("message_type")
        scene_type = SceneType.USER if message_type == "private" else SceneType.GROUP
        scene_id = SceneId(_id(data.get("user_id") if scene_type == SceneType.USER else data.get("group_id")))
        user_id = UserId(_id(data.get("user_id", 0)))
        self_id = UserId(_id(data.get("self_id", 0)))
        message_payload = data.get("message", [])
        if not isinstance(message_payload, list):
            logger.warning("OneBot message event rejected: message must be an array")
            return None
        message = codec.decode_message(message_payload)
        sender_data = data.get("sender") or {}
        anonymous_data = data.get("anonymous")
        return OneBotMessageReceivedEvent(
            timestamp=_timestamp(data.get("time")),
            scene_type=scene_type,
            scene_id=scene_id,
            user_id=user_id,
            message_id=MessageId(_id(data.get("message_id", ""))),
            message=message,
            sender=UserSnapshot(
                user_id=UserId(_id(sender_data.get("user_id", user_id))),
                nick_name=sender_data.get("nickname"),
                display_name=sender_data.get("card") or sender_data.get("nickname"),
                sex=_sex(sender_data.get("sex")),
                role=_member_role_or_none(sender_data.get("role")),
                title=sender_data.get("title"),
            ),
            is_mentioned=_is_mentioned(message, self_id),
            self_id=self_id,
            sub_type=data.get("sub_type"),
            raw_message=data.get("raw_message"),
            font=int(data["font"]) if data.get("font") is not None else None,
            anonymous=(
                OneBotAnonymousInfo(
                    id=_id(anonymous_data.get("id", "")),
                    name=str(anonymous_data.get("name", "")),
                    flag=str(anonymous_data.get("flag", "")),
                )
                if isinstance(anonymous_data, dict)
                else None
            ),
            sender_age=int(sender_data["age"]) if sender_data.get("age") is not None else None,
            sender_area=sender_data.get("area"),
            sender_level=sender_data.get("level"),
        )

    if post_type == "notice":
        return _translate_notice(data, message_group_lookup)

    if post_type == "request":
        return _translate_request(data)

    return None


def _translate_notice(
    data: dict[str, Any],
    message_group_lookup: MessageGroupLookup | None = None,
) -> Event | None:
    notice_type = data.get("notice_type")
    timestamp = _timestamp(data.get("time"))
    user_id = UserId(_id(data.get("user_id", 0)))
    group_id = GroupId(_id(data.get("group_id", 0)))
    scene = {
        "scene_type": SceneType.GROUP,
        "scene_id": SceneId(str(group_id)),
        "user_id": user_id,
        "timestamp": timestamp,
    }

    if notice_type in {"group_recall", "friend_recall"}:
        if notice_type == "friend_recall":
            return MessageRecalledEvent(
                timestamp=timestamp,
                scene_type=SceneType.USER,
                scene_id=SceneId(str(user_id)),
                user_id=user_id,
                message_id=MessageId(_id(data.get("message_id", ""))),
            )
        return MessageRecalledEvent(
            **scene,
            message_id=MessageId(_id(data.get("message_id", ""))),
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
        )

    if notice_type == "group_admin":
        is_set = data.get("sub_type") == "set"
        return MemberRoleChangedEvent(
            **scene,
            member_id=user_id,
            old_role=None,
            new_role=MemberRole.ADMIN if is_set else MemberRole.MEMBER,
        )

    if notice_type == "group_increase":
        return MemberJoinedEvent(
            **scene,
            member_id=user_id,
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
            inviter_id=UserId(_id(data["operator_id"])) if data.get("sub_type") == "invite" else None,
        )

    if notice_type == "group_decrease":
        return OneBotMemberLeftEvent(
            **scene,
            member_id=user_id,
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
            kicked=data.get("sub_type") in {"kick", "kick_me"},
            sub_type=data.get("sub_type"),
            self_kicked=data.get("sub_type") == "kick_me",
        )

    if notice_type == "group_ban":
        muted = data.get("sub_type") == "ban"
        duration = data.get("duration")
        return MemberMuteChangedEvent(
            **scene,
            member_id=user_id,
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
            muted=muted,
            duration=int(duration) if muted and duration is not None else None,
        )

    if notice_type == "group_whole_mute":
        return GroupMuteChangedEvent(
            **scene,
            muted=bool(data.get("is_mute", data.get("sub_type") == "mute")),
            duration=int(data["duration"]) if data.get("duration") is not None else None,
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
        )

    if notice_type == "group_name_change":
        return GroupNameChangedEvent(
            **scene,
            old_name=data.get("old_group_name"),
            new_name=str(data.get("new_group_name", "")),
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
        )

    if notice_type == "group_card":
        return OneBotGroupCardChangedEvent(
            **scene,
            member_id=user_id,
            old_card=data.get("card_old"),
            new_card=str(data.get("card_new", "")),
        )

    if notice_type in {"group_upload", "friend_upload"}:
        file_data = data.get("file") or {}
        scene_type = SceneType.GROUP if notice_type == "group_upload" else SceneType.USER
        scene_id = group_id if scene_type == SceneType.GROUP else user_id
        return OneBotFileUploadedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=SceneId(str(scene_id)),
            user_id=user_id,
            file=FileInfo(
                file_id=FileId(_id(file_data.get("id", file_data.get("file_id", "")))),
                name=str(file_data.get("name", file_data.get("file_name", ""))),
                size=int(file_data.get("size") or file_data.get("file_size") or 0),
            ),
            busid=int(file_data["busid"]) if file_data.get("busid") is not None else None,
            file_hash=file_data.get("hash") or file_data.get("file_hash"),
        )

    if notice_type == "notify" and data.get("sub_type") == "poke":
        if not _has_group(data.get("group_id")):
            return OneBotPokeReceivedEvent(
                timestamp=timestamp,
                scene_type=SceneType.USER,
                scene_id=SceneId(str(user_id)),
                user_id=user_id,
                target_id=UserId(_id(data.get("target_id", 0))),
                poke_type=data.get("type"),
                poke_id=data.get("id"),
            )
        return OneBotPokeReceivedEvent(
            **scene,
            target_id=UserId(_id(data.get("target_id", 0))),
            poke_type=data.get("type"),
            poke_id=data.get("id"),
        )

    if notice_type == "notify" and data.get("sub_type") == "lucky_king":
        return OneBotLuckyKingEvent(
            **scene,
            sender_id=user_id,
            target_id=UserId(_id(data.get("target_id", 0))),
        )

    if notice_type == "notify" and data.get("sub_type") == "honor":
        return OneBotHonorEvent(
            **scene,
            member_id=user_id,
            honor_type=str(data.get("honor_type", "")),
        )

    if notice_type == "essence":
        return EssenceChangedEvent(
            **scene,
            message_id=MessageId(_id(data.get("message_id", ""))),
            operator_id=UserId(_id(data["operator_id"])) if data.get("operator_id") else None,
            added=data.get("sub_type") == "add",
        )

    if notice_type in {"reaction", "group_msg_emoji_like"}:
        reaction_type = data.get("reaction_type")
        code = str(data.get("code", ""))
        reaction_kind = (
            ReactionKind.EMOJI if reaction_type == "emoji" or not code.lstrip("-").isdigit() else ReactionKind.FACE
        )
        message_id = MessageId(_id(data.get("message_id", "")))
        group_id = data.get("group_id")
        if not _has_group(group_id) and message_group_lookup is not None:
            group_id = message_group_lookup(message_id)
        if not _has_group(group_id):
            logger.warning(f"OneBot reaction event could not resolve group context: message_id={message_id}")
            return OneBotReactionEvent(
                timestamp=timestamp,
                message_id=message_id,
                operator_id=UserId(_id(data.get("operator_id") or data.get("user_id", 0))),
                reaction=ReactionValue(kind=reaction_kind, value=code),
                added=data.get("sub_type") == "add",
                count=int(data["count"]) if data.get("count") is not None else None,
            )
        return MessageReactionChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=SceneId(str(group_id)),
            user_id=UserId(_id(data.get("operator_id") or data.get("user_id", 0))),
            message_id=message_id,
            reaction=ReactionValue(
                kind=reaction_kind,
                value=code,
            ),
            added=data.get("sub_type") == "add",
            count=int(data["count"]) if data.get("count") is not None else None,
        )

    if notice_type == "friend_add":
        return FriendAddedEvent(
            timestamp=timestamp,
            user_id=UserId(_id(data.get("user_id", 0))),
        )

    return None


def _translate_request(data: dict[str, Any]) -> Event | None:
    request_type = data.get("request_type")
    timestamp = _timestamp(data.get("time"))
    user_id = UserId(_id(data.get("user_id", 0)))
    request_id = RequestId(_id(data.get("flag", "")))
    comment = data.get("comment")
    if request_type == "friend":
        return FriendRequestedEvent(
            timestamp=timestamp,
            request_id=request_id,
            user_id=user_id,
            comment=comment,
        )
    if request_type == "group":
        group_id = GroupId(_id(data.get("group_id", 0)))
        sub_type = data.get("sub_type")
        if sub_type == "invite":
            return GroupInvitationReceivedEvent(
                timestamp=timestamp,
                scene_type=SceneType.GROUP,
                scene_id=SceneId(str(group_id)),
                user_id=user_id,
                request_id=request_id,
                inviter_id=user_id,
            )
        return GroupJoinRequestedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=SceneId(str(group_id)),
            user_id=user_id,
            request_id=request_id,
            inviter_id=None,
            comment=comment,
        )
    return None
