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
    DownloadFileAction,
    FetchMessageAction,
    FileReference,
    FileUrl,
    FriendInfo,
    GetBotProfileAction,
    GetBotStatusAction,
    GetCookieAction,
    GetCsrfTokenAction,
    GetFileInfoAction,
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

from .ids import (
    SCENE_FRIEND,
    SCENE_GROUP,
    decode_group_invitation_id,
    decode_group_request_id,
    decode_message_id,
    encode_message_id,
)
from .segments import MilkySegmentCodec, decode_forwarded_messages

ResultT = TypeVar("ResultT")

MILKY_ENDPOINTS = frozenset(
    {
        "get_login_info",
        "get_impl_info",
        "get_user_profile",
        "get_friend_list",
        "get_group_list",
        "get_group_info",
        "get_group_member_list",
        "get_group_member_info",
        "send_private_message",
        "send_group_message",
        "recall_private_message",
        "recall_group_message",
        "get_message",
        "get_forwarded_messages",
        "kick_group_member",
        "set_group_member_mute",
        "set_group_member_admin",
        "set_group_member_card",
        "set_group_member_special_title",
        "set_group_name",
        "set_group_whole_mute",
        "quit_group",
        "set_group_essence_message",
        "send_group_message_reaction",
        "send_group_nudge",
        "send_friend_nudge",
        "send_profile_like",
        "get_cookies",
        "get_csrf_token",
        "accept_friend_request",
        "reject_friend_request",
        "accept_group_request",
        "reject_group_request",
        "accept_group_invitation",
        "reject_group_invitation",
        "get_group_files",
        "upload_group_file",
        "upload_private_file",
        "get_group_file_download_url",
        "get_private_file_download_url",
    }
)


class ActionTransport(Protocol):
    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]: ...


FileContextLookup = Callable[[str], dict[str, JsonValue] | None]
RequestContextLookup = Callable[[str], dict[str, JsonValue] | None]


class MilkyKickMemberAction(KickMemberAction):
    reject_add_request: bool = False


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


class AcceptGroupInvitationAction(Action[None]):
    request_id: str

    @override
    def log_summary(self) -> str:
        return f"group invitation {format_text(self.request_id)} accept"


class RejectGroupInvitationAction(Action[None]):
    request_id: str
    reason: str | None = None

    @override
    def log_summary(self) -> str:
        return f"group invitation {format_text(self.request_id)} reject"


class GetForwardMessageAction(Action[Message]):
    log_level: ClassVar[str] = "TRACE"
    forward_id: str

    @override
    def log_summary(self) -> str:
        return f"fetch forward {format_text(self.forward_id)}"


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


class GetGroupFilesAction(Action[list[FileReference]]):
    log_level: ClassVar[str] = "TRACE"
    group_id: str
    parent_folder_id: str = "/"

    @override
    def log_summary(self) -> str:
        return f"[group] {format_text(str(self.group_id))} files in {format_text(self.parent_folder_id)}"


class GroupReactionAction(Action[None]):
    group_id: str
    message_id: str
    reaction: str
    enabled: bool = True

    @override
    def log_summary(self) -> str:
        action = "react" if self.enabled else "unreact"
        return f"{action} message {format_text(str(self.message_id))} with {format_text(self.reaction)}"


