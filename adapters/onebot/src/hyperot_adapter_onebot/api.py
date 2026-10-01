from __future__ import annotations

from typing_extensions import override

from hyperot.v2.actions import (
    CookieInfo,
    CsrfTokenInfo,
    FileReference,
    FileUrl,
    MuteMemberAction,
    ReactMessageAction,
)
from hyperot.v2.api import BotAPI, ClientAPI, FileAPI, GroupAPI, GroupMemberAPI, MessageAPI, UserAPI
from hyperot.v2.common import CapabilityNotSupportedError, FileId, GroupId, MessageId, SceneId, SceneType, UserId

from .actions import (
    GetGroupFileUrlAction,
    GetPrivateFileUrlAction,
    GroupReactionAction,
    OneBotKickMemberAction,
    OneBotLeaveGroupAction,
    OneBotSetMemberTitleAction,
)


class OneBotUserAPI(UserAPI):
    async def send_like(self, times: int = 1) -> None:
        from hyperot.v2.actions import SendLikeAction

        await self._context.execute(SendLikeAction(user_id=self.user_id, times=times))


class OneBotGroupMemberAPI(GroupMemberAPI):
    @override
    async def kick(self, reject_add_request: bool = False) -> None:
        await self._context.execute(
            OneBotKickMemberAction(
                group_id=self.group_id,
                user_id=self.user_id,
                reject_add_request=reject_add_request,
            )
        )

    @override
    async def mute(self, duration: int = 1800) -> None:
        await self._context.execute(
            MuteMemberAction(
                group_id=self.group_id,
                user_id=self.user_id,
                duration=duration,
            )
        )

    @override
    async def set_card(self, card: str) -> None:
        from hyperot.v2.actions import SetMemberCardAction

        await self._context.execute(
            SetMemberCardAction(
                group_id=self.group_id,
                user_id=self.user_id,
                card=card,
            )
        )

    @override
    async def set_title(self, title: str, duration: int = -1) -> None:
        await self._context.execute(
            OneBotSetMemberTitleAction(
                group_id=self.group_id,
                user_id=self.user_id,
                title=title,
                duration=duration,
            )
        )


class OneBotGroupAPI(GroupAPI):
    @override
    def member(self, user_id: str | int) -> OneBotGroupMemberAPI:
        return OneBotGroupMemberAPI(self._context, self.group_id, UserId(str(user_id)))

    async def reaction(self, message_id: str | int, reaction: str) -> None:
        await self._context.execute(
            GroupReactionAction(
                group_id=self.group_id,
                message_id=MessageId(str(message_id)),
                reaction=reaction,
                enabled=True,
            )
        )

    @override
    async def leave(self, is_dismiss: bool = False) -> None:
        await self._context.execute(
            OneBotLeaveGroupAction(
                group_id=self.group_id,
                is_dismiss=is_dismiss,
            )
        )


class OneBotMessageAPI(MessageAPI):
    async def group_reaction(self, reaction: str) -> None:
        await self._context.execute(
            ReactMessageAction(
                message_id=self.message_id,
                reaction=reaction,
                enabled=True,
            )
        )


class OneBotFileAPI(FileAPI):
    @override
    async def info(self) -> FileReference:
        raise CapabilityNotSupportedError("OneBot has no generic file info endpoint")

    @override
    async def download(self) -> FileUrl:
        raise CapabilityNotSupportedError("OneBot has no generic file download endpoint")

    async def group_url(self, group_id: str | int) -> FileUrl:
        return await self._context.execute(
            GetGroupFileUrlAction(
                group_id=GroupId(str(group_id)),
                file_id=self.file_id,
            )
        )

    async def private_url(self, user_id: str | int, file_hash: str | None = None) -> FileUrl:
        return await self._context.execute(
            GetPrivateFileUrlAction(
                user_id=UserId(str(user_id)),
                file_id=self.file_id,
                file_hash=file_hash,
            )
        )


class OneBotBotAPI(BotAPI):
    async def cookies(self, domain: str) -> CookieInfo:
        from hyperot.v2.actions import GetCookieAction

        return await self._context.execute(GetCookieAction(domain=domain))

    async def csrf_token(self) -> CsrfTokenInfo:
        from hyperot.v2.actions import GetCsrfTokenAction

        return await self._context.execute(GetCsrfTokenAction())


class OneBotAPI(ClientAPI):
    @override
    def scene(self, scene_type: SceneType, scene_id: str | int):
        return super().scene(scene_type, scene_id)

    @override
    def user(self, user_id: str | int) -> OneBotUserAPI:
        return OneBotUserAPI(self._context, SceneType.USER, SceneId(str(user_id)), UserId(str(user_id)))

    @override
    def group(self, group_id: str | int) -> OneBotGroupAPI:
        return OneBotGroupAPI(self._context, SceneType.GROUP, SceneId(str(group_id)), GroupId(str(group_id)))

    @override
    def message(self, message_id: str | int) -> OneBotMessageAPI:
        return OneBotMessageAPI(self._context, MessageId(str(message_id)))

    @override
    def file(self, file_id: str | int) -> OneBotFileAPI:
        return OneBotFileAPI(self._context, FileId(str(file_id)))

    @override
    @property
    def bot(self) -> OneBotBotAPI:
        return OneBotBotAPI(self._context)
