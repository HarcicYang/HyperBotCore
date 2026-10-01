from __future__ import annotations

from typing import Any

from typing_extensions import override

from hyperot.v2.actions import (
    CookieInfo,
    CsrfTokenInfo,
    FileReference,
    FileUrl,
    GetCookieAction,
    GetCsrfTokenAction,
    SendLikeAction,
)
from hyperot.v2.api import (
    BotAPI,
    ClientAPI,
    FileAPI,
    GroupAPI,
    GroupMemberAPI,
    UserAPI,
)
from hyperot.v2.common import SceneType

from .actions import (
    AcceptGroupInvitationAction,
    GetGroupFilesAction,
    GetGroupFileUrlAction,
    GetPrivateFileUrlAction,
    GroupReactionAction,
    MilkyKickMemberAction,
    RejectGroupInvitationAction,
    UploadGroupFileAction,
)


class MilkyInvitationAPI:
    def __init__(self, context: Any, request_id: str) -> None:
        self._context = context
        self.request_id = request_id

    async def accept(self) -> None:
        await self._context.execute(AcceptGroupInvitationAction(request_id=self.request_id))

    async def reject(self, reason: str | None = None) -> None:
        await self._context.execute(RejectGroupInvitationAction(request_id=self.request_id, reason=reason))


class MilkyUserAPI(UserAPI):
    async def send_like(self, count: int = 1) -> None:
        await self._context.execute(SendLikeAction(user_id=self.user_id, times=count))


class MilkyGroupMemberAPI(GroupMemberAPI):
    @override
    async def kick(self, reject_add_request: bool = False) -> None:
        await self._context.execute(
            MilkyKickMemberAction(
                group_id=self.group_id,
                user_id=self.user_id,
                reject_add_request=reject_add_request,
            )
        )

    @override
    async def mute(self, duration: int = 1800) -> None:
        await super().mute(duration)


class MilkyGroupAPI(GroupAPI):
    @override
    def member(self, user_id: str | int) -> MilkyGroupMemberAPI:
        return MilkyGroupMemberAPI(self._context, self.group_id, str(user_id))

    async def reaction(self, message_id: str | int, reaction: str) -> None:
        await self._context.execute(
            GroupReactionAction(
                group_id=self.group_id,
                message_id=str(message_id),
                reaction=reaction,
                enabled=True,
            )
        )

    async def files(self, folder_id: str = "/") -> list[FileReference]:
        return await self._context.execute(GetGroupFilesAction(group_id=self.group_id, parent_folder_id=folder_id))

    async def upload_file(self, file: str, name: str | None = None, folder: str | None = None) -> None:
        await self._context.execute(UploadGroupFileAction(group_id=self.group_id, file=file, name=name, folder=folder))


class MilkyFileAPI(FileAPI):
    async def group_url(self, group_id: str | int) -> FileUrl:
        return await self._context.execute(GetGroupFileUrlAction(group_id=str(group_id), file_id=self.file_id))

    async def private_url(self, user_id: str | int, file_hash: str | None = None) -> FileUrl:
        return await self._context.execute(
            GetPrivateFileUrlAction(user_id=str(user_id), file_id=self.file_id, file_hash=file_hash)
        )


class MilkyBotAPI(BotAPI):
    async def cookies(self, domain: str) -> CookieInfo:
        return await self._context.execute(GetCookieAction(domain=domain))

    async def csrf_token(self) -> CsrfTokenInfo:
        return await self._context.execute(GetCsrfTokenAction())


class MilkyAPI(ClientAPI):
    def invitation(self, request_id: str | int) -> MilkyInvitationAPI:
        return MilkyInvitationAPI(self._context, str(request_id))

    @override
    def user(self, user_id: str | int) -> MilkyUserAPI:
        return MilkyUserAPI(self._context, SceneType.USER, str(user_id), str(user_id))

    @override
    def group(self, group_id: str | int) -> MilkyGroupAPI:
        return MilkyGroupAPI(self._context, SceneType.GROUP, str(group_id), str(group_id))

    @override
    def file(self, file_id: str | int) -> MilkyFileAPI:
        return MilkyFileAPI(self._context, str(file_id))

    @override
    @property
    def bot(self) -> MilkyBotAPI:
        return MilkyBotAPI(self._context)


__all__ = [
    "MilkyAPI",
    "MilkyBotAPI",
    "MilkyFileAPI",
    "MilkyGroupAPI",
    "MilkyGroupMemberAPI",
    "MilkyInvitationAPI",
    "MilkyUserAPI",
]
