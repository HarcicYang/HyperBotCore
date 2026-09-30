from typing import ClassVar

from typing_extensions import override

from ..common import FileId, GroupId, MemberRole, MessageId, RequestId, SceneId, SceneType, UserId
from ..messages import Message
from .base import Action
from .formatting import format_actor, format_message, format_preview, format_scene, format_text, format_value
from .result import (
    BotProfile,
    BotStatus,
    CookieInfo,
    CsrfTokenInfo,
    FileReference,
    FileUrl,
    FriendInfo,
    GroupMemberProfile,
    GroupProfile,
    SendResult,
    UserProfile,
    VersionInfo,
)


class SendMessageAction(Action[SendResult]):
    scene_type: SceneType
    scene_id: SceneId
    message: Message

    @override
    def log_summary(self) -> str:
        return f"{format_scene(self.scene_type, self.scene_id)} send: {format_message(self.message)}"


class RecallMessageAction(Action[None]):
    message_id: MessageId

    @override
    def log_summary(self) -> str:
        return f"recall message {format_text(str(self.message_id))}"


class FetchMessageAction(Action[Message]):
    log_level: ClassVar[str] = "TRACE"
    message_id: MessageId

    @override
    def log_summary(self) -> str:
        return f"fetch message {format_text(str(self.message_id))}"


class GetBotProfileAction(Action[BotProfile]):
    log_level: ClassVar[str] = "TRACE"

    @override
    def log_summary(self) -> str:
        return "bot profile"


class GetBotStatusAction(Action[BotStatus]):
    log_level: ClassVar[str] = "TRACE"

    @override
    def log_summary(self) -> str:
        return "bot status"


class GetVersionAction(Action[VersionInfo]):
    log_level: ClassVar[str] = "TRACE"

    @override
    def log_summary(self) -> str:
        return "bot version"


class GetUserProfileAction(Action[UserProfile]):
    log_level: ClassVar[str] = "TRACE"
    user_id: UserId

    @override
    def log_summary(self) -> str:
        return f"user {format_actor(self.user_id)} profile"


class GetFriendListAction(Action[list[FriendInfo]]):
    log_level: ClassVar[str] = "TRACE"

    @override
    def log_summary(self) -> str:
        return "friend list"


class GetGroupProfileAction(Action[GroupProfile]):
    log_level: ClassVar[str] = "TRACE"
    group_id: GroupId

    @override
    def log_summary(self) -> str:
        return f"group {format_text(str(self.group_id))} profile"


class GetGroupListAction(Action[list[GroupProfile]]):
    log_level: ClassVar[str] = "TRACE"

    @override
    def log_summary(self) -> str:
        return "group list"


class GetGroupMemberAction(Action[GroupMemberProfile]):
    log_level: ClassVar[str] = "TRACE"
    group_id: GroupId
    user_id: UserId

    @override
    def log_summary(self) -> str:
        return f"group {format_text(str(self.group_id))} member {format_actor(self.user_id)} profile"


class GetGroupMemberListAction(Action[list[GroupMemberProfile]]):
    log_level: ClassVar[str] = "TRACE"
    group_id: GroupId

    @override
    def log_summary(self) -> str:
        return f"group {format_text(str(self.group_id))} member list"


class KickMemberAction(Action[None]):
    group_id: GroupId
    user_id: UserId

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} kick {format_actor(self.user_id)}"


class MuteMemberAction(Action[None]):
    group_id: GroupId
    user_id: UserId
    duration: int

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} mute {format_actor(self.user_id)} for {self.duration}s"


class UnmuteMemberAction(Action[None]):
    group_id: GroupId
    user_id: UserId

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} unmute {format_actor(self.user_id)}"


class SetMemberRoleAction(Action[None]):
    group_id: GroupId
    user_id: UserId
    role: MemberRole

    @override
    def log_summary(self) -> str:
        return (
            f"[group] {format_text(str(self.group_id))} set {format_actor(self.user_id)} role {format_value(self.role)}"
        )


