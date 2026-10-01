from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from hyperot.v2.common import (
    FileInfo,
    MemberRole,
    ReactionKind,
    ReactionValue,
    SceneType,
    UserSex,
    UserSnapshot,
)
from hyperot.v2.events import (
    BotOfflineEvent,
    EssenceChangedEvent,
    Event,
    FileUploadedEvent,
    FriendRequestedEvent,
    GroupInvitationReceivedEvent,
    GroupJoinRequestedEvent,
    GroupMemberInviteRequestedEvent,
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

from .ids import (
    SCENE_FRIEND,
    SCENE_GROUP,
    SCENE_TEMP,
    encode_group_invitation_id,
    encode_group_request_id,
    encode_message_id,
)
from .segments import MilkySegmentCodec

logger = Logger.fetch("hyperot.v2.events")


def _id(value: object) -> str:
    return str(value)


def _timestamp(value: object) -> datetime:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return datetime.now(UTC)


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


def _role(value: object) -> MemberRole | None:
    match value:
        case "owner":
            return MemberRole.OWNER
        case "admin":
            return MemberRole.ADMIN
        case "member":
            return MemberRole.MEMBER
        case _:
            return None


def _reaction_kind(value: object) -> ReactionKind:
    return ReactionKind.FACE if value == "face" else ReactionKind.EMOJI


def _is_mentioned(message: Message, self_id: str) -> bool:
    for segment in message:
        if isinstance(segment, MentionAll):
            return True
        if isinstance(segment, Mention) and str(segment.user_id) == str(self_id):
            return True
    return False


class MilkyMessageReceivedEvent(MessageReceivedEvent):
    self_id: str
    message_scene: str


class MilkyPeerPinChangedEvent(SceneEvent):
    is_pinned: bool


class MilkyGroupDisbandedEvent(SceneEvent):
    operator_id: str


class MilkyFriendRequestedEvent(FriendRequestedEvent):
    initiator_id: str
    initiator_uid: str
    via: str | None = None
    is_filtered: bool = False


class MilkyGroupJoinRequestedEvent(GroupJoinRequestedEvent):
    notification_seq: str
    notification_type: str = "join_request"
    is_filtered: bool = False


class MilkyMemberInviteRequestedEvent(GroupMemberInviteRequestedEvent):
    notification_seq: str
    notification_type: str = "invited_join_request"
    is_filtered: bool = False


class MilkyGroupInvitationReceivedEvent(GroupInvitationReceivedEvent):
    invitation_seq: str


class MilkyFriendFileUploadedEvent(FileUploadedEvent):
    file_hash: str | None = None
    is_self: bool = False


def scene_of(message_scene: object) -> tuple[SceneType, str]:
    match message_scene:
        case "group":
            return SceneType.GROUP, SCENE_GROUP
        case "temp":
            return SceneType.USER, SCENE_TEMP
        case _:
            return SceneType.USER, SCENE_FRIEND


def translate_event(data: dict[str, Any], codec: MilkySegmentCodec) -> Event | None:
    event_type = data.get("event_type")
    timestamp = _timestamp(data.get("time"))

    if event_type == "bot_offline":
        return BotOfflineEvent(timestamp=timestamp, reason=str(data.get("data", {}).get("reason", "")))

    if event_type == "message_receive":
        return _translate_message(data.get("data") or {}, _id(data.get("self_id", 0)), timestamp, codec)

    if event_type == "message_recall":
        payload = data.get("data") or {}
        scene_type, scene_name = scene_of(payload.get("message_scene"))
        return MessageRecalledEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=_id(payload.get("peer_id", 0))
            if scene_type is SceneType.GROUP
            else _id(payload.get("sender_id", 0)),
            user_id=_id(payload.get("sender_id", 0)),
            message_id=encode_message_id(scene_name, payload.get("peer_id", 0), payload.get("message_seq", 0)),
            operator_id=_id(payload["operator_id"]) if payload.get("operator_id") else None,
        )

    if event_type == "peer_pin_change":
        payload = data.get("data") or {}
        scene_type, _ = scene_of(payload.get("message_scene"))
        return MilkyPeerPinChangedEvent(
            timestamp=timestamp,
            scene_type=scene_type,
            scene_id=_id(payload.get("peer_id", 0)),
            is_pinned=bool(payload.get("is_pinned", False)),
        )

    if event_type == "friend_request":
        payload = data.get("data") or {}
        return MilkyFriendRequestedEvent(
            timestamp=timestamp,
            request_id=str(payload.get("initiator_uid", "")),
            user_id=_id(payload.get("initiator_id", 0)),
            comment=payload.get("comment"),
            initiator_id=_id(payload.get("initiator_id", 0)),
            initiator_uid=str(payload.get("initiator_uid", "")),
            via=payload.get("via"),
            is_filtered=bool(payload.get("is_filtered", False)),
        )

    if event_type == "group_join_request":
        payload = data.get("data") or {}
        group_id = _id(payload.get("group_id", 0))
        return MilkyGroupJoinRequestedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=group_id,
            user_id=_id(payload.get("initiator_id", 0)),
            request_id=encode_group_request_id(group_id, payload.get("notification_seq", 0)),
            comment=payload.get("comment"),
            notification_seq=_id(payload.get("notification_seq", 0)),
            notification_type="join_request",
            is_filtered=bool(payload.get("is_filtered", False)),
        )

    if event_type == "group_invited_join_request":
        payload = data.get("data") or {}
        group_id = _id(payload.get("group_id", 0))
        return MilkyMemberInviteRequestedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=group_id,
            user_id=_id(payload.get("initiator_id", 0)),
            request_id=encode_group_request_id(group_id, payload.get("notification_seq", 0)),
            inviter_id=_id(payload.get("initiator_id", 0)),
            target_user_id=_id(payload.get("target_user_id", 0)),
            notification_seq=_id(payload.get("notification_seq", 0)),
            notification_type="invited_join_request",
            is_filtered=bool(payload.get("is_filtered", False)),
        )

    if event_type == "group_invitation":
        payload = data.get("data") or {}
        group_id = _id(payload.get("group_id", 0))
        return MilkyGroupInvitationReceivedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=group_id,
            user_id=_id(payload.get("initiator_id", 0)),
            request_id=encode_group_invitation_id(group_id, payload.get("invitation_seq", 0)),
            inviter_id=_id(payload.get("initiator_id", 0)),
            source_group_id=_id(payload["source_group_id"]) if payload.get("source_group_id") else None,
            invitation_seq=_id(payload.get("invitation_seq", 0)),
        )

    if event_type == "friend_nudge":
        payload = data.get("data") or {}
        return PokeReceivedEvent(
            timestamp=timestamp,
            scene_type=SceneType.USER,
            scene_id=_id(payload.get("user_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            target_id=_id(data.get("self_id", 0)),
            display_action=payload.get("display_action"),
            display_suffix=payload.get("display_suffix"),
            display_image_url=payload.get("display_action_img_url"),
        )

    if event_type == "group_nudge":
        payload = data.get("data") or {}
        return PokeReceivedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("sender_id", 0)),
            target_id=_id(payload.get("receiver_id", 0)),
            display_action=payload.get("display_action"),
            display_suffix=payload.get("display_suffix"),
            display_image_url=payload.get("display_action_img_url"),
        )

    if event_type == "friend_file_upload":
        payload = data.get("data") or {}
        return MilkyFriendFileUploadedEvent(
            timestamp=timestamp,
            scene_type=SceneType.USER,
            scene_id=_id(payload.get("user_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            file=_file_info(payload),
            file_hash=payload.get("file_hash"),
            is_self=bool(payload.get("is_self", False)),
        )

    if event_type == "group_admin_change":
        payload = data.get("data") or {}
        return MemberRoleChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            member_id=_id(payload.get("user_id", 0)),
            operator_id=_id(payload["operator_id"]) if payload.get("operator_id") else None,
            old_role=None,
            new_role=MemberRole.ADMIN if payload.get("is_set") else MemberRole.MEMBER,
        )

    if event_type == "group_essence_message_change":
        payload = data.get("data") or {}
        group_id = _id(payload.get("group_id", 0))
        return EssenceChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=group_id,
            user_id=_id(payload.get("operator_id", 0)),
            message_id=encode_message_id(SCENE_GROUP, group_id, payload.get("message_seq", 0)),
            operator_id=_id(payload["operator_id"]) if payload.get("operator_id") else None,
            added=bool(payload.get("is_set", False)),
        )

    if event_type == "group_member_increase":
        payload = data.get("data") or {}
        return MemberJoinedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            member_id=_id(payload.get("user_id", 0)),
            operator_id=_id(payload["operator_id"]) if payload.get("operator_id") else None,
            inviter_id=_id(payload["invitor_id"]) if payload.get("invitor_id") else None,
        )

    if event_type == "group_member_decrease":
        payload = data.get("data") or {}
        operator_id = _id(payload["operator_id"]) if payload.get("operator_id") else None
        return MemberLeftEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            member_id=_id(payload.get("user_id", 0)),
            operator_id=operator_id,
            kicked=operator_id is not None,
        )

    if event_type == "group_disband":
        payload = data.get("data") or {}
        return MilkyGroupDisbandedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            operator_id=_id(payload.get("operator_id", 0)),
        )

    if event_type == "group_name_change":
        payload = data.get("data") or {}
        return GroupNameChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("operator_id", 0)),
            old_name=None,
            new_name=str(payload.get("new_group_name", "")),
            operator_id=_id(payload.get("operator_id", 0)),
        )

    if event_type == "group_message_reaction":
        payload = data.get("data") or {}
        group_id = _id(payload.get("group_id", 0))
        return MessageReactionChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=group_id,
            user_id=_id(payload.get("user_id", 0)),
            message_id=encode_message_id(SCENE_GROUP, group_id, payload.get("message_seq", 0)),
            reaction=ReactionValue(
                kind=_reaction_kind(payload.get("reaction_type", "face")),
                value=str(payload.get("face_id", "")),
            ),
            added=bool(payload.get("is_add", False)),
        )

    if event_type == "group_mute":
        payload = data.get("data") or {}
        duration = int(payload.get("duration") or 0)
        return MemberMuteChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            member_id=_id(payload.get("user_id", 0)),
            operator_id=_id(payload["operator_id"]) if payload.get("operator_id") else None,
            muted=duration > 0,
            duration=duration,
        )

    if event_type == "group_whole_mute":
        payload = data.get("data") or {}
        return GroupMuteChangedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("operator_id", 0)),
            muted=bool(payload.get("is_mute", False)),
            operator_id=_id(payload["operator_id"]) if payload.get("operator_id") else None,
        )

    if event_type == "group_file_upload":
        payload = data.get("data") or {}
        return FileUploadedEvent(
            timestamp=timestamp,
            scene_type=SceneType.GROUP,
            scene_id=_id(payload.get("group_id", 0)),
            user_id=_id(payload.get("user_id", 0)),
            file=_file_info(payload),
        )

    # Milky 1.2 asks application ends to ignore event types they do not know.
    logger.warning(f"忽略未知的 Milky 事件类型：{event_type}")
    return None


