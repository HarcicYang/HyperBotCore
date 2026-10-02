"""Action handlers.

Satori exposes one HTTP route per operation, named ``{resource}.{method}``, and returns
the resource itself instead of a wrapped envelope. This module registers a handler for
every V2 action the protocol can serve and leaves the rest unregistered, so calling an
unsupported capability raises ``CapabilityNotSupportedError`` before it ever reaches the
protocol end.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, JsonValue
from typing_extensions import override

from hyperot.v2.actions import (
    Action,
    ApproveFriendRequestAction,
    ApproveGroupRequestAction,
    BotProfile,
    BotStatus,
    DownloadFileAction,
    FetchMessageAction,
    FileUrl,
    FriendInfo,
    GetBotProfileAction,
    GetBotStatusAction,
    GetFriendListAction,
    GetGroupListAction,
    GetGroupMemberAction,
    GetGroupMemberListAction,
    GetGroupProfileAction,
    GetUserProfileAction,
    GroupMemberProfile,
    GroupProfile,
    KickMemberAction,
    MuteMemberAction,
    RawAction,
    RawResult,
    ReactMessageAction,
    RecallMessageAction,
    RejectFriendRequestAction,
    RejectGroupRequestAction,
    SendMessageAction,
    SendResult,
    SetGroupMuteAction,
    SetMemberRoleAction,
    UnmuteMemberAction,
    UserProfile,
)
from hyperot.v2.actions.formatting import format_text
from hyperot.v2.adapter import ActionRegistry
from hyperot.v2.common import ActionRejectedError, MemberRole, SceneType
from hyperot.v2.messages import Message

from .ids import (
    FRIEND_REQUEST,
    GUILD_MEMBER_REQUEST,
    GUILD_REQUEST,
    decode_message_id,
    decode_request_id,
    encode_message_id,
)
from .segments import SatoriSegmentCodec
from .transport import SatoriTransport

ResultT = TypeVar("ResultT")

#: Standard routes this adapter can call. Kept as data so the contract test can check the
#: adapter against the specification instead of against private handler names.
SATORI_ENDPOINTS = frozenset(
    {
        "guild.approve",
        "guild.get",
        "guild.list",
        "guild.member.approve",
        "guild.member.get",
        "guild.member.kick",
        "guild.member.list",
        "guild.member.mute",
        "guild.member.role.set",
        "guild.member.role.unset",
        "guild.role.list",
        "channel.get",
        "channel.list",
        "channel.mute",
        "friend.approve",
        "friend.list",
        "login.get",
        "message.create",
        "message.delete",
        "message.get",
        "message.list",
        "meta",
        "meta/webhook.create",
        "reaction.create",
        "reaction.delete",
        "upload.create",
        "user.channel.create",
        "user.get",
    }
)

#: channel.mute has no "forever" value and the V2 mute-all action carries no duration,
#: so a mute-all is sent as a month and lifted with duration 0.
GROUP_MUTE_DURATION_MS = 30 * 24 * 3600 * 1000

ROLE_KEYWORDS: dict[MemberRole, tuple[str, ...]] = {
    MemberRole.OWNER: ("owner", "群主", "创建者"),
    MemberRole.ADMIN: ("admin", "管理"),
    MemberRole.MEMBER: ("member", "成员"),
}


class ChannelInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    type: int = 0
    name: str = ""
    parent_id: str = ""


class RoleInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    id: str
    name: str = ""


class SatoriChannelListAction(Action[list[ChannelInfo]]):
    log_level: ClassVar[str] = "TRACE"
    guild_id: str

    @override
    def log_summary(self) -> str:
        return f"guild {format_text(self.guild_id)} channel list"


class SatoriGuildRoleListAction(Action[list[RoleInfo]]):
    log_level: ClassVar[str] = "TRACE"
    guild_id: str

    @override
    def log_summary(self) -> str:
        return f"guild {format_text(self.guild_id)} role list"


class SatoriSetGuildMemberRoleAction(Action[None]):
    guild_id: str
    user_id: str
    role_id: str
    enabled: bool = True

    @override
    def log_summary(self) -> str:
        action = "grant" if self.enabled else "revoke"
        return f"[guild] {format_text(self.guild_id)} {action} role {format_text(self.role_id)}"


class SatoriMessageListAction(Action[list[Message]]):
    log_level: ClassVar[str] = "TRACE"
    channel_id: str
    limit: int = 50

    @override
    def log_summary(self) -> str:
        return f"channel {format_text(self.channel_id)} message list"


class SatoriUploadFileAction(Action[dict[str, str]]):
    files: tuple[tuple[str, str], ...] = ()

    @override
    def log_summary(self) -> str:
        names = ", ".join(name for name, _ in self.files) or "<none>"
        return f"upload files ({names})"


class ChannelIndex:
    """Remembers which channel serves which guild and which user.

    Satori addresses messages by channel, while the V2 group scene addresses a guild and
    the user scene addresses a user, so sending needs the channel behind them. Events
    provide that pairing for free; anything else is learned from ``channel.list`` and
    ``user.channel.create``.
    """

    def __init__(self) -> None:
        self._guild_channels: dict[str, str] = {}
        self._user_channels: dict[str, str] = {}
        self._channels: set[str] = set()

    def remember(self, channel_id: str, guild_id: str | None = None) -> None:
        if not channel_id:
            return
        self._channels.add(channel_id)
        if guild_id:
            self._guild_channels[guild_id] = channel_id

    def remember_user_channel(self, user_id: str, channel_id: str) -> None:
        if user_id and channel_id:
            self._user_channels[user_id] = channel_id
            self._channels.add(channel_id)

    def channel_for_guild(self, guild_id: str) -> str | None:
        return self._guild_channels.get(guild_id)

    def channel_for_user(self, user_id: str) -> str | None:
        return self._user_channels.get(user_id)

    def is_channel(self, channel_id: str) -> bool:
        return channel_id in self._channels


class SatoriActions:
    def __init__(
        self,
        transport: SatoriTransport,
        codec: SatoriSegmentCodec,
        action_timeout: float,
        *,
        channel_index: ChannelIndex | None = None,
        online_provider: Callable[[], bool] | None = None,
        proxy_urls_provider: Callable[[], list[str]] | None = None,
    ) -> None:
        self.transport = transport
        self.codec = codec
        self.action_timeout = action_timeout
        self.channel_index = channel_index or ChannelIndex()
        self.online_provider = online_provider
        self.proxy_urls_provider = proxy_urls_provider

    def register_all(self, registry: ActionRegistry) -> None:
        registry.register(RawAction, self.raw)
        registry.register(SendMessageAction, self.send_message)
        registry.register(RecallMessageAction, self.recall_message)
        registry.register(FetchMessageAction, self.fetch_message)
        registry.register(SatoriMessageListAction, self.message_list)
        registry.register(SatoriChannelListAction, self.channel_list)
        registry.register(SatoriGuildRoleListAction, self.guild_role_list)
        registry.register(SatoriSetGuildMemberRoleAction, self.set_guild_member_role)
        registry.register(SatoriUploadFileAction, self.upload_file)
        registry.register(GetBotProfileAction, self.get_bot_profile)
        registry.register(GetBotStatusAction, self.get_bot_status)
        registry.register(GetUserProfileAction, self.get_user_profile)
        registry.register(GetFriendListAction, self.get_friend_list)
        registry.register(GetGroupProfileAction, self.get_group_profile)
        registry.register(GetGroupListAction, self.get_group_list)
        registry.register(GetGroupMemberAction, self.get_group_member)
        registry.register(GetGroupMemberListAction, self.get_group_member_list)
        registry.register(KickMemberAction, self.kick_member)
        registry.register(MuteMemberAction, self.mute_member)
        registry.register(UnmuteMemberAction, self.unmute_member)
        registry.register(SetMemberRoleAction, self.set_member_role)
        registry.register(SetGroupMuteAction, self.set_group_mute)
        registry.register(ReactMessageAction, self.react_message)
        registry.register(ApproveFriendRequestAction, self.approve_friend_request)
        registry.register(RejectFriendRequestAction, self.reject_friend_request)
        registry.register(ApproveGroupRequestAction, self.approve_group_request)
        registry.register(RejectGroupRequestAction, self.reject_group_request)
        registry.register(DownloadFileAction, self.download_file)

    # -- plumbing ---------------------------------------------------------------

    async def raw(self, action: RawAction) -> RawResult:
        # Standard routes and the internal proxy routes both live under /v1.
        return RawResult(data=await self._call(action.action, dict(action.params)))

    async def _call(self, route: str, params: dict[str, Any]) -> JsonValue:
        return await self.transport.call(route, params, self.action_timeout)

    async def _call_object(self, route: str, params: dict[str, Any]) -> dict[str, Any]:
        data = await self._call(route, params)
        return data if isinstance(data, dict) else {}

    async def _list_all(self, route: str, params: dict[str, Any]) -> list[JsonValue]:
        """Follow the ``next`` token of a paginated list until it runs out."""
        items: list[JsonValue] = []
        token: str | None = None
        seen: set[str] = set()
        while True:
            body = dict(params)
            if token:
                body["next"] = token
            data = await self._call_object(route, body)
            entries = data.get("data")
            if isinstance(entries, list):
                items.extend(entries)
            token = data.get("next")
            if not token or token in seen:
                return items
            seen.add(str(token))

    async def _channel_for_scene(self, scene_type: SceneType, scene_id: str) -> str:
        """Return the channel a scene addresses, learning it when it is not known."""
        if scene_type == SceneType.GUILD:
            self.channel_index.remember(scene_id)
            return scene_id
        if scene_type == SceneType.GROUP:
            channel_id = self.channel_index.channel_for_guild(scene_id)
            if channel_id is None:
                channel_id = await self._plain_channel_of_guild(scene_id)
            return channel_id
        if self.channel_index.is_channel(scene_id):
            # The scene already names a channel the adapter has seen.
            return scene_id
        channel_id = self.channel_index.channel_for_user(scene_id)
        if channel_id is not None:
            return channel_id
        channel = await self._call_object("user.channel.create", {"user_id": scene_id})
        channel_id = str(channel.get("id") or "")
        if not channel_id:
            raise ActionRejectedError(f"Satori created no private channel for user {scene_id}")
        self.channel_index.remember_user_channel(scene_id, channel_id)
        return channel_id

    async def _plain_channel_of_guild(self, guild_id: str) -> str:
        """Pick the text channel of a guild that exposes only one."""
        channels = await self.channel_list(SatoriChannelListAction(guild_id=guild_id))
        for channel in channels:
            if channel.type == 0 and channel.id:
                return channel.id
        raise ActionRejectedError(f"Satori guild {guild_id} exposes no text channel")

    # -- messages ---------------------------------------------------------------

    async def send_message(self, action: SendMessageAction) -> SendResult:
        channel_id = await self._channel_for_scene(action.scene_type, action.scene_id)
        data = await self._call(
            "message.create",
            {"channel_id": channel_id, "content": self.codec.encode_message(action.message)},
        )
        # message.create returns the messages it sent, one per content message.
        message_id = ""
        if isinstance(data, list) and data and isinstance(data[0], dict):
            message_id = str(data[0].get("id") or "")
        elif isinstance(data, dict):
            message_id = str(data.get("id") or "")
        return SendResult(message_id=encode_message_id(channel_id, message_id))

    async def recall_message(self, action: RecallMessageAction) -> None:
        channel_id, message_id = _split_message_id(action.message_id)
        await self._call("message.delete", {"channel_id": channel_id, "message_id": message_id})

    async def fetch_message(self, action: FetchMessageAction) -> Message:
        channel_id, message_id = _split_message_id(action.message_id)
        data = await self._call_object("message.get", {"channel_id": channel_id, "message_id": message_id})
        return self.codec.decode_message(data.get("content"))

    async def message_list(self, action: SatoriMessageListAction) -> list[Message]:
        data = await self._call_object(
            "message.list",
            {"channel_id": action.channel_id, "direction": "before", "limit": action.limit},
        )
        entries = data.get("data")
        if not isinstance(entries, list):
            return []
        return [self.codec.decode_message(entry.get("content")) for entry in entries if isinstance(entry, dict)]

    async def react_message(self, action: ReactMessageAction) -> None:
        channel_id, message_id = _split_message_id(action.message_id)
        route = "reaction.create" if action.enabled else "reaction.delete"
        await self._call(route, {"channel_id": channel_id, "message_id": message_id, "emoji_id": action.reaction})

    # -- queries ----------------------------------------------------------------

    async def get_bot_profile(self, _action: GetBotProfileAction) -> BotProfile:
        data = await self._call_object("login.get", {})
        user = data.get("user") or {}
        return BotProfile(
            user_id=str(user.get("id") or ""),
            display_name=str(user.get("nick") or user.get("name") or ""),
        )

    async def get_bot_status(self, _action: GetBotStatusAction) -> BotStatus:
        # Satori has no status API; the login the SDK reported carries it.
        online = self.online_provider() if self.online_provider is not None else True
        return BotStatus(online=online)

    async def get_user_profile(self, action: GetUserProfileAction) -> UserProfile:
        data = await self._call_object("user.get", {"user_id": action.user_id})
        return UserProfile(
            user_id=str(data.get("id") or action.user_id),
            display_name=str(data.get("nick") or data.get("name") or ""),
        )

    async def get_friend_list(self, _action: GetFriendListAction) -> list[FriendInfo]:
        friends: list[FriendInfo] = []
        for entry in await self._list_all("friend.list", {}):
            if not isinstance(entry, dict):
                continue
            user = _object(entry.get("user"))
            friends.append(
                FriendInfo(
                    user_id=str(user.get("id") or ""),
                    display_name=str(entry.get("nick") or user.get("nick") or user.get("name") or ""),
                )
            )
        return friends

    async def get_group_profile(self, action: GetGroupProfileAction) -> GroupProfile:
        data = await self._call_object("guild.get", {"guild_id": action.group_id})
        return GroupProfile(group_id=str(data.get("id") or action.group_id), name=str(data.get("name") or ""))

    async def get_group_list(self, _action: GetGroupListAction) -> list[GroupProfile]:
        return [
            GroupProfile(group_id=str(entry.get("id") or ""), name=str(entry.get("name") or ""))
            for entry in await self._list_all("guild.list", {})
            if isinstance(entry, dict)
        ]

    async def get_group_member(self, action: GetGroupMemberAction) -> GroupMemberProfile:
        data = await self._call_object(
            "guild.member.get",
            {"guild_id": action.group_id, "user_id": action.user_id},
        )
        return _member_profile(data, action.group_id, action.user_id)

    async def get_group_member_list(self, action: GetGroupMemberListAction) -> list[GroupMemberProfile]:
        return [
            _member_profile(entry, action.group_id, "")
            for entry in await self._list_all("guild.member.list", {"guild_id": action.group_id})
            if isinstance(entry, dict)
        ]

    async def channel_list(self, action: SatoriChannelListAction) -> list[ChannelInfo]:
        channels: list[ChannelInfo] = []
        for entry in await self._list_all("channel.list", {"guild_id": action.guild_id}):
            if not isinstance(entry, dict):
                continue
            channels.append(
                ChannelInfo(
                    id=str(entry.get("id") or ""),
                    type=_count(entry.get("type")),
                    name=str(entry.get("name") or ""),
                    parent_id=str(entry.get("parent_id") or ""),
                )
            )
        for channel in channels:
            self.channel_index.remember(channel.id, action.guild_id)
        return channels

    async def guild_role_list(self, action: SatoriGuildRoleListAction) -> list[RoleInfo]:
        return [
            RoleInfo(id=str(entry.get("id") or ""), name=str(entry.get("name") or ""))
            for entry in await self._list_all("guild.role.list", {"guild_id": action.guild_id})
            if isinstance(entry, dict)
        ]

    # -- moderation -------------------------------------------------------------

    async def kick_member(self, action: KickMemberAction) -> None:
        await self._call(
            "guild.member.kick",
            {"guild_id": action.group_id, "user_id": action.user_id, "permanent": False},
        )

    async def mute_member(self, action: MuteMemberAction) -> None:
        await self._mute(action.group_id, action.user_id, action.duration)

    async def unmute_member(self, action: UnmuteMemberAction) -> None:
        await self._mute(action.group_id, action.user_id, 0)

    async def _mute(self, group_id: str, user_id: str, seconds: int) -> None:
        # Satori mute durations are milliseconds while the V2 action counts seconds.
        await self._call(
            "guild.member.mute",
            {"guild_id": group_id, "user_id": user_id, "duration": max(seconds, 0) * 1000},
        )

    async def set_member_role(self, action: SetMemberRoleAction) -> None:
        roles = await self.guild_role_list(SatoriGuildRoleListAction(guild_id=action.group_id))
        if action.role == MemberRole.MEMBER:
            for role in roles:
                await self.set_guild_member_role(
                    SatoriSetGuildMemberRoleAction(
                        guild_id=action.group_id,
                        user_id=action.user_id,
                        role_id=role.id,
                        enabled=False,
                    )
                )
            return
        role = _match_role(roles, action.role)
        if role is None:
            raise ActionRejectedError(
                f"Satori guild {action.group_id} has no role matching {action.role.value};"
                " use api.group().member().set_role_id() with a role from guild.role.list"
            )
        await self.set_guild_member_role(
            SatoriSetGuildMemberRoleAction(
                guild_id=action.group_id,
                user_id=action.user_id,
                role_id=role.id,
                enabled=True,
            )
        )

    async def set_guild_member_role(self, action: SatoriSetGuildMemberRoleAction) -> None:
        route = "guild.member.role.set" if action.enabled else "guild.member.role.unset"
        await self._call(
            route,
            {"guild_id": action.guild_id, "user_id": action.user_id, "role_id": action.role_id},
        )

    async def set_group_mute(self, action: SetGroupMuteAction) -> None:
        channel_id = await self._channel_for_scene(SceneType.GROUP, action.group_id)
        await self._call(
            "channel.mute",
            {"channel_id": channel_id, "duration": GROUP_MUTE_DURATION_MS if action.muted else 0},
        )

    # -- requests ---------------------------------------------------------------

    async def approve_friend_request(self, action: ApproveFriendRequestAction) -> None:
        kind, _guild_id, message_id = decode_request_id(action.request_id)
        await self._approve(kind, message_id, approve=True)

    async def reject_friend_request(self, action: RejectFriendRequestAction) -> None:
        kind, _guild_id, message_id = decode_request_id(action.request_id)
        await self._approve(kind, message_id, approve=False, comment=action.reason)

    async def approve_group_request(self, action: ApproveGroupRequestAction) -> None:
        kind, guild_id, message_id = decode_request_id(action.request_id)
        await self._approve(kind, message_id, approve=True, guild_id=guild_id)

    async def reject_group_request(self, action: RejectGroupRequestAction) -> None:
        kind, guild_id, message_id = decode_request_id(action.request_id)
        await self._approve(kind, message_id, approve=False, comment=action.reason, guild_id=guild_id)

    async def _approve(
        self,
        kind: str,
        message_id: str,
        *,
        approve: bool,
        comment: str | None = None,
        guild_id: str = "",
    ) -> None:
        params: dict[str, Any] = {"message_id": message_id}
        if kind == FRIEND_REQUEST:
            route = "friend.approve"
        elif kind == GUILD_MEMBER_REQUEST:
            route = "guild.member.approve"
            params["guild_id"] = guild_id
        elif kind == GUILD_REQUEST:
            route = "guild.approve"
            params["guild_id"] = guild_id
        else:
            raise ActionRejectedError(f"unknown Satori request kind: {kind}")
        params["approve"] = approve
        if comment:
            params["comment"] = comment
        await self._call(route, params)

    # -- resources --------------------------------------------------------------

    async def download_file(self, action: DownloadFileAction) -> FileUrl:
        return FileUrl(url=self._resource_url(str(action.file_id)))

    def _resource_url(self, source: str) -> str:
        """Return a URL the application can fetch directly.

        Internal links, and URLs the SDK listed in ``proxy_urls``, go through the proxy
        route; a plain public URL is already usable as it is.
        """
        builder = getattr(self.transport, "proxy_url", None)
        if self.proxy_urls_provider is not None:
            proxy_urls = self.proxy_urls_provider()
        else:
            listed = getattr(self.transport, "proxy_urls", None)
            proxy_urls = listed() if listed is not None else []
        if source.startswith("internal:") or any(source.startswith(prefix) for prefix in proxy_urls if prefix):
            return builder(source) if builder is not None else source
        return source

    async def upload_file(self, action: SatoriUploadFileAction) -> dict[str, str]:
        files: list[tuple[str, bytes, str, str]] = []
        for name, path in action.files:
            data, content_type, filename = await _read_file(path)
            files.append((name, data, content_type, filename))
        return await self.transport.upload(files, self.action_timeout)


async def _read_file(path: str) -> tuple[bytes, str, str]:
    if path.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as client:
            response = await client.get(path)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/octet-stream")
            return response.content, content_type.split(";")[0], Path(path).name or "file"
    file = Path(path)
    content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    return file.read_bytes(), content_type, file.name


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _split_message_id(message_id: str) -> tuple[str, str]:
    channel_id, inner = decode_message_id(message_id)
    if not channel_id:
        raise ActionRejectedError(f"Satori needs the channel of message {message_id} to act on it")
    return channel_id, inner


def _member_profile(data: dict[str, Any], group_id: str, user_id: str) -> GroupMemberProfile:
    user = data.get("user") or {}
    roles = data.get("roles")
    card = str(data.get("nick") or "") or None
    return GroupMemberProfile(
        group_id=group_id,
        user_id=str(user.get("id") or user_id),
        display_name=str(user.get("nick") or user.get("name") or ""),
        card=card,
        role=_role_from_roles(roles),
    )


def _role_from_roles(roles: object) -> MemberRole | None:
    if not isinstance(roles, list):
        return None
    names = [str((role or {}).get("name", "")).lower() for role in roles if isinstance(role, dict)]
    if not names:
        return None
    if any("owner" in name or "群主" in name for name in names):
        return MemberRole.OWNER
    if any("admin" in name or "管理" in name for name in names):
        return MemberRole.ADMIN
    return MemberRole.MEMBER


def _match_role(roles: list[RoleInfo], role: MemberRole) -> RoleInfo | None:
    for keyword in ROLE_KEYWORDS.get(role, ()):
        for candidate in roles:
            if keyword in candidate.name.lower():
                return candidate
    return None


__all__ = [
    "GROUP_MUTE_DURATION_MS",
    "SATORI_ENDPOINTS",
    "ChannelIndex",
    "ChannelInfo",
    "RoleInfo",
    "SatoriActions",
    "SatoriChannelListAction",
    "SatoriGuildRoleListAction",
    "SatoriMessageListAction",
    "SatoriSetGuildMemberRoleAction",
    "SatoriUploadFileAction",
]
