"""The extended API surface of the Satori adapter.

The generic scene, group, member, message and file APIs come from the V2 core and work
as they are. This module adds the calls that only make sense for Satori: channels,
roles, message history and file upload.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import override

from hyperot.v2.api import ClientAPI, FileAPI, GroupAPI, GroupMemberAPI, SceneAPI
from hyperot.v2.common import SceneType
from hyperot.v2.messages import Message

from .actions import (
    ChannelInfo,
    RoleInfo,
    SatoriChannelListAction,
    SatoriGuildRoleListAction,
    SatoriMessageListAction,
    SatoriSetGuildMemberRoleAction,
    SatoriUploadFileAction,
)


@dataclass(frozen=True, slots=True)
class SatoriChannelAPI(SceneAPI):
    """Addresses a single channel of a guild."""

    channel_id: str

    async def messages(self, limit: int = 50) -> list[Message]:
        return await self._context.execute(
            SatoriMessageListAction(channel_id=self.channel_id, limit=limit)
        )


@dataclass(frozen=True, slots=True)
class SatoriGroupMemberAPI(GroupMemberAPI):
    async def set_role_id(self, role_id: str | int, enabled: bool = True) -> None:
        await self._context.execute(
            SatoriSetGuildMemberRoleAction(
                guild_id=self.group_id,
                user_id=self.user_id,
                role_id=str(role_id),
                enabled=enabled,
            )
        )


@dataclass(frozen=True, slots=True)
class SatoriGroupAPI(GroupAPI):
    @override
    def member(self, user_id: str | int) -> SatoriGroupMemberAPI:
        return SatoriGroupMemberAPI(self._context, self.group_id, str(user_id))

    def channel(self, channel_id: str | int) -> SatoriChannelAPI:
        return SatoriChannelAPI(self._context, SceneType.GUILD, str(channel_id), str(channel_id))

    async def channels(self) -> list[ChannelInfo]:
        return await self._context.execute(SatoriChannelListAction(guild_id=self.group_id))

    async def roles(self) -> list[RoleInfo]:
        return await self._context.execute(SatoriGuildRoleListAction(guild_id=self.group_id))


class SatoriFileAPI(FileAPI):
    """Files the SDK points at with a URL or an internal: link."""


class SatoriAPI(ClientAPI):
    def channel(self, channel_id: str | int) -> SatoriChannelAPI:
        return SatoriChannelAPI(self._context, SceneType.GUILD, str(channel_id), str(channel_id))

    @override
    def group(self, group_id: str | int) -> SatoriGroupAPI:
        return SatoriGroupAPI(self._context, SceneType.GROUP, str(group_id), str(group_id))

    @override
    def file(self, file_id: str | int) -> SatoriFileAPI:
        return SatoriFileAPI(self._context, str(file_id))

    async def upload(self, files: dict[str, str]) -> dict[str, str]:
        """Upload local files or URLs and return the URLs to use in message content."""
        return await self._context.execute(
            SatoriUploadFileAction(files=tuple((name, path) for name, path in files.items()))
        )


__all__ = [
    "SatoriAPI",
    "SatoriChannelAPI",
    "SatoriFileAPI",
    "SatoriGroupAPI",
    "SatoriGroupMemberAPI",
]
