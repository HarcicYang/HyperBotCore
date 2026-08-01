from collections.abc import Callable

from typing_extensions import override

from ... import common, configurator, hyperogger, network, segments
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

config = configurator.BotConfig.get("hyper-bot")
logger = hyperogger.Logger()
logger.set_level(config.log_level)


class OneBotActions(ActionsBase):
    def __init__(self, cnt: network.WebsocketConnection | network.HTTPConnection):
        self.connection = cnt

        class CustomAction:
            def __init__(self, cnt_i: network.WebsocketConnection | network.HTTPConnection):
                self.connection = cnt_i

            def __getattr__(self, item) -> Callable:
                async def wrapper(**kwargs) -> str:
                    packet = Packet(str(item), **kwargs)
                    await packet.send_to(self.connection)
                    return packet.echo

                return wrapper

        self.custom = CustomAction(self.connection)

    @override
    async def send_msg(
        self, message: common.Message | str, group_id: int | None = None, user_id: int | None = None
    ) -> common.Ret[MsgSendRsp]:
        if isinstance(message, str):
            message = common.Message(segments.Text(message))
        if group_id:
            packet = Packet("send_msg", group_id=group_id, message=await message.get())
        elif user_id:
            packet = Packet("send_msg", user_id=user_id, message=await message.get())
        else:
            raise errors.ArgsInvalidError("'send' API requires 'group_id' or 'user_id' but none of them are provided.")
        await packet.send_to(self.connection)
        logger.info(f"向{(('群 ' + str(group_id)) if group_id else ('用户' + str(user_id))) + ' '}发送：{message!s}")
        return await common.Ret.fetch(packet.echo, MsgSendRsp)

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
        await Packet(
            "delete_msg",
            message_id=message_id,
        ).send_to(self.connection)
        logger.info(f"撤回 {message_id}")

    @override
    async def set_group_kick(self, group_id: int, user_id: int) -> None:
        await Packet(
            "set_group_kick",
            group_id=group_id,
            user_id=user_id,
        ).send_to(self.connection)
        logger.info(f"将用户 {user_id} 移出群 {group_id}")

    @override
    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 60) -> None:
        await Packet(
            "set_group_ban",
            group_id=group_id,
            user_id=user_id,
            duration=duration,
        ).send_to(self.connection)
        logger.info(f"在群 {group_id} 将用户 {user_id} 禁言 {duration}s")

    @override
    async def get_login_info(self) -> common.Ret[GetLoginInfoRsp]:
        packet = Packet("get_login_info")
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, GetLoginInfoRsp)

    @override
    async def get_version_info(self) -> common.Ret[GetVerInfoRsp]:
        packet = Packet("get_version_info")
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, GetVerInfoRsp)

    @override
    async def send_forward_msg(self, message: common.Message) -> common.Ret[SendForwardRsp]:
        packet = Packet("send_forward_msg", messages=await message.get())
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, SendForwardRsp)

    @override
    async def get_forward_msg(self, sid: str) -> common.Ret[common.Message]:
        packet = Packet(
            "get_forward_msg",
            id=sid,
        )
        await packet.send_to(self.connection)
        ret = await common.Ret.fetch(packet.echo, gen_message)
        for i in ret.data:
            if isinstance(i, segments.Node):
                i.content = gen_message({"message": i.content})

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
        packet = Packet("send_group_forward_msg", group_id=group_id, messages=await message.get())
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, SendForwardRsp)

    @override
    async def set_group_add_request(
        self, flag: str, sub_type: str, approve: bool, reason: str = "Not Mentioned"
    ) -> None:
        await Packet("set_group_add_request", flag=flag, sub_type=sub_type, approve=approve, reason=reason).send_to(
            self.connection
        )
        logger.info(f"由于 {reason}，{'通过' if approve else '拒绝'} {flag} 请求")

    @override
    async def get_stranger_info(self, user_id: int) -> common.Ret[GetStrInfoRsp]:
        packet = Packet(
            "get_stranger_info",
            user_id=user_id,
            no_cache=True,
        )
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, GetStrInfoRsp)

    @override
    async def get_group_member_info(self, group_id: int, user_id: int) -> common.Ret[GetGrpMemInfoRsp]:
        packet = Packet("get_group_member_info", group_id=group_id, user_id=user_id, no_cache=True)
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, GetGrpMemInfoRsp)

    @override
    async def get_group_info(self, group_id: int) -> common.Ret[GetGrpInfoRsp]:
        packet = Packet("get_group_info", group_id=group_id, no_cache=True)
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, GetGrpInfoRsp)

    @override
    async def get_status(self) -> common.Ret:
        packet = Packet("get_status")
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo)

    @override
    async def set_essence_msg(self, message_id: int) -> None:
        await Packet("set_essence_msg", message_id=message_id).send_to(self.connection)

    @override
    async def set_group_special_title(self, group_id: int, user_id: int, title: str) -> None:
        await Packet(
            "set_group_special_title",
            group_id=group_id,
            user_id=user_id,
            special_title=title,
        ).send_to(self.connection)

    @override
    async def get_msg(self, msg_id: int) -> common.Ret[GetMsgRsp]:
        packet = Packet("get_msg", message_id=msg_id)
        await packet.send_to(self.connection)
        return await common.Ret.fetch(packet.echo, GetMsgRsp)

    @override
    async def send_callback(self, group_id: int, bot_id: int, data: dict) -> None:
        await Packet("send_group_bot_callback", group_id=group_id, bot_id=bot_id, **data).send_to(self.connection)
