from abc import ABC
from collections.abc import Callable
from typing import Literal, cast

from . import common, configurator, hyperogger
from .hyperogger import levels
from .network import HTTPConnection, WebsocketConnection
from .segments import At, message_types

__all__ = [
    "BotOnLineEvent",
    "Event",
    "EventManager",
    "FriendAddEvent",
    "FriendAddRequestEvent",
    "FriendFileUploadEvent",
    "FriendRecallEvent",
    "GroupAddInviteEvent",
    "GroupAdminEvent",
    "GroupAnonymous",
    "GroupEssenceEvent",
    "GroupFileUploadEvent",
    "GroupInvitationEvent",
    "GroupMemberDecreaseEvent",
    "GroupMemberIncreaseEvent",
    "GroupMessageEvent",
    "GroupMuteEvent",
    "GroupNameChangeEvent",
    "GroupRecallEvent",
    "GroupSender",
    "GroupWholeMuteEvent",
    "HyperListenerStartNotify",
    "HyperListenerStopNotify",
    "HyperNotify",
    "MessageEvent",
    "MessageReactionEvent",
    "NoticeEvent",
    "NotifyEvent",
    "PrivateMessageEvent",
    "PrivateSender",
    "RequestEvent",
    "UnrecognizedEvent",
    "em",
    "gen_message",
    "init",
]

config: configurator.BotConfig
logger: hyperogger.Logger


def init():
    global config, logger
    config = configurator.BotConfig.get("hyper-bot")
    logger = hyperogger.Logger()
    logger.set_level(config.log_level)


class EventManager:
    def __init__(self):
        self.event_lis: dict[str, dict[str, type[Event]]] = {"message": {}, "notice": {}, "request": {}}
        self.events: list[type[Event]] = []

    def reg(self, type_of: str, str_eql: str) -> Callable:
        def wrapper(cls: type[Event]) -> type[Event]:
            self.event_lis[type_of][str_eql] = cls
            self.events.append(cls)
            return cls

        return wrapper

    def new(self, data: dict) -> "Event":
        logger.trace(str(data))
        try:
            return self.event_lis[data["post_type"]][data[f"{data['post_type']}_type"]](data)
        except KeyError:
            typ = data[f"{data['post_type']}_type"]
            logger.log(f"不存在的事件类型：{data['post_type']}.{typ}", levels.WARNING)
            logger.log(str(data), levels.DEBUG)
            return UnrecognizedEvent(data)


em = EventManager()


class GroupSender:
    user_id: int | None
    nickname: str | None
    sex: Literal["male", "female", "unknown"] | None
    age: int | None
    card: str | None
    area: str | None
    level: str | None
    role: Literal["owner", "admin", "member"] | None
    title: str | None

    def __init__(self, json_data: dict):
        self.user_id = json_data.get("user_id")
        self.nickname = json_data.get("nickname")
        self.sex = json_data.get("sex")
        self.age = json_data.get("age")
        self.card = json_data.get("card")
        self.area = json_data.get("area")
        self.level = json_data.get("level")
        self.role = json_data.get("role")
        self.title = json_data.get("title")


class PrivateSender:
    user_id: int | None
    nickname: str | None
    sex: Literal["male", "female", "unknown"] | None
    age: int | None

    def __init__(self, json_data: dict):
        self.user_id = json_data.get("user_id")
        self.nickname = json_data.get("nickname")
        self.sex = json_data.get("sex")
        self.age = json_data.get("age")


class GroupAnonymous:
    id: str | None
    name: str | None
    flag: str | None

    def __init__(self, json_data: dict | None):
        if json_data is None:
            pass
        else:
            self.id = json_data.get("id")
            self.name = json_data.get("name")
            self.flag = json_data.get("flag")


def gen_message(data: dict) -> common.Message:
    message = common.Message()
    for i in data["message"]:
        if i["type"] in message_types:
            args = []
            for j in message_types[i["type"]]["args"]:
                args.append(i["data"].get(j))
            message.add(message_types[i["type"]]["type"](*args))
        else:
            logger.log(f"无法序列化的消息段 {i['type']}", levels.WARNING)
            logger.log(str(i), levels.DEBUG)

    return message


