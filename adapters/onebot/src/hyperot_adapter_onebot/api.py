from __future__ import annotations

from typing_extensions import override

from hyperot.v2.actions import CookieInfo, CsrfTokenInfo, FileUrl
from hyperot.v2.api import BotAPI, ClientAPI, FileAPI, GroupAPI, GroupMemberAPI, MessageAPI, UserAPI
from hyperot.v2.common import FileId, GroupId, MessageId, SceneId, SceneType, UserId

from .actions import (
    GetGroupFileUrlAction,
    GetPrivateFileUrlAction,
    GroupReactionAction,
)


class OneBotUserAPI(UserAPI):
    async def send_like(self, times: int = 1) -> None:
        from hyperot.v2.actions import SendLikeAction

        await self._context.execute(SendLikeAction(user_id=self.user_id, times=times))


class OneBotGroupMemberAPI(GroupMemberAPI):
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


class OneBotGroupAPI(GroupAPI):
    @override
    def member(self, user_id: UserId) -> OneBotGroupMemberAPI:
        return OneBotGroupMemberAPI(self._context, self.group_id, user_id)

    async def reaction(self, message_id: MessageId, reaction: str) -> None:
        await self._context.execute(
            GroupReactionAction(
                message_id=message_id,
                reaction=reaction,
                enabled=True,
            )
        )


class OneBotMessageAPI(MessageAPI):
    async def group_reaction(self, reaction: str) -> None:
        await self._context.execute(
            GroupReactionAction(
                message_id=self.message_id,
                reaction=reaction,
                enabled=True,
            )
        )


class OneBotFileAPI(FileAPI):
    async def group_url(self, group_id: GroupId) -> FileUrl:
        return await self._context.execute(
            GetGroupFileUrlAction(
                group_id=group_id,
                file_id=self.file_id,
            )
        )

    async def private_url(self, user_id: UserId, file_hash: str | None = None) -> FileUrl:
        return await self._context.execute(
            GetPrivateFileUrlAction(
                user_id=user_id,
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
    def scene(self, scene_type: SceneType, scene_id: SceneId):
        return super().scene(scene_type, scene_id)

    @override
    def user(self, user_id: UserId) -> OneBotUserAPI:
        return OneBotUserAPI(self._context, SceneType.USER, SceneId(str(user_id)), user_id)

    @override
    def group(self, group_id: GroupId) -> OneBotGroupAPI:
        return OneBotGroupAPI(self._context, SceneType.GROUP, SceneId(str(group_id)), group_id)

    @override
    def message(self, message_id: MessageId) -> OneBotMessageAPI:
        return OneBotMessageAPI(self._context, message_id)

    @override
    def file(self, file_id: FileId) -> OneBotFileAPI:
        return OneBotFileAPI(self._context, file_id)

    @override
    @property
    def bot(self) -> OneBotBotAPI:
        return OneBotBotAPI(self._context)
