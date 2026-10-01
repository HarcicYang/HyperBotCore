from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar, Protocol, TypeVar

from pydantic import JsonValue
from typing_extensions import override

from hyperot.v2.actions import (
    Action,
    ApproveFriendRequestAction,
    ApproveGroupRequestAction,
    BotProfile,
    BotStatus,
    CookieInfo,
    CsrfTokenInfo,
    FetchMessageAction,
    FileUrl,
    FriendInfo,
    GetBotProfileAction,
    GetBotStatusAction,
    GetCookieAction,
    GetCsrfTokenAction,
    GetFriendListAction,
    GetGroupListAction,
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
    SendLikeAction,
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
from hyperot.v2.actions.formatting import (
    format_message,
    format_source,
    format_text,
)
from hyperot.v2.adapter import ActionRegistry
from hyperot.v2.common import (
    ActionRejectedError,
    MemberRole,
    SceneType,
)
from hyperot.v2.messages import Message

from .segments import OneBotSegmentCodec

ResultT = TypeVar("ResultT")

ONEBOT_ENDPOINTS = frozenset(
    {
        "send_msg",
        "send_private_msg",
        "send_group_msg",
        "delete_msg",
        "get_msg",
        "get_forward_msg",
        "send_like",
        "send_poke",
        "set_group_kick",
        "set_group_ban",
        "set_group_whole_ban",
        "set_group_admin",
        "set_group_card",
        "set_group_name",
        "set_group_leave",
        "set_group_special_title",
        "set_friend_add_request",
        "set_group_add_request",
        "get_login_info",
        "get_stranger_info",
        "get_friend_list",
        "get_group_info",
        "get_group_list",
        "get_group_member_info",
        "get_group_member_list",
        "get_status",
        "get_version_info",
        "get_cookies",
        "get_csrf_token",
        "group_reaction",
        "upload_group_file",
        "upload_private_file",
        "get_group_file_url",
        "get_private_file_url",
    }
)


class ActionTransport(Protocol):
    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]: ...


MessageGroupLookup = Callable[[str], str | None]
MessageGroupRemember = Callable[[str, str], None]
RequestSubtypeLookup = Callable[[str], str | None]
FileContextLookup = Callable[[str], dict[str, JsonValue] | None]


class OneBotKickMemberAction(KickMemberAction):
    reject_add_request: bool = False


class OneBotSetMemberTitleAction(SetMemberTitleAction):
    duration: int = -1


class OneBotLeaveGroupAction(LeaveGroupAction):
    is_dismiss: bool = False


class SendPrivateMessageAction(Action[SendResult]):
    user_id: str
    message: Message

    @override
    def log_summary(self) -> str:
        return f"[user] {format_text(str(self.user_id))} send: {format_message(self.message)}"


class SendGroupMessageAction(Action[SendResult]):
    group_id: str
    message: Message

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} send: {format_message(self.message)}"


class GetForwardMessageAction(Action[Message]):
    log_level: ClassVar[str] = "TRACE"
    forward_id: str

    @override
    def log_summary(self) -> str:
        return f"fetch forward {format_text(self.forward_id)}"


class GroupReactionAction(Action[None]):
    group_id: str
    message_id: str
    reaction: str
    enabled: bool = True

    @override
    def log_summary(self) -> str:
        action = "react" if self.enabled else "unreact"
        return f"{action} message {format_text(str(self.message_id))} with {format_text(self.reaction)}"


class UploadGroupFileAction(Action[None]):
    group_id: str
    file: str
    name: str | None = None
    folder: str | None = None

    @override
    def log_summary(self) -> str:
        name = self.name or format_source(self.file)
        folder = f" folder={format_text(self.folder)}" if self.folder else ""
        return f"[group] {format_text(str(self.group_id))} upload file {name}{folder}"


class UploadPrivateFileAction(Action[None]):
    user_id: str
    file: str
    name: str | None = None

    @override
    def log_summary(self) -> str:
        name = self.name or format_source(self.file)
        return f"[user] {format_text(str(self.user_id))} upload file {name}"


class GetGroupFileUrlAction(Action[FileUrl]):
    log_level: ClassVar[str] = "TRACE"
    group_id: str
    file_id: str

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} file {format_text(str(self.file_id))} url"


class GetPrivateFileUrlAction(Action[FileUrl]):
    log_level: ClassVar[str] = "TRACE"
    user_id: str
    file_id: str
    file_hash: str | None = None

    @override
    def log_summary(self) -> str:
        return f"[user] {format_text(str(self.user_id))} file {format_text(str(self.file_id))} url"


