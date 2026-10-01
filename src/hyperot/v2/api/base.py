from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import JsonValue

from ..actions import (
    ApproveFriendRequestAction,
    ApproveGroupRequestAction,
    BotProfile,
    BotStatus,
    DownloadFileAction,
    FetchMessageAction,
    FileReference,
    FileUrl,
    GetBotProfileAction,
    GetBotStatusAction,
    GetFileInfoAction,
    GetGroupMemberAction,
    GetGroupMemberListAction,
    GetGroupProfileAction,
    GetUserProfileAction,
    GetVersionAction,
    GroupMemberProfile,
    GroupProfile,
    KickMemberAction,
    LeaveGroupAction,
    MuteMemberAction,
    PokeAction,
    RawAction,
    RawResult,
    ReactMessageAction,
    RecallMessageAction,
    RejectFriendRequestAction,
    RejectGroupRequestAction,
    SendMessageAction,
    SendResult,
    SetEssenceAction,
    SetGroupMuteAction,
    SetGroupNameAction,
    SetMemberCardAction,
    SetMemberRoleAction,
    SetMemberTitleAction,
    UnmuteMemberAction,
    UserProfile,
    VersionInfo,
)
from ..common import FileId, GroupId, MemberRole, MessageId, RequestId, SceneId, SceneType, UserId
from ..messages import Message, Quote
from .context import APIContext


@dataclass(frozen=True, slots=True)
class SceneAPI:
    _context: APIContext
    _scene_type: SceneType
    _scene_id: SceneId

    async def send(self, message: Message | str) -> SendResult:
        if isinstance(message, str):
            message = Message.text(message)
        return await self._context.execute(
            SendMessageAction(
                scene_type=self._scene_type,
                scene_id=self._scene_id,
                message=message,
            )
        )

    async def recall(self, message_id: MessageId) -> None:
        await self._context.execute(RecallMessageAction(message_id=message_id))

    async def poke(self, user_id: UserId) -> None:
        await self._context.execute(
            PokeAction(
                scene_type=self._scene_type,
                scene_id=self._scene_id,
                user_id=user_id,
            )
        )


@dataclass(frozen=True, slots=True)
class UserAPI(SceneAPI):
    user_id: UserId

    async def profile(self) -> UserProfile:
        return await self._context.execute(GetUserProfileAction(user_id=self.user_id))


@dataclass(frozen=True, slots=True)
class GroupMemberAPI:
    _context: APIContext
    group_id: GroupId
    user_id: UserId

    async def profile(self) -> GroupMemberProfile:
        return await self._context.execute(
            GetGroupMemberAction(
                group_id=self.group_id,
                user_id=self.user_id,
            )
        )

    async def kick(self) -> None:
        await self._context.execute(KickMemberAction(group_id=self.group_id, user_id=self.user_id))

    async def mute(self, duration: int) -> None:
        await self._context.execute(
            MuteMemberAction(
                group_id=self.group_id,
                user_id=self.user_id,
                duration=duration,
            )
        )

    async def unmute(self) -> None:
        await self._context.execute(UnmuteMemberAction(group_id=self.group_id, user_id=self.user_id))

    async def set_role(self, role: MemberRole) -> None:
        await self._context.execute(
            SetMemberRoleAction(
                group_id=self.group_id,
                user_id=self.user_id,
                role=role,
            )
        )

    async def set_title(self, title: str) -> None:
        await self._context.execute(
            SetMemberTitleAction(
                group_id=self.group_id,
                user_id=self.user_id,
                title=title,
            )
        )

    async def set_card(self, card: str) -> None:
        await self._context.execute(
            SetMemberCardAction(
                group_id=self.group_id,
                user_id=self.user_id,
                card=card,
            )
        )


@dataclass(frozen=True, slots=True)
class GroupAPI(SceneAPI):
    group_id: GroupId

    def member(self, user_id: UserId) -> GroupMemberAPI:
        return GroupMemberAPI(self._context, self.group_id, user_id)

    async def profile(self) -> GroupProfile:
        return await self._context.execute(GetGroupProfileAction(group_id=self.group_id))

    async def members(self) -> list[GroupMemberProfile]:
        return await self._context.execute(GetGroupMemberListAction(group_id=self.group_id))

    async def set_name(self, name: str) -> None:
        await self._context.execute(SetGroupNameAction(group_id=self.group_id, name=name))

    async def mute_all(self) -> None:
        await self._context.execute(SetGroupMuteAction(group_id=self.group_id, muted=True))

    async def unmute_all(self) -> None:
        await self._context.execute(SetGroupMuteAction(group_id=self.group_id, muted=False))

    async def leave(self) -> None:
        await self._context.execute(LeaveGroupAction(group_id=self.group_id))