class Event(ABC):
    data: dict
    time: int
    self_id: int
    post_type: str
    user_id: int | None
    group_id: int | None
    is_owner: bool
    blocked: bool
    is_silent: bool

    def __init__(self, data: dict):
        self.data = data.copy()
        self.time = cast(int, data.get("time"))
        self.self_id = data.get("self_id", 0)
        self.post_type = cast(str, data.get("post_type"))
        self.user_id = data.get("user_id")
        self.group_id = data.get("group_id")

        self.is_owner = self.self_id in config.owner
        self.blocked = self.user_id in config.black_list or self.group_id in config.black_list
        self.is_silent = self.user_id in config.silents or self.group_id in config.silents or 0 in config.silents

    def print_log(self) -> None: ...


class UnrecognizedEvent(Event):
    pass


class MessageEvent(Event):
    sub_type: str | None
    message_id: str
    message: common.Message
    msg_str: str

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.message_id = str(data.get("message_id"))
        self.message = gen_message(data=data)
        self.msg_str = str(self.message)


@em.reg("message", "private")
class PrivateMessageEvent(MessageEvent):
    sender: PrivateSender

    def __init__(self, data: dict):
        super().__init__(data)
        self.sender = PrivateSender(data.get("sender"))  # type: ignore

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"收到 {self.user_id} 的消息：{self.message}")


@em.reg("message", "group")
class GroupMessageEvent(MessageEvent):
    sender: GroupSender
    anonymous: GroupAnonymous
    is_mentioned: bool

    def __init__(self, data: dict):
        super().__init__(data)
        self.sender = GroupSender(data.get("sender"))  # type: ignore
        self.anonymous = GroupAnonymous(data.get("anonymous"))  # type: ignore
        self.is_mentioned = At(str(self.self_id)) in self.message

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"收到来自群 {self.group_id} 中 {self.user_id} 的消息： {self.message}")


class NoticeEvent(Event):
    notice_type: str | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.notice_type = data.get("notice_type")


@em.reg("notice", "group_upload")
class GroupFileUploadEvent(NoticeEvent):
    file: dict | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.file = data.get("file")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"{self.user_id} 在 {self.group_id} 上传了文件 {self.file}")


@em.reg("notice", "group_admin")
class GroupAdminEvent(NoticeEvent):
    sub_type: Literal["set", "unset"] | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")

        self.print_log()

    def print_log(self) -> None:
        logger.log(
            f"用户 {self.user_id} 在群 {self.group_id} 被{'设置' if self.sub_type == 'set' else '取消'}管理员身份"
        )


