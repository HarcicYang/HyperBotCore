from typing_extensions import override

from ..common import FileInfo, MemberRole, ReactionValue, UserSnapshot
from ..messages import Message
from .base import Event, SceneEvent
from .formatting import (
    format_actor,
    format_id,
    format_message,
    format_scene,
    format_text,
    format_value,
    format_with_reason,
)


class MessageReceivedEvent(SceneEvent):
    message_id: str
    message: Message
    sender: UserSnapshot | None = None
    is_mentioned: bool = False

    @override
    def print_log(self) -> None:
        self._emit_log(
            f"{format_scene(self)} {format_actor(self.user_id, self.sender)}: {format_message(self.message)}"
        )


class MessageRecalledEvent(SceneEvent):
    message_id: str
    operator_id: str | None = None

    @override
    def print_log(self) -> None:
        actor = format_actor(self.operator_id or self.user_id)
        self._emit_log(f"{format_scene(self)} {actor} recalled message {format_id(self.message_id)}")


class MessageReactionChangedEvent(SceneEvent):
    message_id: str
    reaction: ReactionValue
    added: bool
    count: int | None = None

    @override
    def print_log(self) -> None:
        action = "added" if self.added else "removed"
        count = f" ({self.count})" if self.count is not None else ""
        reaction = format_value(self.reaction)
        self._emit_log(
            f"{format_scene(self)} {format_actor(self.user_id)} {action} reaction"
            f" {reaction}{count} on {format_id(self.message_id)}"
        )


class MemberJoinedEvent(SceneEvent):
    member_id: str
    operator_id: str | None = None
    inviter_id: str | None = None

    @override
    def print_log(self) -> None:
        inviter = f" via {format_actor(self.inviter_id)}" if self.inviter_id is not None else ""
        self._emit_log(f"{format_scene(self)} {format_actor(self.member_id)} joined{inviter}")


class MemberLeftEvent(SceneEvent):
    member_id: str
    operator_id: str | None = None
    kicked: bool = False

    @override
    def print_log(self) -> None:
        if self.kicked:
            message = f"{format_scene(self)} {format_actor(self.member_id)} kicked by {format_actor(self.operator_id)}"
        else:
            message = f"{format_scene(self)} {format_actor(self.member_id)} left"
        self._emit_log(message)


class MemberMuteChangedEvent(SceneEvent):
    member_id: str
    operator_id: str | None = None
    muted: bool
    duration: int | None = None

    @override
    def print_log(self) -> None:
        if not self.muted:
            message = f"{format_scene(self)} {format_actor(self.member_id)} unmuted by {format_actor(self.operator_id)}"
        else:
            duration = f" for {self.duration}s" if self.duration is not None else ""
            message = (
                f"{format_scene(self)} {format_actor(self.member_id)}"
                f" muted{duration} by {format_actor(self.operator_id)}"
            )
        self._emit_log(message)


class MemberRoleChangedEvent(SceneEvent):
    member_id: str
    operator_id: str | None = None
    old_role: MemberRole | None = None
    new_role: MemberRole

    @override
    def print_log(self) -> None:
        old_role = format_value(self.old_role) if self.old_role is not None else "unknown"
        self._emit_log(
            f"{format_scene(self)} {format_actor(self.member_id)} role"
            f" {old_role} -> {format_value(self.new_role)} by {format_actor(self.operator_id)}"
        )


class GroupNameChangedEvent(SceneEvent):
    old_name: str | None = None
    new_name: str
    operator_id: str | None = None

    @override
    def print_log(self) -> None:
        old_name = format_text(self.old_name) if self.old_name is not None else "unknown"
        self._emit_log(
            f"{format_scene(self)} group renamed {old_name} -> {format_text(self.new_name)}"
            f" by {format_actor(self.operator_id)}"
        )


class GroupMuteChangedEvent(SceneEvent):
    muted: bool
    duration: int | None = None
    operator_id: str | None = None

    @override
    def print_log(self) -> None:
        if not self.muted:
            message = f"{format_scene(self)} group unmuted by {format_actor(self.operator_id)}"
        else:
            duration = f" for {self.duration}s" if self.duration is not None else ""
            message = f"{format_scene(self)} group muted{duration} by {format_actor(self.operator_id)}"
        self._emit_log(message)


class FileUploadedEvent(SceneEvent):
    file: FileInfo

    @override
    def print_log(self) -> None:
        size = f" ({self.file.size} bytes)" if self.file.size > 0 else ""
        self._emit_log(
            f"{format_scene(self)} {format_actor(self.user_id)} uploaded file {format_text(self.file.name)}{size}"
        )


class EssenceChangedEvent(SceneEvent):
    message_id: str
    operator_id: str | None = None
    added: bool

    @override
    def print_log(self) -> None:
        action = "added" if self.added else "removed"
        self._emit_log(
            f"{format_scene(self)} {format_actor(self.operator_id)}"
            f" {action} message {format_id(self.message_id)} to essence"
        )


class PokeReceivedEvent(SceneEvent):
    target_id: str
    display_action: str | None = None
    display_suffix: str | None = None
    display_image_url: str | None = None

    @override
    def print_log(self) -> None:
        self._emit_log(f"{format_scene(self)} {format_actor(self.user_id)} poked {format_actor(self.target_id)}")


class FriendRequestedEvent(Event):
    request_id: str
    user_id: str
    comment: str | None = None

    @override
    def print_log(self) -> None:
        comment = f": {format_text(self.comment)}" if self.comment else ""
        self._emit_log(f"[user] {format_id(self.user_id)} friend request from {format_actor(self.user_id)}{comment}")


class FriendAddedEvent(Event):
    user_id: str

    @override
    def print_log(self) -> None:
        self._emit_log(f"[user] {format_id(self.user_id)} friend added")


class GroupJoinRequestedEvent(SceneEvent):
    request_id: str
    inviter_id: str | None = None
    comment: str | None = None

    @override
    def print_log(self) -> None:
        comment = f": {format_text(self.comment)}" if self.comment else ""
        self._emit_log(f"{format_scene(self)} join request from {format_actor(self.user_id)}{comment}")


class GroupInvitationReceivedEvent(SceneEvent):
    request_id: str | None = None
    inviter_id: str | None = None
    source_group_id: str | None = None

    @override
    def print_log(self) -> None:
        source = f" from group {format_id(self.source_group_id)}" if self.source_group_id is not None else ""
        self._emit_log(f"{format_scene(self)} invitation from {format_actor(self.inviter_id or self.user_id)}{source}")


class GroupMemberInviteRequestedEvent(SceneEvent):
    request_id: str
    inviter_id: str | None = None
    target_user_id: str

    @override
    def print_log(self) -> None:
        self._emit_log(
            f"{format_scene(self)} {format_actor(self.inviter_id)}"
            f" requested to invite {format_actor(self.target_user_id)}"
        )


class BotOnlineEvent(Event):
    reason: str | None = None

    @override
    def print_log(self) -> None:
        self._emit_log(format_with_reason("[bot] online", self.reason))


class BotOfflineEvent(Event):
    reason: str | None = None

    @override
    def print_log(self) -> None:
        self._emit_log(format_with_reason("[bot] offline", self.reason))


class ClientStartedEvent(Event):
    @override
    def print_log(self) -> None:
        self._emit_log("[client] started")


class ClientStoppedEvent(Event):
    @override
    def print_log(self) -> None:
        self._emit_log("[client] stopped")
