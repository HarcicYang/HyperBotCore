from abc import ABC, abstractmethod
from typing import Any

from ..common import Message, Ret
from ..utils.apiresponse import (
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

__all__ = ["ActionsBase"]


class ActionsBase(ABC):
    """协议无关的 Actions 接口，OneBot/Milky 适配器分别实现。

    `custom` 支持调用未封装的协议 API：
    - OneBot：方法名即 OneBot action，返回 echo ID（str）
    - Milky：方法名即 Milky API，返回响应 data 字典
    """

    custom: Any

    @abstractmethod
    async def send_msg(
        self, message: Message | str, group_id: int | None = None, user_id: int | None = None
    ) -> Ret[MsgSendRsp]: ...

    @abstractmethod
    async def send_group_msg(self, message: Message | str, group_id: int | None = None) -> Ret[MsgSendRsp]: ...

    @abstractmethod
    async def send_private_msg(self, message: Message | str, user_id: int | None = None) -> Ret[MsgSendRsp]: ...

    @abstractmethod
    async def del_msg(self, message_id: int) -> None: ...

    @abstractmethod
    async def set_group_kick(self, group_id: int, user_id: int) -> None: ...

    @abstractmethod
    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 60) -> None: ...

    @abstractmethod
    async def get_login_info(self) -> Ret[GetLoginInfoRsp]: ...

    @abstractmethod
    async def get_version_info(self) -> Ret[GetVerInfoRsp]: ...

    @abstractmethod
    async def send_forward_msg(self, message: Message) -> Ret[SendForwardRsp]: ...

    @abstractmethod
    async def get_forward_msg(self, sid: str) -> Ret[Message]: ...

    @abstractmethod
    async def forward_solve(self, message: Message) -> Message: ...

    @abstractmethod
    async def send_group_forward_msg(self, group_id: int, message: Message) -> Ret[SendGrpForwardRsp]: ...

    @abstractmethod
    async def set_group_add_request(
        self, flag: str, sub_type: str, approve: bool, reason: str = "Not Mentioned"
    ) -> None: ...

    @abstractmethod
    async def get_stranger_info(self, user_id: int) -> Ret[GetStrInfoRsp]: ...

    @abstractmethod
    async def get_group_member_info(self, group_id: int, user_id: int) -> Ret[GetGrpMemInfoRsp]: ...

    @abstractmethod
    async def get_group_info(self, group_id: int) -> Ret[GetGrpInfoRsp]: ...

    @abstractmethod
    async def get_status(self) -> Ret: ...

    @abstractmethod
    async def set_essence_msg(self, message_id: int) -> None: ...

    @abstractmethod
    async def set_group_special_title(self, group_id: int, user_id: int, title: str) -> None: ...

    @abstractmethod
    async def get_msg(self, msg_id: int) -> Ret[GetMsgRsp]: ...

    @abstractmethod
    async def send_callback(self, group_id: int, bot_id: int, data: dict) -> None: ...