def _translate_message(
    payload: dict[str, Any],
    self_id: str,
    timestamp: datetime,
    codec: MilkySegmentCodec,
) -> Event | None:
    scene_type, scene_name = scene_of(payload.get("message_scene"))
    peer_id = payload.get("peer_id", 0)
    sender_id = _id(payload.get("sender_id", 0))
    message = codec.decode_message(payload.get("segments") or [], scene=scene_name, peer_id=peer_id)
    scene_id = _id(peer_id) if scene_type is SceneType.GROUP else sender_id
    return MilkyMessageReceivedEvent(
        timestamp=timestamp,
        scene_type=scene_type,
        scene_id=scene_id,
        user_id=sender_id,
        message_id=encode_message_id(scene_name, peer_id, payload.get("message_seq", 0)),
        message=message,
        sender=_sender_snapshot(payload, sender_id, scene_name),
        is_mentioned=_is_mentioned(message, self_id),
        self_id=self_id,
        message_scene=scene_name,
    )


def _sender_snapshot(payload: dict[str, Any], sender_id: str, scene_name: str) -> UserSnapshot:
    member = payload.get("group_member") or {}
    friend = payload.get("friend") or {}
    if scene_name == SCENE_GROUP and member:
        return UserSnapshot(
            user_id=_id(member.get("user_id", sender_id)),
            nick_name=member.get("nickname"),
            display_name=member.get("card") or member.get("nickname"),
            sex=_sex(member.get("sex")),
            role=_role(member.get("role")),
            title=member.get("title"),
        )
    source = friend or member
    if source:
        return UserSnapshot(
            user_id=_id(source.get("user_id", sender_id)),
            nick_name=source.get("nickname"),
            display_name=source.get("nickname"),
            sex=_sex(source.get("sex")),
        )
    return UserSnapshot(user_id=sender_id)


def _file_info(payload: dict[str, Any]) -> FileInfo:
    return FileInfo(
        file_id=_id(payload.get("file_id", "")),
        name=str(payload.get("file_name", "")),
        size=int(payload.get("file_size") or 0),
    )


__all__ = [
    "MilkyFriendFileUploadedEvent",
    "MilkyFriendRequestedEvent",
    "MilkyGroupDisbandedEvent",
    "MilkyGroupInvitationReceivedEvent",
    "MilkyGroupJoinRequestedEvent",
    "MilkyMemberInviteRequestedEvent",
    "MilkyMessageReceivedEvent",
    "MilkyPeerPinChangedEvent",
    "scene_of",
    "translate_event",
]