@dataclass(frozen=True, slots=True)
class MessageAPI:
    _context: APIContext
    message_id: MessageId

    async def fetch(self) -> Message:
        return await self._context.execute(FetchMessageAction(message_id=self.message_id))

    async def quote(self) -> Quote:
        message = await self.fetch()
        return Quote(message_id=self.message_id, message=message)

    async def recall(self) -> None:
        await self._context.execute(RecallMessageAction(message_id=self.message_id))

    async def react(self, reaction: str) -> None:
        await self._context.execute(
            ReactMessageAction(
                message_id=self.message_id,
                reaction=reaction,
                enabled=True,
            )
        )

    async def unreact(self, reaction: str) -> None:
        await self._context.execute(
            ReactMessageAction(
                message_id=self.message_id,
                reaction=reaction,
                enabled=False,
            )
        )

    async def set_essence(self) -> None:
        await self._context.execute(SetEssenceAction(message_id=self.message_id, enabled=True))

    async def remove_essence(self) -> None:
        await self._context.execute(SetEssenceAction(message_id=self.message_id, enabled=False))


@dataclass(frozen=True, slots=True)
class FriendRequestAPI:
    _context: APIContext
    request_id: RequestId

    async def approve(self) -> None:
        await self._context.execute(ApproveFriendRequestAction(request_id=self.request_id))

    async def reject(self, reason: str | None = None) -> None:
        await self._context.execute(
            RejectFriendRequestAction(
                request_id=self.request_id,
                reason=reason,
            )
        )


@dataclass(frozen=True, slots=True)
class GroupRequestAPI:
    _context: APIContext
    request_id: RequestId

    async def approve(self) -> None:
        await self._context.execute(ApproveGroupRequestAction(request_id=self.request_id))

    async def reject(self, reason: str | None = None) -> None:
        await self._context.execute(
            RejectGroupRequestAction(
                request_id=self.request_id,
                reason=reason,
            )
        )


@dataclass(frozen=True, slots=True)
class FileAPI:
    _context: APIContext
    file_id: FileId

    async def info(self) -> FileReference:
        return await self._context.execute(GetFileInfoAction(file_id=self.file_id))

    async def download(self) -> FileUrl:
        return await self._context.execute(DownloadFileAction(file_id=self.file_id))


@dataclass(frozen=True, slots=True)
class BotAPI:
    _context: APIContext

    async def profile(self) -> BotProfile:
        return await self._context.execute(GetBotProfileAction())

    async def status(self) -> BotStatus:
        return await self._context.execute(GetBotStatusAction())

    async def version(self) -> VersionInfo:
        return await self._context.execute(GetVersionAction())


class ClientAPI:
    def __init__(self, context: APIContext) -> None:
        self._context = context

    def scene(self, scene_type: SceneType, scene_id: SceneId) -> SceneAPI:
        return SceneAPI(self._context, scene_type, scene_id)

    def user(self, user_id: UserId) -> UserAPI:
        return UserAPI(self._context, SceneType.USER, SceneId(str(user_id)), user_id)

    def group(self, group_id: GroupId) -> GroupAPI:
        return GroupAPI(self._context, SceneType.GROUP, SceneId(str(group_id)), group_id)

    def message(self, message_id: MessageId) -> MessageAPI:
        return MessageAPI(self._context, message_id)

    def friend_request(self, request_id: RequestId) -> FriendRequestAPI:
        return FriendRequestAPI(self._context, request_id)

    def group_request(self, request_id: RequestId) -> GroupRequestAPI:
        return GroupRequestAPI(self._context, request_id)

    def file(self, file_id: FileId) -> FileAPI:
        return FileAPI(self._context, file_id)

    async def raw(self, action: str, params: Mapping[str, JsonValue] | None = None) -> RawResult:
        return await self._context.execute(RawAction(action=action, params=dict(params or {})))

    @property
    def bot(self) -> BotAPI:
        return BotAPI(self._context)
