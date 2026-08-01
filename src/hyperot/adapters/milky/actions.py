from collections.abc import Callable

from typing_extensions import override

from ... import common, configurator, hyperogger, segments
from ...events import gen_message
from ...protocol import ActionsBase
from ...utils import errors
from ...utils.apiresponse import (
    GetGrpInfoRsp,
    GetGrpMemInfoRsp,
    GetLoginInfoRsp,
    GetMsgRsp,
    GetStrInfoRsp,
    GetVerInfoRsp,
    MsgSendRsp,
    SendForwardRsp,
    SendGrpForwardRsp,
)
from .packet import Packet
from .translator import (
    MilkyHttpConnection,
    message_translator,
    msg_deid,
    msg_enid,
    node_list_to_milky_forward,
    to_milky_message,
)

config = configurator.BotConfig.get("hyper-bot")
logger = hyperogger.Logger.create("hyperot.adapter.milky.actions", config.log_level)


class MilkyActions(ActionsBase):
    def __init__(self, cnt: MilkyHttpConnection):
        self.connection = cnt

        class CustomAction:
            def __init__(self, cnt_i: MilkyHttpConnection):
                self.connection = cnt_i

            def __getattr__(self, item) -> Callable:
                async def wrapper(**kwargs) -> dict | None:
                    res = await Packet(str(item), **kwargs).send_to(self.connection)
                    return res.get("data")

                return wrapper

        self.custom = CustomAction(self.connection)

    @override
    async def send_msg(
        self, message: common.Message | str, group_id: int | None = None, user_id: int | None = None
    ) -> common.Ret[MsgSendRsp]:
        if isinstance(message, str):
            message = common.Message(segments.Text(message))
        elif not isinstance(message, common.Message):
            message = common.Message(message)
        if group_id is not None:
            endpoint, scene, peer = "send_group_message", 1, group_id
        elif user_id is not None:
            endpoint, scene, peer = "send_private_message", 0, user_id
        else:
            raise errors.ArgsInvalidError("'send' API requires 'group_id' or 'user_id' but none of them are provided.")
        res = await Packet(
            endpoint,
            **{("group_id" if group_id is not None else "user_id"): peer},
            message=to_milky_message(message),
        ).send_to(self.connection)
        ret = common.Ret(res)
        ret.data = MsgSendRsp({"message_id": msg_enid(scene, res["data"]["message_seq"], peer)})
        logger.info(f"向{'群 ' + str(peer) if scene else '用户 ' + str(peer)}发送：{message!s}")
        return ret

    @override
    async def send_group_msg(
        self, message: common.Message | str, group_id: int | None = None
    ) -> common.Ret[MsgSendRsp]:
        return await self.send_msg(message, group_id=group_id)

    @override
    async def send_private_msg(
        self, message: common.Message | str, user_id: int | None = None
    ) -> common.Ret[MsgSendRsp]:
        return await self.send_msg(message, user_id=user_id)

    @override
    async def del_msg(self, message_id: int) -> None:
        scene, seq, peer = msg_deid(message_id)
        if scene == 0:
            await Packet("recall_private_message", user_id=peer, message_seq=seq).send_to(self.connection)
        else:
            await Packet("recall_group_message", group_id=peer, message_seq=seq).send_to(self.connection)
        logger.info(f"撤回消息 {message_id}")

    @override
    async def set_group_kick(self, group_id: int, user_id: int) -> None:
        await Packet("kick_group_member", group_id=group_id, user_id=user_id).send_to(self.connection)
        logger.info(f"将用户 {user_id} 移出群 {group_id}")

    @override
    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 60) -> None:
        await Packet("set_group_member_mute", group_id=group_id, user_id=user_id, duration=duration).send_to(
            self.connection
        )
        logger.info(f"在群 {group_id} 将用户 {user_id} 禁言 {duration}s")

    @override
    async def get_login_info(self) -> common.Ret[GetLoginInfoRsp]:
        res = await Packet("get_login_info").send_to(self.connection)
        ret = common.Ret(res)
        ret.data = GetLoginInfoRsp({"user_id": res["data"]["uin"], "nickname": res["data"]["nickname"]})
        return ret

    @override
    async def get_version_info(self) -> common.Ret[GetVerInfoRsp]:
        res = await Packet("get_impl_info").send_to(self.connection)
        ret = common.Ret(res)
        ret.data = GetVerInfoRsp(
            {
                "app_name": res["data"]["impl_name"],
                "app_version": res["data"]["impl_version"],
                "protocol_version": res["data"]["milky_version"],
            }
        )
        return ret

    @override
    async def send_forward_msg(self, message: common.Message) -> common.Ret[SendForwardRsp]:
        raise NotImplementedError("Milky adapter 发送合并转发请使用 send_group_forward_msg")

    @override
    async def get_forward_msg(self, sid: str) -> common.Ret[common.Message]:
        res = await Packet("get_forwarded_messages", forward_id=sid).send_to(self.connection)
        nodes = []
        for fm in res["data"]["messages"]:
            content = gen_message({"message": message_translator(fm.get("segments", []), 0, 0)})
            nodes.append(
                segments.Node(
                    user_id=str(fm.get("message_seq", 0)), nickname=fm.get("sender_name", ""), content=content
                )
            )
        ret = common.Ret(res)
        ret.data = common.Message(*nodes)
        return ret

    @override
    async def forward_solve(self, message: common.Message) -> common.Message:
        for i in message:
            if isinstance(i, segments.Forward):
                data = await self.get_forward_msg(i.id)
                return data.data
        raise ValueError("Incorrect message type")

    @override
    async def send_group_forward_msg(self, group_id: int, message: common.Message) -> common.Ret[SendGrpForwardRsp]:
        res = await Packet("send_group_msg", group_id=group_id, message=[node_list_to_milky_forward(message)]).send_to(
            self.connection
        )
        ret = common.Ret(res)
        ret.data = SendGrpForwardRsp({"message_id": res["data"]["message_seq"], "forward_id": ""})
        return ret

    @override
    async def set_group_add_request(
        self, flag: str, sub_type: str, approve: bool, reason: str = "Not Mentioned"
    ) -> None:
        group_id, seq = (int(x) for x in flag.split(":"))
        notification_type = "join_request" if sub_type == "add" else "invited_join_request"
        endpoint = "accept_group_request" if approve else "reject_group_request"
        params = {
            "notification_seq": seq,
            "notification_type": notification_type,
            "group_id": group_id,
        }
        if not approve:
            params["reason"] = reason
        await Packet(endpoint, **params).send_to(self.connection)
        logger.info(f"由于 {reason}，{'通过' if approve else '拒绝'} {flag} 请求")

    @override
    async def get_stranger_info(self, user_id: int) -> common.Ret[GetStrInfoRsp]:
        res = await Packet("get_user_profile", user_id=user_id).send_to(self.connection)
        ret = common.Ret(res)
        d = res["data"]
        ret.data = GetStrInfoRsp(
            {
                "user_id": user_id,
                "nickname": d.get("nickname", ""),
                "sex": d.get("sex", "unknown"),
                "age": d.get("age", 0),
            }
        )
        return ret

    @override
    async def get_group_member_info(self, group_id: int, user_id: int) -> common.Ret[GetGrpMemInfoRsp]:
        res = await Packet("get_group_member_info", group_id=group_id, user_id=user_id).send_to(self.connection)
        ret = common.Ret(res)
        d = res["data"].get("member", {})
        ret.data = GetGrpMemInfoRsp(
            {
                "group_id": d.get("group_id", group_id),
                "user_id": d.get("user_id", user_id),
                "nickname": d.get("nickname", ""),
                "card": d.get("card", ""),
                "sex": d.get("sex", "unknown"),
                "age": 0,
                "area": "",
                "join_time": d.get("join_time", 0),
                "last_sent_time": d.get("last_sent_time", 0),
                "level": str(d.get("level", "")),
                "role": d.get("role", "member"),
                "unfriendly": False,
                "title": d.get("title", ""),
                "title_expire_time": 0,
                "card_changeable": False,
            }
        )
        return ret

    @override
    async def get_group_info(self, group_id: int) -> common.Ret[GetGrpInfoRsp]:
        res = await Packet("get_group_info", group_id=group_id).send_to(self.connection)
        ret = common.Ret(res)
        d = res["data"].get("group", {})
        ret.data = GetGrpInfoRsp(
            {
                "group_id": d.get("group_id", group_id),
                "group_name": d.get("group_name", ""),
                "member_count": d.get("member_count", 0),
                "max_member_count": d.get("max_member_count", 0),
            }
        )
        return ret

    @override
    async def get_status(self) -> common.Ret:
        return common.Ret({"status": "ok", "retcode": 0, "data": {}})

    @override
    async def set_essence_msg(self, message_id: int) -> None:
        scene, seq, peer = msg_deid(message_id)
        if scene != 1:
            raise ValueError("Only group messages can be set as essence")
        await Packet("set_group_essence_message", group_id=peer, message_seq=seq, is_set=True).send_to(self.connection)

    @override
    async def set_group_special_title(self, group_id: int, user_id: int, title: str) -> None:
        await Packet("set_group_member_special_title", group_id=group_id, user_id=user_id, special_title=title).send_to(
            self.connection
        )

    @override
    async def get_msg(self, msg_id: int) -> common.Ret[GetMsgRsp]:
        scene, seq, peer = msg_deid(msg_id)
        message_scene = "friend" if scene == 0 else "group"
        res = await Packet("get_message", message_scene=message_scene, peer_id=peer, message_seq=seq).send_to(
            self.connection
        )
        ret = common.Ret(res)
        d = res["data"]
        ret.data = GetMsgRsp(
            {
                "time": d.get("time", 0),
                "message_type": "group" if d.get("message_scene") == "group" else "private",
                "message_id": 0,
                "real_id": d.get("message_seq", 0),
                "sender": d.get("group_member", d.get("friend", {})),
                "message": message_translator(d.get("segments", []), d.get("peer_id", 0), scene),
            }
        )
        return ret

    @override
    async def send_callback(self, group_id: int, bot_id: int, data: dict) -> None:
        raise NotImplementedError("Milky adapter does not support send_callback")
