from abc import ABC
from typing import Literal

from typing_extensions import override

from ..common import Message
from ..events import GroupSender, PrivateSender, gen_message

__all__ = [
    "BaseResponse",
    "GetGrpInfoRsp",
    "GetGrpMemInfoRsp",
    "GetLoginInfoRsp",
    "GetMsgRsp",
    "GetStrInfoRsp",
    "GetVerInfoRsp",
    "MsgSendRsp",
    "SendForwardRsp",
    "SendGrpForwardRsp",
]


class BaseResponse(ABC):
    def __init__(self, json_data: dict | str):
        self.raw = json_data
        if json_data:
            assert isinstance(json_data, dict)
            self.inner_build(json_data)

    def inner_build(self, json_data: dict) -> None: ...


class MsgSendRsp(BaseResponse):
    message_id: int

    @override
    def inner_build(self, json_data: dict):
        self.message_id = json_data["message_id"]


class GetLoginInfoRsp(BaseResponse):
    user_id: int
    nickname: str

    @override
    def inner_build(self, json_data: dict):
        self.user_id = json_data["user_id"]
        self.nickname = json_data["nickname"]


class GetVerInfoRsp(BaseResponse):
    app_name: str
    app_version: str
    protocol_version: str

    @override
    def inner_build(self, json_data: dict):
        self.app_name = json_data["app_name"]
        self.app_version = json_data["app_version"]
        self.protocol_version = json_data["protocol_version"]


class SendForwardRsp(BaseResponse):
    res_id: str

    @override
    def __init__(self, json_data: dict | str):
        self.raw = json_data
        if json_data:
            self.inner_build(json_data)

    @override
    def inner_build(self, json_data: dict | str):
        if isinstance(json_data, dict):
            self.res_id = str(json_data["res_id"])
        else:
            self.res_id = json_data


class SendGrpForwardRsp(BaseResponse):
    message_id: int
    forward_id: str

    @override
    def inner_build(self, json_data: dict):
        self.message_id = json_data.get("message_id", 0)
        # 兼容部分协议端仅返回 res_id 的实现
        self.forward_id = str(json_data.get("forward_id", json_data.get("res_id", "")))


class GetStrInfoRsp(BaseResponse):
    user_id: int
    nickname: str
    sex: str
    age: int

    @override
    def inner_build(self, json_data: dict):
        self.user_id = json_data["user_id"]
        self.nickname = json_data["nickname"]
        self.sex = json_data["sex"]
        self.age = json_data["age"]


class GetGrpMemInfoRsp(BaseResponse):
    group_id: int
    user_id: int
    nickname: str
    card: str
    sex: str
    age: int
    area: str
    join_time: int
    last_sent_time: int
    level: str
    role: Literal["owner", "admin", "member"]
    unfriendly: bool
    title: str
    title_expire_time: int
    card_changeable: bool

    @override
    def inner_build(self, json_data: dict):
        self.group_id = json_data["group_id"]
        self.user_id = json_data["user_id"]
        self.nickname = json_data["nickname"]
        self.card = json_data["card"]
        self.sex = json_data["sex"]
        self.age = json_data["age"]
        self.area = json_data["area"]
        self.join_time = json_data["join_time"]
        self.last_sent_time = json_data["last_sent_time"]
        self.level = json_data["level"]
        self.role = json_data["role"]
        self.unfriendly = json_data["unfriendly"]
        self.title = json_data["title"]
        self.title_expire_time = json_data["title_expire_time"]
        self.card_changeable = json_data["card_changeable"]


class GetGrpInfoRsp(BaseResponse):
    group_id: int
    group_name: str
    member_count: int
    max_member_count: int

    @override
    def inner_build(self, json_data: dict):
        self.group_id = json_data["group_id"]
        self.group_name = json_data["group_name"]
        self.member_count = json_data["member_count"]
        self.max_member_count = json_data["max_member_count"]


class GetMsgRsp(BaseResponse):
    time: int
    message_type: Literal["private", "group"]
    message_id: int
    real_id: int
    sender: PrivateSender | GroupSender
    message: Message

    @override
    def inner_build(self, json_data: dict):
        self.time = json_data["time"]
        self.message_type = json_data["message_type"]
        self.message_id = json_data["message_id"]
        self.real_id = json_data["real_id"]
        self.sender = (
            GroupSender(json_data["sender"]) if self.message_type == "group" else PrivateSender(json_data["sender"])
        )
        self.message = gen_message(json_data)

    @classmethod
    def build(
        cls,
        time: int,
        message_type: Literal["private", "group"],
        message_id: int,
        real_id: int,
        sender: dict,
        message: dict,
    ):
        return cls(
            {
                "time": time,
                "message_type": message_type,
                "message_id": message_id,
                "real_id": real_id,
                "sender": sender,
                "message": message,
            }
        )