class SetMemberTitleAction(Action[None]):
    group_id: GroupId
    user_id: UserId
    title: str

    @override
    def log_summary(self) -> str:
        return (
            f"[group] {format_text(str(self.group_id))} set {format_actor(self.user_id)}"
            f" title: {format_text(self.title)}"
        )


class SetMemberCardAction(Action[None]):
    group_id: GroupId
    user_id: UserId
    card: str

    @override
    def log_summary(self) -> str:
        return (
            f"[group] {format_text(str(self.group_id))} set {format_actor(self.user_id)} card: {format_text(self.card)}"
        )


class SetGroupNameAction(Action[None]):
    group_id: GroupId
    name: str

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} rename: {format_text(self.name)}"


class SetGroupMuteAction(Action[None]):
    group_id: GroupId
    muted: bool

    @override
    def log_summary(self) -> str:
        action = "mute all" if self.muted else "unmute all"
        return f"[group] {format_text(str(self.group_id))} {action}"


class LeaveGroupAction(Action[None]):
    group_id: GroupId

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} leave"


class ReactMessageAction(Action[None]):
    message_id: MessageId
    reaction: str
    enabled: bool = True

    @override
    def log_summary(self) -> str:
        action = "react" if self.enabled else "unreact"
        return f"{action} message {format_text(str(self.message_id))} with {format_text(self.reaction)}"


class SetEssenceAction(Action[None]):
    message_id: MessageId
    enabled: bool = True

    @override
    def log_summary(self) -> str:
        action = "add" if self.enabled else "remove"
        return f"{action} essence message {format_text(str(self.message_id))}"


class PokeAction(Action[None]):
    scene_type: SceneType
    scene_id: SceneId
    user_id: UserId

    @override
    def log_summary(self) -> str:
        return f"{format_scene(self.scene_type, self.scene_id)} poke {format_actor(self.user_id)}"


class ApproveFriendRequestAction(Action[None]):
    request_id: RequestId

    @override
    def log_summary(self) -> str:
        return f"friend request {format_text(str(self.request_id))} approve"


class RejectFriendRequestAction(Action[None]):
    request_id: RequestId
    reason: str | None = None

    @override
    def log_summary(self) -> str:
        reason = f": {format_preview(self.reason)}" if self.reason else ""
        return f"friend request {format_text(str(self.request_id))} reject{reason}"


class ApproveGroupRequestAction(Action[None]):
    request_id: RequestId

    @override
    def log_summary(self) -> str:
        return f"group request {format_text(str(self.request_id))} approve"


class RejectGroupRequestAction(Action[None]):
    request_id: RequestId
    reason: str | None = None

    @override
    def log_summary(self) -> str:
        reason = f": {format_preview(self.reason)}" if self.reason else ""
        return f"group request {format_text(str(self.request_id))} reject{reason}"


class GetFileInfoAction(Action[FileReference]):
    log_level: ClassVar[str] = "TRACE"
    file_id: FileId

    @override
    def log_summary(self) -> str:
        return f"file {format_text(str(self.file_id))} info"


class DownloadFileAction(Action[FileUrl]):
    log_level: ClassVar[str] = "TRACE"
    file_id: FileId

    @override
    def log_summary(self) -> str:
        return f"file {format_text(str(self.file_id))} download"


class SendLikeAction(Action[None]):
    user_id: UserId
    times: int = 1

    @override
    def log_summary(self) -> str:
        return f"send like to {format_actor(self.user_id)} x{self.times}"


class GetCookieAction(Action[CookieInfo]):
    log_level: ClassVar[str] = "TRACE"
    domain: str

    @override
    def log_summary(self) -> str:
        return f"get cookie for {format_text(self.domain)}"


class GetCsrfTokenAction(Action[CsrfTokenInfo]):
    log_level: ClassVar[str] = "TRACE"

    @override
    def log_summary(self) -> str:
        return "get csrf token"