class OneBotActions:
    def __init__(
        self,
        transport: ActionTransport,
        codec: OneBotSegmentCodec,
        action_timeout: float,
        *,
        message_group_lookup: MessageGroupLookup | None = None,
        message_group_remember: MessageGroupRemember | None = None,
        request_subtype_lookup: RequestSubtypeLookup | None = None,
        file_context_lookup: FileContextLookup | None = None,
    ) -> None:
        self.transport = transport
        self.codec = codec
        self.action_timeout = action_timeout
        self.message_group_lookup = message_group_lookup
        self.message_group_remember = message_group_remember
        self.request_subtype_lookup = request_subtype_lookup
        self.file_context_lookup = file_context_lookup

    def register_all(self, registry: ActionRegistry) -> None:
        registry.register(RawAction, self.raw)
        registry.register(SendMessageAction, self.send_message)
        registry.register(SendPrivateMessageAction, self.send_private_message)
        registry.register(SendGroupMessageAction, self.send_group_message)
        registry.register(RecallMessageAction, self.recall_message)
        registry.register(FetchMessageAction, self.fetch_message)
        registry.register(GetForwardMessageAction, self.get_forward_message)
        registry.register(GetBotProfileAction, self.get_bot_profile)
        registry.register(GetBotStatusAction, self.get_bot_status)
        registry.register(GetVersionAction, self.get_version)
        registry.register(GetUserProfileAction, self.get_user_profile)
        registry.register(GetFriendListAction, self.get_friend_list)
        registry.register(GetGroupProfileAction, self.get_group_profile)
        registry.register(GetGroupListAction, self.get_group_list)
        registry.register(GetGroupMemberAction, self.get_group_member)
        registry.register(GetGroupMemberListAction, self.get_group_member_list)
        registry.register(KickMemberAction, self.kick_member)
        registry.register(OneBotKickMemberAction, self.kick_member)
        registry.register(MuteMemberAction, self.mute_member)
        registry.register(UnmuteMemberAction, self.unmute_member)
        registry.register(SetMemberRoleAction, self.set_member_role)
        registry.register(SetMemberTitleAction, self.set_member_title)
        registry.register(OneBotSetMemberTitleAction, self.set_member_title)
        registry.register(SetMemberCardAction, self.set_member_card)
        registry.register(SetGroupNameAction, self.set_group_name)
        registry.register(SetGroupMuteAction, self.set_group_mute)
        registry.register(LeaveGroupAction, self.leave_group)
        registry.register(OneBotLeaveGroupAction, self.leave_group)
        registry.register(ReactMessageAction, self.react_message)
        registry.register(SetEssenceAction, self.set_essence)
        registry.register(PokeAction, self.poke)
        registry.register(SendLikeAction, self.send_like)
        registry.register(GetCookieAction, self.get_cookie)
        registry.register(GetCsrfTokenAction, self.get_csrf_token)
        registry.register(ApproveFriendRequestAction, self.approve_friend_request)
        registry.register(RejectFriendRequestAction, self.reject_friend_request)
        registry.register(ApproveGroupRequestAction, self.approve_group_request)
        registry.register(RejectGroupRequestAction, self.reject_group_request)
        registry.register(UploadGroupFileAction, self.upload_group_file)
        registry.register(UploadPrivateFileAction, self.upload_private_file)
        registry.register(GetGroupFileUrlAction, self.get_group_file_url)
        registry.register(GetPrivateFileUrlAction, self.get_private_file_url)
        registry.register(GroupReactionAction, self.group_reaction)

    async def raw(self, action: RawAction) -> RawResult:
        data = await self._call_raw(action.action, dict(action.params))
        return RawResult(data=data)

    async def _call_raw(self, endpoint: str, params: dict[str, Any]) -> JsonValue:
        response = await self.transport.call(endpoint, params, self.action_timeout)
        status = response.get("status")
        retcode = int(response.get("retcode", 0))
        if status not in {None, "ok", "async"} or retcode not in {0, 1}:
            raise ActionRejectedError(f"{endpoint} failed with retcode={retcode}: {response.get('message', '')}")
        return response.get("data")

    async def _call(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        data = await self._call_raw(endpoint, params)
        if data is None:
            return {}
        if not isinstance(data, dict):
            return {"data": data}
        return data

    async def send_message(self, action: SendMessageAction) -> SendResult:
        params: dict[str, Any] = {"message": self.codec.encode_message(action.message)}
        if action.scene_type == SceneType.GROUP:
            params["group_id"] = str(action.scene_id)
        else:
            params["user_id"] = str(action.scene_id)
        data = await self._call("send_msg", params)
        message_id = str(data["message_id"])
        if action.scene_type == SceneType.GROUP and self.message_group_remember is not None:
            self.message_group_remember(message_id, str(action.scene_id))
        return SendResult(message_id=message_id)

    async def send_private_message(self, action: SendPrivateMessageAction) -> SendResult:
        data = await self._call(
            "send_private_msg",
            {"user_id": str(action.user_id), "message": self.codec.encode_message(action.message)},
        )
        return SendResult(message_id=str(data["message_id"]))

    async def send_group_message(self, action: SendGroupMessageAction) -> SendResult:
        data = await self._call(
            "send_group_msg",
            {"group_id": str(action.group_id), "message": self.codec.encode_message(action.message)},
        )
        message_id = str(data["message_id"])
        if self.message_group_remember is not None:
            self.message_group_remember(message_id, action.group_id)
        return SendResult(message_id=message_id)

    async def recall_message(self, action: RecallMessageAction) -> None:
        await self._call("delete_msg", {"message_id": str(action.message_id)})

    async def fetch_message(self, action: FetchMessageAction) -> Message:
        data = await self._call("get_msg", {"message_id": str(action.message_id)})
        return self.codec.decode_message(data.get("message", []))

    async def get_forward_message(self, action: GetForwardMessageAction) -> Message:
        data = await self._call("get_forward_msg", {"id": action.forward_id})
        nodes = []
        for node in data.get("message", []):
            node_data = node.get("data", node)
            nodes.append(
                {
                    "type": "node",
                    "data": {
                        "user_id": node_data.get("user_id", ""),
                        "nickname": node_data.get("nickname", ""),
                        "content": node_data.get("content", []),
                    },
                }
            )
        return self.codec.decode_message(nodes)

    async def get_bot_profile(self, _action: GetBotProfileAction) -> BotProfile:
        data = await self._call("get_login_info", {})
        return BotProfile(
            user_id=str(data.get("user_id", 0)),
            display_name=str(data.get("nickname", "")),
        )

    async def get_bot_status(self, _action: GetBotStatusAction) -> BotStatus:
        data = await self._call("get_status", {})
        return BotStatus(
            online=bool(data.get("online", True)),
            good=bool(data.get("good", True)),
            app_good=bool(data.get("app_good", True)),
            memory=int(data.get("memory", 0)),
        )

    async def get_version(self, _action: GetVersionAction) -> VersionInfo:
        data = await self._call("get_version_info", {})
        return VersionInfo(
            app_name=str(data.get("app_name", "")),
            app_version=str(data.get("app_version", "")),
            protocol_version=str(data.get("protocol_version", "")),
        )

    async def get_user_profile(self, action: GetUserProfileAction) -> UserProfile:
        data = await self._call("get_stranger_info", {"user_id": str(action.user_id)})
        return UserProfile(
            user_id=str(data.get("user_id", action.user_id)),
            display_name=str(data.get("nickname", "")),
            sex=str(data.get("sex", "")),
            age=int(data.get("age", 0)),
        )

    async def get_friend_list(self, _action: GetFriendListAction) -> list[FriendInfo]:
        data = await self._call("get_friend_list", {})
        items = data.get("data", data) if "data" in data else data
        if isinstance(items, dict):
            items = items.get("list", [])
        return [
            FriendInfo(
                user_id=str(item.get("user_id", 0)),
                display_name=str(item.get("nickname", "")),
            )
            for item in items
        ]

    async def get_group_profile(self, action: GetGroupProfileAction) -> GroupProfile:
        data = await self._call("get_group_info", {"group_id": str(action.group_id)})
        return GroupProfile(
            group_id=str(data.get("group_id", action.group_id)),
            name=str(data.get("group_name", "")),
            member_count=int(data.get("member_count", 0)),
            max_member_count=int(data.get("max_member_count", 0)),
        )

    async def get_group_list(self, _action: GetGroupListAction) -> list[GroupProfile]:
        data = await self._call("get_group_list", {})
        items = data.get("data", data) if "data" in data else data
        if isinstance(items, dict):
            items = items.get("list", [])
        return [
            GroupProfile(
                group_id=str(item.get("group_id", 0)),
                name=str(item.get("group_name", "")),
                member_count=int(item.get("member_count", 0)),
                max_member_count=int(item.get("max_member_count", 0)),
            )
            for item in items
        ]

    async def get_group_member(self, action: GetGroupMemberAction) -> GroupMemberProfile:
        data = await self._call(
            "get_group_member_info",
            {"group_id": str(action.group_id), "user_id": str(action.user_id)},
        )
        return GroupMemberProfile(
            group_id=str(data.get("group_id", action.group_id)),
            user_id=str(data.get("user_id", action.user_id)),
            display_name=str(data.get("nickname", "")),
            card=str(data.get("card", "")),
            role=_member_role(data.get("role")),
        )

    async def get_group_member_list(self, action: GetGroupMemberListAction) -> list[GroupMemberProfile]:
        data = await self._call("get_group_member_list", {"group_id": str(action.group_id)})
        items = data.get("data", data) if "data" in data else data
        if isinstance(items, dict):
            items = items.get("list", [])
        return [
            GroupMemberProfile(
                group_id=str(item.get("group_id", action.group_id)),
                user_id=str(item.get("user_id", 0)),
                display_name=str(item.get("nickname", "")),
                card=str(item.get("card", "")),
                role=_member_role(item.get("role")),
            )
            for item in items
        ]

    async def kick_member(self, action: KickMemberAction) -> None:
        params: dict[str, Any] = {"group_id": str(action.group_id), "user_id": str(action.user_id)}
        if isinstance(action, OneBotKickMemberAction):
            params["reject_add_request"] = action.reject_add_request
        await self._call("set_group_kick", params)

    async def mute_member(self, action: MuteMemberAction) -> None:
        await self._call(
            "set_group_ban",
            {"group_id": str(action.group_id), "user_id": str(action.user_id), "duration": action.duration},
        )

    async def unmute_member(self, action: UnmuteMemberAction) -> None:
        await self._call(
            "set_group_ban",
            {"group_id": str(action.group_id), "user_id": str(action.user_id), "duration": 0},
        )

    async def set_member_role(self, action: SetMemberRoleAction) -> None:
        await self._call(
            "set_group_admin",
            {
                "group_id": str(action.group_id),
                "user_id": str(action.user_id),
                "enable": action.role != MemberRole.MEMBER,
            },
        )

    async def set_member_title(self, action: SetMemberTitleAction) -> None:
        params: dict[str, Any] = {
            "group_id": str(action.group_id),
            "user_id": str(action.user_id),
            "special_title": action.title,
        }
        if isinstance(action, OneBotSetMemberTitleAction):
            params["duration"] = action.duration
        await self._call("set_group_special_title", params)

    async def set_member_card(self, action: SetMemberCardAction) -> None:
        await self._call(
            "set_group_card",
            {"group_id": str(action.group_id), "user_id": str(action.user_id), "card": action.card},
        )

    async def set_group_name(self, action: SetGroupNameAction) -> None:
        await self._call("set_group_name", {"group_id": str(action.group_id), "group_name": action.name})

    async def set_group_mute(self, action: SetGroupMuteAction) -> None:
        await self._call("set_group_whole_ban", {"group_id": str(action.group_id), "enable": action.muted})

    async def leave_group(self, action: LeaveGroupAction) -> None:
        params: dict[str, Any] = {"group_id": str(action.group_id)}
        if isinstance(action, OneBotLeaveGroupAction):
            params["is_dismiss"] = action.is_dismiss
        await self._call("set_group_leave", params)

    async def react_message(self, action: ReactMessageAction) -> None:
        if self.message_group_lookup is None:
            raise ActionRejectedError("OneBot reaction requires message context")
        group_id = self.message_group_lookup(action.message_id)
        if group_id is None:
            raise ActionRejectedError(f"OneBot reaction requires group context for message {action.message_id}")
        await self._send_group_reaction(group_id, action.message_id, action.reaction, action.enabled)

    async def group_reaction(self, action: GroupReactionAction) -> None:
        await self._send_group_reaction(action.group_id, action.message_id, action.reaction, action.enabled)

    async def _send_group_reaction(
        self,
        group_id: str,
        message_id: str,
        reaction: str,
        enabled: bool,
    ) -> None:
        params: dict[str, Any] = {
            "group_id": str(group_id),
            "message_id": str(message_id),
            "is_add": enabled,
        }
        if reaction.lstrip("-").isdigit():
            params["code"] = int(reaction)
        else:
            params["emoji"] = reaction
        await self._call(
            "group_reaction",
            params,
        )

    async def set_essence(self, action: SetEssenceAction) -> None:
        endpoint = "set_essence_msg" if action.enabled else "delete_essence_msg"
        await self._call(endpoint, {"message_id": str(action.message_id)})

    async def poke(self, action: PokeAction) -> None:
        params = {"user_id": str(action.user_id)}
        if action.scene_type == SceneType.GROUP:
            params["group_id"] = str(action.scene_id)
        await self._call("send_poke", params)

    async def send_like(self, action: SendLikeAction) -> None:
        await self._call("send_like", {"user_id": str(action.user_id), "times": action.times})

    async def get_cookie(self, action: GetCookieAction) -> CookieInfo:
        data = await self._call("get_cookies", {"domain": action.domain})
        return CookieInfo(cookies=str(data.get("cookies", "")))

    async def get_csrf_token(self, _action: GetCsrfTokenAction) -> CsrfTokenInfo:
        data = await self._call("get_csrf_token", {})
        return CsrfTokenInfo(token=int(data.get("token", 0)))

    async def approve_friend_request(self, action: ApproveFriendRequestAction) -> None:
        await self._call("set_friend_add_request", {"flag": str(action.request_id), "approve": True})

    async def reject_friend_request(self, action: RejectFriendRequestAction) -> None:
        await self._call(
            "set_friend_add_request",
            {"flag": str(action.request_id), "approve": False, "remark": action.reason or ""},
        )

    async def approve_group_request(self, action: ApproveGroupRequestAction) -> None:
        sub_type = self._request_subtype(str(action.request_id))
        await self._call(
            "set_group_add_request",
            {"flag": str(action.request_id), "sub_type": sub_type, "approve": True},
        )

    async def reject_group_request(self, action: RejectGroupRequestAction) -> None:
        sub_type = self._request_subtype(str(action.request_id))
        await self._call(
            "set_group_add_request",
            {
                "flag": str(action.request_id),
                "sub_type": sub_type,
                "approve": False,
                "reason": action.reason or "",
            },
        )

    async def upload_group_file(self, action: UploadGroupFileAction) -> None:
        params = {"group_id": str(action.group_id), "file": action.file}
        if action.name:
            params["name"] = action.name
        if action.folder:
            params["folder"] = action.folder
        await self._call("upload_group_file", params)

    async def upload_private_file(self, action: UploadPrivateFileAction) -> None:
        params = {"user_id": str(action.user_id), "file": action.file}
        if action.name:
            params["name"] = action.name
        await self._call("upload_private_file", params)

    async def get_group_file_url(self, action: GetGroupFileUrlAction) -> FileUrl:
        context = self.file_context_lookup(action.file_id) if self.file_context_lookup is not None else None
        params: dict[str, Any] = {"group_id": str(action.group_id), "file_id": str(action.file_id)}
        if context is not None and "busid" in context:
            params["busid"] = context["busid"]
        data = await self._call("get_group_file_url", params)
        return FileUrl(url=str(data.get("url", "")))

    async def get_private_file_url(self, action: GetPrivateFileUrlAction) -> FileUrl:
        params = {"user_id": str(action.user_id), "file_id": str(action.file_id)}
        file_hash = action.file_hash
        if file_hash is None and self.file_context_lookup is not None:
            context = self.file_context_lookup(action.file_id)
            if context is not None and context.get("file_hash"):
                file_hash = str(context["file_hash"])
        if not file_hash:
            raise ActionRejectedError(f"OneBot private file URL requires file_hash for {action.file_id}")
        params["file_hash"] = file_hash
        data = await self._call("get_private_file_url", params)
        return FileUrl(url=str(data.get("url", "")))

    def _request_subtype(self, request_id: str) -> str:
        if self.request_subtype_lookup is None:
            return "add"
        sub_type = self.request_subtype_lookup(request_id)
        if sub_type not in {"add", "invite"}:
            raise ActionRejectedError(f"OneBot group request subtype is unknown: {request_id}")
        return sub_type


def _member_role(value: object) -> MemberRole | None:
    match value:
        case "owner":
            return MemberRole.OWNER
        case "admin":
            return MemberRole.ADMIN
        case "member":
            return MemberRole.MEMBER
        case _:
            return None