@em.reg("notice", "group_decrease")
class GroupMemberDecreaseEvent(NoticeEvent):
    sub_type: Literal["leave", "kick", "kick_me"] | None
    operator_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.operator_id = data.get("operator_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"{self.user_id} 离开群 {self.group_id}， [{self.sub_type}, {self.operator_id}]")


@em.reg("notice", "group_increase")
class GroupMemberIncreaseEvent(NoticeEvent):
    sub_type: Literal["approve", "invite"] | None
    operator_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.operator_id = data.get("operator_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"{self.user_id} 加入群 {self.group_id}， [{self.sub_type}, {self.operator_id}]")


@em.reg("notice", "group_ban")
class GroupMuteEvent(NoticeEvent):
    sub_type: Literal["ban", "lift_ban"] | None
    operator_id: int | None
    duration: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.operator_id = data.get("operator_id")
        self.duration = data.get("duration")

        self.print_log()

    def print_log(self) -> None:
        logger.log(
            f"{self.user_id} 在群 {self.group_id} 被{'' if self.sub_type == 'ban' else '解除'}禁言， 时长为{self.duration}"
        )


@em.reg("notice", "group_whole_mute")
class GroupWholeMuteEvent(NoticeEvent):
    sub_type: Literal["mute", "unmute"] | None
    operator_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.operator_id = data.get("operator_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(
            f"群 {self.group_id} 被{'开启' if self.sub_type == 'mute' else '取消'}全员禁言，操作者 {self.operator_id}"
        )


@em.reg("notice", "group_name_change")
class GroupNameChangeEvent(NoticeEvent):
    new_group_name: str | None
    operator_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.new_group_name = data.get("new_group_name")
        self.operator_id = data.get("operator_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"群 {self.group_id} 名称变更为 {self.new_group_name}，操作者 {self.operator_id}")


@em.reg("notice", "group_invitation")
class GroupInvitationEvent(NoticeEvent):
    invitation_seq: int | None
    initiator_id: int | None
    source_group_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.invitation_seq = data.get("invitation_seq")
        self.initiator_id = data.get("initiator_id")
        self.source_group_id = data.get("source_group_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"邀请者 {self.initiator_id} 邀请本机器人加入群 {self.group_id}")


@em.reg("notice", "friend_add")
class FriendAddEvent(NoticeEvent):
    def __init__(self, data: dict):
        super().__init__(data)

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"收到 {self.user_id} 的好友请求")


@em.reg("notice", "friend_upload")
class FriendFileUploadEvent(NoticeEvent):
    file: dict | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.file = data.get("file")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"{self.user_id} 上传了文件 {self.file}")


@em.reg("notice", "group_recall")
class GroupRecallEvent(NoticeEvent):
    operator_id: int | None
    message_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.operator_id = data.get("operator_id")
        self.message_id = data.get("message_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"{self.operator_id} 在群 {self.group_id} 中撤回了 {self.user_id} 的消息 {self.message_id}")


@em.reg("notice", "friend_recall")
class FriendRecallEvent(NoticeEvent):
    message_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.message_id = data.get("message_id")

        self.print_log()

    def print_log(self) -> None:
        logger.log(f"{self.user_id} 撤回了一条消息")


@em.reg("notice", "notify")
class NotifyEvent(NoticeEvent):
    sub_type: Literal["poke", "lucky_king", "honor"] | None
    target_id: int | None
    honor_type: str | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.target_id = data.get("target_id")
        self.honor_type = data.get("honor_type")


@em.reg("notice", "essence")
class GroupEssenceEvent(NoticeEvent):
    sub_type: Literal["add", "remove"] | None
    sender_id: int | None
    operator_id: int | None
    message_id: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")
        self.sender_id = data.get("sender_id")
        self.operator_id = data.get("operator_id")
        self.message_id = data.get("message_id")

        self.print_log()

    def print_log(self) -> None:
        action = "设置" if self.sub_type == "add" else "移除"
        logger.log(
            f"{self.operator_id} 在群 {self.group_id} 中将 {self.sender_id} 的消息 {self.message_id} {action}精华"
        )


@em.reg("notice", "reaction")
class MessageReactionEvent(NoticeEvent):
    message_id: int | None
    operator_id: int | None
    sub_type: Literal["add", "remove"] | None
    code: int | None
    count: int | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.message_id = data.get("message_id")
        self.operator_id = data.get("operator_id")
        self.sub_type = data.get("sub_type")
        self.code = data.get("code")
        self.count = data.get("count")


@em.reg("notice", "bot_online")
class BotOnLineEvent(NoticeEvent):
    reason: str | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.reason = data.get("reason")

        self.print_log()

    def print_log(self) -> None:
        logger.info(f"由于 {self.reason} ，OneBot 实现与 QQ 重新连接")


class RequestEvent(Event):
    comment: str | None
    flag: str | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.comment = data.get("comment")
        self.flag = data.get("flag")


@em.reg("request", "friend")
class FriendAddRequestEvent(RequestEvent):
    def __init__(self, data: dict):
        super().__init__(data)


@em.reg("request", "group")
class GroupAddInviteEvent(RequestEvent):
    sub_type: Literal["add", "invite"] | None

    def __init__(self, data: dict):
        super().__init__(data)
        self.sub_type = data.get("sub_type")


class HyperNotify:
    time: int
    type: str

    def __init__(self, time_now: int, notify_type: str):
        self.time = time_now
        self.type = notify_type


class HyperListenerStartNotify(HyperNotify):
    connection: WebsocketConnection | HTTPConnection | None

    def __init__(self, time_now: int, notify_type: str, connection: WebsocketConnection | HTTPConnection | None = None):
        super().__init__(time_now, notify_type)
        self.connection = connection


class HyperListenerStopNotify(HyperNotify):
    pass