class MilkyActions:
    def __init__(
        self,
        transport: ActionTransport,
        codec: MilkySegmentCodec,
        action_timeout: float,
        *,
        file_context_lookup: FileContextLookup | None = None,
        request_context_lookup: RequestContextLookup | None = None,
    ) -> None:
        self.transport = transport
        self.codec = codec
        self.action_timeout = action_timeout
        self.file_context_lookup = file_context_lookup
        self.request_context_lookup = request_context_lookup

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
        registry.register(MilkyKickMemberAction, self.kick_member)
        registry.register(MuteMemberAction, self.mute_member)
        registry.register(UnmuteMemberAction, self.unmute_member)
        registry.register(SetMemberRoleAction, self.set_member_role)
        registry.register(SetMemberTitleAction, self.set_member_title)
        registry.register(SetMemberCardAction, self.set_member_card)
        registry.register(SetGroupNameAction, self.set_group_name)
        registry.register(SetGroupMuteAction, self.set_group_mute)
        registry.register(LeaveGroupAction, self.leave_group)
        registry.register(ReactMessageAction, self.react_message)
        registry.register(GroupReactionAction, self.group_reaction)
        registry.register(SetEssenceAction, self.set_essence)
        registry.register(PokeAction, self.poke)
        registry.register(SendLikeAction, self.send_like)
        registry.register(GetCookieAction, self.get_cookie)
        registry.register(GetCsrfTokenAction, self.get_csrf_token)
        registry.register(ApproveFriendRequestAction, self.approve_friend_request)
        registry.register(RejectFriendRequestAction, self.reject_friend_request)
        registry.register(ApproveGroupRequestAction, self.approve_group_request)
        registry.register(RejectGroupRequestAction, self.reject_group_request)
        registry.register(AcceptGroupInvitationAction, self.accept_group_invitation)
        registry.register(RejectGroupInvitationAction, self.reject_group_invitation)
        registry.register(GetFileInfoAction, self.get_file_info)
        registry.register(DownloadFileAction, self.download_file)
        registry.register(UploadGroupFileAction, self.upload_group_file)
        registry.register(UploadPrivateFileAction, self.upload_private_file)
        registry.register(GetGroupFileUrlAction, self.get_group_file_url)
        registry.register(GetPrivateFileUrlAction, self.get_private_file_url)
        registry.register(GetGroupFilesAction, self.get_group_files)

    async def raw(self, action: RawAction) -> RawResult:
        data = await self._call_raw(action.action, dict(action.params))
        return RawResult(data=data)

    async def _call_raw(self, endpoint: str, params: dict[str, Any]) -> JsonValue:
        response = await self.transport.call(endpoint, params, self.action_timeout)
        status = response.get("status")
        retcode = int(response.get("retcode", 0))
        if status != "ok" or retcode != 0:
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
        if action.scene_type == SceneType.GROUP:
            data = await self._call(
                "send_group_message",
                {"group_id": int(action.scene_id), "message": self.codec.encode_message(action.message)},
            )
            return SendResult(message_id=encode_message_id(SCENE_GROUP, action.scene_id, data["message_seq"]))
        data = await self._call(
            "send_private_message",
            {"user_id": int(action.scene_id), "message": self.codec.encode_message(action.message)},
        )
        return SendResult(message_id=encode_message_id(SCENE_FRIEND, action.scene_id, data["message_seq"]))

    async def send_private_message(self, action: SendPrivateMessageAction) -> SendResult:
        data = await self._call(
            "send_private_message",
            {"user_id": int(action.user_id), "message": self.codec.encode_message(action.message)},
        )
        return SendResult(message_id=encode_message_id(SCENE_FRIEND, action.user_id, data["message_seq"]))

    async def send_group_message(self, action: SendGroupMessageAction) -> SendResult:
        data = await self._call(
            "send_group_message",
            {"group_id": int(action.group_id), "message": self.codec.encode_message(action.message)},
        )
        return SendResult(message_id=encode_message_id(SCENE_GROUP, action.group_id, data["message_seq"]))

    async def recall_message(self, action: RecallMessageAction) -> None:
        scene, peer_id, message_seq = _split_message_id(action.message_id)
        if scene == SCENE_GROUP:
            await self._call(
                "recall_group_message",
                {"group_id": int(peer_id), "message_seq": int(message_seq)},
            )
        else:
            await self._call(
                "recall_private_message",
                {"user_id": int(peer_id), "message_seq": int(message_seq)},
            )

    async def fetch_message(self, action: FetchMessageAction) -> Message:
        scene, peer_id, message_seq = _split_message_id(action.message_id)
        data = await self._call(
            "get_message",
            {"message_scene": scene, "peer_id": int(peer_id), "message_seq": int(message_seq)},
        )
        message = data.get("message") or {}
        return self.codec.decode_message(
            message.get("segments") or [],
            scene=message.get("message_scene", scene),
            peer_id=message.get("peer_id", peer_id),
        )

    async def get_forward_message(self, action: GetForwardMessageAction) -> Message:
        data = await self._call("get_forwarded_messages", {"forward_id": action.forward_id})
        nodes = decode_forwarded_messages(data.get("messages") or [], self.codec)
        return Message(*nodes)

    async def get_bot_profile(self, _action: GetBotProfileAction) -> BotProfile:
        data = await self._call("get_login_info", {})
        return BotProfile(user_id=str(data.get("uin", 0)), display_name=str(data.get("nickname", "")))

    async def get_bot_status(self, _action: GetBotStatusAction) -> BotStatus:
        # Milky exposes no status API, so the protocol end is assumed healthy.
        return BotStatus(online=True)

    async def get_version(self, _action: GetVersionAction) -> VersionInfo:
        data = await self._call("get_impl_info", {})
        return VersionInfo(
            app_name=str(data.get("impl_name", "")),
            app_version=str(data.get("impl_version", "")),
            protocol_version=str(data.get("milky_version", "")),
        )

    async def get_user_profile(self, action: GetUserProfileAction) -> UserProfile:
        data = await self._call("get_user_profile", {"user_id": int(action.user_id)})
        return UserProfile(
            user_id=str(data.get("user_id", action.user_id)),
            display_name=str(data.get("nickname", "")),
            sex=str(data.get("sex", "")),
            age=int(data.get("age", 0)),
        )

    async def get_friend_list(self, _action: GetFriendListAction) -> list[FriendInfo]:
        data = await self._call("get_friend_list", {})
        return [
            FriendInfo(user_id=str(item.get("user_id", 0)), display_name=str(item.get("nickname", "")))
            for item in data.get("friends", [])
        ]

    async def get_group_profile(self, action: GetGroupProfileAction) -> GroupProfile:
        data = await self._call("get_group_info", {"group_id": int(action.group_id)})
        group = data.get("group", {})
        return GroupProfile(
            group_id=str(group.get("group_id", action.group_id)),
            name=str(group.get("group_name", "")),
            member_count=int(group.get("member_count", 0)),
            max_member_count=int(group.get("max_member_count", 0)),
        )

    async def get_group_list(self, _action: GetGroupListAction) -> list[GroupProfile]:
        data = await self._call("get_group_list", {})
        return [
            GroupProfile(
                group_id=str(item.get("group_id", 0)),
                name=str(item.get("group_name", "")),
                member_count=int(item.get("member_count", 0)),
                max_member_count=int(item.get("max_member_count", 0)),
            )
            for item in data.get("groups", [])
        ]

    async def get_group_member(self, action: GetGroupMemberAction) -> GroupMemberProfile:
        data = await self._call(
            "get_group_member_info",
            {"group_id": int(action.group_id), "user_id": int(action.user_id)},
        )
        member = data.get("member", {})
        return GroupMemberProfile(
            group_id=str(member.get("group_id", action.group_id)),
            user_id=str(member.get("user_id", action.user_id)),
            display_name=str(member.get("nickname", "")),
            card=str(member.get("card", "")),
            role=_member_role(member.get("role")),
        )

    async def get_group_member_list(self, action: GetGroupMemberListAction) -> list[GroupMemberProfile]:
        data = await self._call("get_group_member_list", {"group_id": int(action.group_id)})
        return [
            GroupMemberProfile(
                group_id=str(item.get("group_id", action.group_id)),
                user_id=str(item.get("user_id", 0)),
                display_name=str(item.get("nickname", "")),
                card=str(item.get("card", "")),
                role=_member_role(item.get("role")),
            )
            for item in data.get("members", [])
        ]

    async def kick_member(self, action: KickMemberAction) -> None:
        params: dict[str, Any] = {"group_id": int(action.group_id), "user_id": int(action.user_id)}
        if isinstance(action, MilkyKickMemberAction):
            params["reject_add_request"] = action.reject_add_request
        await self._call("kick_group_member", params)

    async def mute_member(self, action: MuteMemberAction) -> None:
        await self._call(
            "set_group_member_mute",
            {"group_id": int(action.group_id), "user_id": int(action.user_id), "duration": action.duration},
        )

    async def unmute_member(self, action: UnmuteMemberAction) -> None:
        await self._call(
            "set_group_member_mute",
            {"group_id": int(action.group_id), "user_id": int(action.user_id), "duration": 0},
        )

    async def set_member_role(self, action: SetMemberRoleAction) -> None:
        await self._call(
            "set_group_member_admin",
            {
                "group_id": int(action.group_id),
                "user_id": int(action.user_id),
                "is_set": action.role != MemberRole.MEMBER,
            },
        )

    async def set_member_title(self, action: SetMemberTitleAction) -> None:
        await self._call(
            "set_group_member_special_title",
            {"group_id": int(action.group_id), "user_id": int(action.user_id), "special_title": action.title},
        )

    async def set_member_card(self, action: SetMemberCardAction) -> None:
        await self._call(
            "set_group_member_card",
            {"group_id": int(action.group_id), "user_id": int(action.user_id), "card": action.card},
        )

    async def set_group_name(self, action: SetGroupNameAction) -> None:
        await self._call("set_group_name", {"group_id": int(action.group_id), "new_group_name": action.name})

    async def set_group_mute(self, action: SetGroupMuteAction) -> None:
        await self._call("set_group_whole_mute", {"group_id": int(action.group_id), "is_mute": action.muted})

    async def leave_group(self, action: LeaveGroupAction) -> None:
        await self._call("quit_group", {"group_id": int(action.group_id)})

    async def react_message(self, action: ReactMessageAction) -> None:
        scene, peer_id, message_seq = _split_message_id(action.message_id)
        if scene != SCENE_GROUP:
            raise ActionRejectedError(f"Milky only supports group message reactions: {action.message_id}")
        await self._send_group_reaction(peer_id, message_seq, action.reaction, action.enabled)

    async def group_reaction(self, action: GroupReactionAction) -> None:
        _, _, message_seq = _split_message_id(action.message_id)
        await self._send_group_reaction(action.group_id, message_seq, action.reaction, action.enabled)

    async def accept_group_invitation(self, action: AcceptGroupInvitationAction) -> None:
        group_id, invitation_seq = decode_group_invitation_id(action.request_id)
        await self._call("accept_group_invitation", {"group_id": int(group_id), "invitation_seq": int(invitation_seq)})

    async def reject_group_invitation(self, action: RejectGroupInvitationAction) -> None:
        group_id, invitation_seq = decode_group_invitation_id(action.request_id)
        params: dict[str, Any] = {"group_id": int(group_id), "invitation_seq": int(invitation_seq)}
        if action.reason:
            params["reason"] = action.reason
        await self._call("reject_group_invitation", params)

    async def _send_group_reaction(self, group_id: str, message_seq: str, reaction: str, enabled: bool) -> None:
        await self._call(
            "send_group_message_reaction",
            {
                "group_id": int(group_id),
                "message_seq": int(message_seq),
                "reaction": reaction,
                "reaction_type": "face" if reaction.isdigit() else "emoji",
                "is_add": enabled,
            },
        )

    async def set_essence(self, action: SetEssenceAction) -> None:
        scene, peer_id, message_seq = _split_message_id(action.message_id)
        if scene != SCENE_GROUP:
            raise ActionRejectedError("Milky only supports group essence messages")
        await self._call(
            "set_group_essence_message",
            {
                "group_id": int(peer_id),
                "message_seq": int(message_seq),
                "is_set": action.enabled,
            },
        )

    async def poke(self, action: PokeAction) -> None:
        if action.scene_type == SceneType.GROUP:
            await self._call("send_group_nudge", {"group_id": int(action.scene_id), "user_id": int(action.user_id)})
        else:
            await self._call("send_friend_nudge", {"user_id": int(action.user_id)})

    async def send_like(self, action: SendLikeAction) -> None:
        await self._call("send_profile_like", {"user_id": int(action.user_id), "count": action.times})

    async def get_cookie(self, action: GetCookieAction) -> CookieInfo:
        data = await self._call("get_cookies", {"domain": action.domain})
        return CookieInfo(cookies=str(data.get("cookies", "")))

    async def get_csrf_token(self, _action: GetCsrfTokenAction) -> CsrfTokenInfo:
        data = await self._call("get_csrf_token", {})
        token = str(data.get("csrf_token", "0"))
        return CsrfTokenInfo(token=int(token) if token.isdigit() else 0)

    async def approve_friend_request(self, action: ApproveFriendRequestAction) -> None:
        await self._call(
            "accept_friend_request",
            {"initiator_uid": str(action.request_id), "is_filtered": self._is_filtered(action.request_id)},
        )

    async def reject_friend_request(self, action: RejectFriendRequestAction) -> None:
        params: dict[str, Any] = {
            "initiator_uid": str(action.request_id),
            "is_filtered": self._is_filtered(action.request_id),
        }
        if action.reason:
            params["reason"] = action.reason
        await self._call("reject_friend_request", params)

    async def approve_group_request(self, action: ApproveGroupRequestAction) -> None:
        group_id, notification_seq = decode_group_request_id(action.request_id)
        context = self._request_context(action.request_id)
        await self._call(
            "accept_group_request",
            {
                "notification_seq": int(notification_seq),
                "notification_type": context.get("notification_type", "join_request"),
                "group_id": int(group_id),
                "is_filtered": bool(context.get("is_filtered", False)),
            },
        )

    async def reject_group_request(self, action: RejectGroupRequestAction) -> None:
        group_id, notification_seq = decode_group_request_id(action.request_id)
        context = self._request_context(action.request_id)
        params: dict[str, Any] = {
            "notification_seq": int(notification_seq),
            "notification_type": context.get("notification_type", "join_request"),
            "group_id": int(group_id),
            "is_filtered": bool(context.get("is_filtered", False)),
        }
        if action.reason:
            params["reason"] = action.reason
        await self._call("reject_group_request", params)

    async def get_file_info(self, action: GetFileInfoAction) -> FileReference:
        reference = await self._group_files(action.file_id)
        if reference is None:
            raise ActionRejectedError(f"Milky cannot look up file {action.file_id} without group context")
        return reference

    async def download_file(self, action: DownloadFileAction) -> FileUrl:
        context = self.file_context_lookup(action.file_id) if self.file_context_lookup is not None else None
        context = context or {}
        params: dict[str, Any] = {"file_id": str(action.file_id)}
        if context.get("group_id"):
            endpoint = "get_group_file_download_url"
            params["group_id"] = _int(context["group_id"])
        elif context.get("user_id") and context.get("file_hash"):
            endpoint = "get_private_file_download_url"
            params["user_id"] = _int(context["user_id"])
            params["file_hash"] = str(context["file_hash"])
            if "is_self" in context:
                params["is_self_send"] = bool(context["is_self"])
        else:
            raise ActionRejectedError(
                f"Milky needs the scene of file {action.file_id}; use group_url() or private_url() instead"
            )
        data = await self._call(endpoint, params)
        return FileUrl(url=str(data.get("download_url", "")))

    async def upload_group_file(self, action: UploadGroupFileAction) -> None:
        params: dict[str, Any] = {
            "group_id": int(action.group_id),
            "file_uri": action.file,
            "file_name": action.name or "file",
        }
        if action.folder:
            params["parent_folder_id"] = action.folder
        await self._call("upload_group_file", params)

    async def upload_private_file(self, action: UploadPrivateFileAction) -> None:
        params: dict[str, Any] = {
            "user_id": int(action.user_id),
            "file_uri": action.file,
            "file_name": action.name or "file",
        }
        await self._call("upload_private_file", params)

    async def get_group_file_url(self, action: GetGroupFileUrlAction) -> FileUrl:
        data = await self._call(
            "get_group_file_download_url",
            {"group_id": int(action.group_id), "file_id": str(action.file_id)},
        )
        return FileUrl(url=str(data.get("download_url", "")))

    async def get_private_file_url(self, action: GetPrivateFileUrlAction) -> FileUrl:
        file_hash = action.file_hash
        if file_hash is None and self.file_context_lookup is not None:
            context = self.file_context_lookup(action.file_id)
            if context is not None and context.get("file_hash"):
                file_hash = str(context["file_hash"])
        if not file_hash:
            raise ActionRejectedError(f"Milky private file URL requires file_hash for {action.file_id}")
        data = await self._call(
            "get_private_file_download_url",
            {
                "user_id": int(action.user_id),
                "file_id": str(action.file_id),
                "file_hash": file_hash,
            },
        )
        return FileUrl(url=str(data.get("download_url", "")))

    async def get_group_files(self, action: GetGroupFilesAction) -> list[FileReference]:
        data = await self._call(
            "get_group_files",
            {"group_id": int(action.group_id), "parent_folder_id": action.parent_folder_id},
        )
        return [
            FileReference(
                file_id=str(item.get("file_id", "")),
                name=str(item.get("file_name", "")),
            )
            for item in data.get("files", [])
        ]

    async def _group_files(self, file_id: str) -> FileReference | None:
        context = self.file_context_lookup(file_id) if self.file_context_lookup is not None else None
        group_id = context.get("group_id") if context else None
        if not group_id:
            return None
        data = await self._call("get_group_files", {"group_id": _int(group_id), "parent_folder_id": "/"})
        for item in data.get("files", []):
            if str(item.get("file_id", "")) == str(file_id):
                return FileReference(
                    file_id=str(item.get("file_id", "")),
                    name=str(item.get("file_name", "")),
                )
        return None

    def _request_context(self, request_id: str) -> dict[str, JsonValue]:
        if self.request_context_lookup is None:
            return {}
        return self.request_context_lookup(request_id) or {}

    def _is_filtered(self, request_id: str) -> bool:
        return bool(self._request_context(request_id).get("is_filtered", False))


def _split_message_id(message_id: str) -> tuple[str, str, str]:
    try:
        return decode_message_id(message_id)
    except ValueError as exc:
        raise ActionRejectedError(str(exc)) from exc


def _int(value: object) -> int:
    if isinstance(value, int | float):
        return int(value)
    return int(str(value))


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


__all__ = [
    "MILKY_ENDPOINTS",
    "AcceptGroupInvitationAction",
    "GetForwardMessageAction",
    "GetGroupFileUrlAction",
    "GetGroupFilesAction",
    "GetPrivateFileUrlAction",
    "GroupReactionAction",
    "MilkyActions",
    "MilkyKickMemberAction",
    "RejectGroupInvitationAction",
    "SendGroupMessageAction",
    "SendPrivateMessageAction",
    "UploadGroupFileAction",
    "UploadPrivateFileAction",
]
