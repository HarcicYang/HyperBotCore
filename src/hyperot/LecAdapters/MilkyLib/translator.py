import json
from typing import TYPE_CHECKING

from websockets.asyncio.client import connect as wsc

from hyperot.network import WebsocketConnection, httpx_post

from ... import configurator, hyperogger
from ...adapters.obuilder import OneBotEventBuilder, OneBotJsonMessageBuilder
from ...utils import errors

if TYPE_CHECKING:
    from ...common import Message

config = configurator.BotConfig.get("hyper-bot")
logger = hyperogger.Logger()
logger.set_level(config.log_level)


class MilkyOutGoingSegBuilder:
    def __init__(self) -> None:
        self.segments: list[dict] = []

    def text(self, text: str) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "text", "data": {"text": text}})
        return self

    def mention(self, user_id: int) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "mention", "data": {"user_id": user_id}})
        return self

    def mention_all(self) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "mention_all", "data": {}})
        return self

    def face(self, face_id: str) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "face", "data": {"face_id": face_id}})
        return self

    def reply(self, seq: int) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "reply", "data": {"message_seq": seq}})
        return self

    def image(self, uri: str, summary: str = "[Image]", sub_type: str = "normal") -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "image", "data": {"uri": uri, "summary": summary, "sub_type": sub_type}})
        return self

    def record(self, uri: str) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "record", "data": {"uri": uri}})
        return self

    def video(self, uri: str, thumb_uri: str | None = None) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "video", "data": {"uri": uri, "thumb_uri": thumb_uri}})
        return self

    @staticmethod
    def outgoing_forward(user_id: int, sender_name: str, segments: list[dict]) -> dict:
        return {"user_id": user_id, "sender_name": sender_name, "segments": segments}

    def forward(self, messages: list[dict]) -> "MilkyOutGoingSegBuilder":
        self.segments.append({"type": "forward", "data": {"messages": messages}})
        return self

    def build(self) -> list[dict]:
        return self.segments


def msg_enid(scene: int, seq: int, peer_id: int) -> int:
    # For scene: friend: 0, group: 1
    return (scene << 128) | (seq << 64) | peer_id


def msg_deid(enid: int) -> tuple[int, int, int]:
    scene = (enid >> 128) & 0xFFFF
    seq = (enid >> 64) & 0xFFFFFFFF
    peer_id = enid & 0xFFFFFFFFFFFFFFFF
    return scene, seq, peer_id


def message_translator(milky_message: list[dict], peer_id: int, scene: int = 0) -> list[dict]:
    builder = OneBotJsonMessageBuilder()
    for seg in milky_message:
        seg_type = seg["type"]
        seg_data = seg["data"]
        match seg_type:
            case "text":
                builder.text(seg_data["text"])
            case "image":
                builder.image(file=seg_data["temp_url"], summary=seg_data.get("summary", "[Image]"))
            case "mention":
                builder.at(seg_data["user_id"])
            case "mention_all":
                builder.at("all")
            case "reply":
                builder.reply(message_id=str(msg_enid(scene, seg_data["message_seq"], peer_id)))
            case "face":
                builder.faces(face_id=seg_data["face_id"])
            case "record":
                builder.record(file=seg_data["temp_url"])
            case "video":
                builder.video(file=seg_data["temp_url"])
            case "forward":
                builder.forward(forward_id=seg_data["forward_id"])
            case "market_face":
                builder.mface(
                    face_id=seg_data.get("emoji_id", ""),
                    tab_id=str(seg_data.get("emoji_package_id", "")),
                    key=seg_data.get("key", ""),
                )
            case "light_app":
                builder.json({"app_name": seg_data.get("app_name", ""), "payload": seg_data.get("json_payload", "")})
            case "xml":
                builder.json({"service_id": seg_data.get("service_id", 0), "payload": seg_data.get("xml_payload", "")})
            case "file":
                logger.debug(f"忽略不支持的文件消息段：{seg_data}")
            case _:
                logger.debug(f"忽略未知消息段：{seg_type}")

    return builder.build()


def _nodes_to_forward_messages(nodes: list) -> list[dict]:
    messages = []
    for node in nodes:
        node_full = node.to_json() if hasattr(node, "to_json") else node
        node_data = node_full.get("data", node_full)
        content = node_data.get("content")
        if hasattr(content, "get_sync"):
            node_segs = [_to_milky_seg(s) for s in content.get_sync()]
        elif isinstance(content, list):
            node_segs = [_to_milky_seg(s) for s in content]
        elif isinstance(content, dict):
            node_segs = [_to_milky_seg(content)]
        else:
            node_segs = []
        messages.append(
            {
                "user_id": node_data.get("user_id"),
                "sender_name": node_data.get("nickname") or node_data.get("nick_name"),
                "segments": node_segs,
            }
        )
    return messages


def node_list_to_milky_forward(message: "Message") -> dict:
    return {"type": "forward", "data": {"messages": _nodes_to_forward_messages(list(message.contents))}}


def _to_milky_seg(seg: dict) -> dict:
    seg_type = seg["type"]
    seg_data = seg["data"]
    match seg_type:
        case "text":
            return {"type": "text", "data": {"text": seg_data["text"]}}
        case "at":
            if seg_data.get("qq") == "all":
                return {"type": "mention_all", "data": {}}
            try:
                uid = int(seg_data["qq"])
            except (KeyError, TypeError, ValueError):
                uid = seg_data.get("qq")
            return {"type": "mention", "data": {"user_id": uid}}
        case "reply":
            try:
                seq = msg_deid(int(seg_data["id"]))[1]
            except (KeyError, TypeError, ValueError):
                seq = seg_data.get("id")
            return {"type": "reply", "data": {"message_seq": seq}}
        case "face":
            return {
                "type": "face",
                "data": {"face_id": seg_data.get("id"), "is_large": seg_data.get("is_large", False)},
            }
        case "image":
            return {
                "type": "image",
                "data": {
                    "uri": seg_data.get("file"),
                    "summary": seg_data.get("summary", "[Image]"),
                    "sub_type": seg_data.get("sub_type", "normal"),
                },
            }
        case "record":
            return {"type": "record", "data": {"uri": seg_data.get("file")}}
        case "video":
            return {"type": "video", "data": {"uri": seg_data.get("file"), "thumb_uri": seg_data.get("thumb_uri")}}
        case "forward":
            return {"type": "forward", "data": {"messages": _nodes_to_forward_messages(seg_data.get("content", []))}}
        case _:
            return {"type": "text", "data": {"text": ""}}


def milky_seg_from_dict(seg: dict) -> dict:
    return _to_milky_seg(seg.to_json() if hasattr(seg, "to_json") else seg)


def to_milky_message(message: "Message") -> list[dict]:
    for i in message.contents:
        if not hasattr(i, "milky_outgoing_seg"):
            raise NotImplementedError(f"Segment {type(i)} not supported in Milky adapter.")
    return [i.milky_outgoing_seg() for i in message.contents]


class MilkyHttpConnection(WebsocketConnection):
    async def connect(self) -> None:
        if self.auth:
            self.ws = await wsc(self.url + "/event", header={"Authorization": "Bearer " + self.auth})
        else:
            self.ws = await wsc(self.url + "/event")

    async def recv(self) -> dict | None:
        milky_rp = json.loads(await self.ws.recv())
        milky_event_type = milky_rp.get("event_type") or milky_rp.get("type")
        milky_time = milky_rp["time"]
        milky_self_id = milky_rp["self_id"]
        milky_data = milky_rp["data"]
        builder = OneBotEventBuilder()
        match milky_event_type:
            case "message_receive":
                scene = milky_data["message_scene"]
                if scene == "friend":
                    return (
                        builder.init(milky_time, milky_self_id, milky_data["sender_id"], 0)
                        .as_private_message(
                            message_translator(milky_data["segments"], milky_data["peer_id"], 0),
                            str(msg_enid(0, milky_data["message_seq"], milky_data["sender_id"])),
                        )
                        .private_sender(milky_data["friend"]["nickname"], milky_data["friend"]["sex"], 0)
                        .build()
                    )
                if scene == "group":
                    return (
                        builder.init(milky_time, milky_self_id, milky_data["sender_id"], milky_data["peer_id"])
                        .as_group_message(
                            message_translator(milky_data["segments"], milky_data["peer_id"], 1),
                            str(msg_enid(1, milky_data["message_seq"], milky_data["peer_id"])),
                        )
                        .group_sender(
                            milky_data["group_member"]["nickname"],
                            milky_data["group_member"]["sex"],
                            0,
                            milky_data["group_member"]["card"],
                            "",
                            str(milky_data["group_member"]["level"]),
                            milky_data["group_member"]["role"],
                            milky_data["group_member"]["title"],
                        )
                        .build()
                    )
                if scene == "temp":
                    logger.debug(f"临时会话消息按私聊消息处理：{milky_data}")
                    return (
                        builder.init(milky_time, milky_self_id, milky_data["sender_id"], 0)
                        .as_private_message(
                            message_translator(milky_data["segments"], milky_data["peer_id"], 0),
                            str(msg_enid(0, milky_data["message_seq"], milky_data["sender_id"])),
                        )
                        .private_sender("", "unknown", 0)
                        .build()
                    )
                logger.debug(f"忽略未知消息场景：{scene}")
                return None
            case "bot_offline":
                return (
                    builder.init(milky_time, milky_self_id, milky_self_id, 0)
                    .as_bot_online_event(milky_data.get("reason", "bot offline"))
                    .build()
                )
            case "message_recall":
                scene = milky_data["message_scene"]
                if scene == "group":
                    return (
                        builder.init(milky_time, milky_self_id, milky_data["sender_id"], milky_data["peer_id"])
                        .as_group_recall_event(milky_data["operator_id"], str(milky_data["message_seq"]))
                        .build()
                    )
                return (
                    builder.init(milky_time, milky_self_id, milky_data["sender_id"], 0)
                    .as_friend_recall_event(milky_data["message_seq"])
                    .build()
                )
            case "group_admin_change":
                builder.data["sub_type"] = "set" if milky_data["is_set"] else "unset"
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], milky_data["group_id"])
                    .as_group_admin_event()
                    .build()
                )
            case "group_essence_message_change":
                builder.data["sub_type"] = "add" if milky_data["is_set"] else "remove"
                return (
                    builder.init(milky_time, milky_self_id, 0, milky_data["group_id"])
                    .as_group_essence_event(0, milky_data["operator_id"], str(milky_data["message_seq"]))
                    .build()
                )
            case "group_member_increase":
                sub_type = "invite" if milky_data.get("invitor_id") else "approve"
                operator = milky_data.get("operator_id") or milky_data.get("invitor_id")
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], milky_data["group_id"])
                    .as_group_increase_event(operator, sub_type)
                    .build()
                )
            case "group_member_decrease":
                sub_type = "kick" if milky_data.get("operator_id") else "leave"
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], milky_data["group_id"])
                    .as_group_decrease_event(milky_data.get("operator_id", 0), sub_type)
                    .build()
                )
            case "group_mute":
                sub_type = "ban" if milky_data["duration"] else "lift_ban"
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], milky_data["group_id"])
                    .as_group_mute_event(milky_data["operator_id"], milky_data["duration"], sub_type)
                    .build()
                )
            case "group_whole_mute":
                return (
                    builder.init(milky_time, milky_self_id, milky_data.get("operator_id", 0), milky_data["group_id"])
                    .as_group_whole_mute_event(milky_data["is_mute"])
                    .build()
                )
            case "group_name_change":
                return (
                    builder.init(milky_time, milky_self_id, milky_data.get("operator_id", 0), milky_data["group_id"])
                    .as_group_name_change_event(milky_data["new_group_name"], milky_data["operator_id"])
                    .build()
                )
            case "group_invitation":
                return (
                    builder.init(milky_time, milky_self_id, milky_data["initiator_id"], milky_data["group_id"])
                    .as_group_invitation_event(
                        milky_data["invitation_seq"], milky_data["initiator_id"], milky_data.get("source_group_id")
                    )
                    .build()
                )
            case "group_file_upload":
                file = {
                    "id": milky_data["file_id"],
                    "name": milky_data["file_name"],
                    "size": milky_data["file_size"],
                    "busid": 0,
                }
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], milky_data["group_id"])
                    .as_group_file_upload(file)
                    .build()
                )
            case "friend_file_upload":
                file = {
                    "id": milky_data["file_id"],
                    "name": milky_data["file_name"],
                    "size": milky_data["file_size"],
                    "busid": 0,
                    "hash": milky_data.get("file_hash", ""),
                }
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], 0)
                    .as_friend_file_upload_event(file)
                    .build()
                )
            case "group_message_reaction":
                builder.data["sub_type"] = "add" if milky_data["is_add"] else "remove"
                try:
                    code = int(milky_data["face_id"])
                except (TypeError, ValueError):
                    code = milky_data["face_id"]
                return (
                    builder.init(milky_time, milky_self_id, milky_data["user_id"], milky_data["group_id"])
                    .as_group_reaction_event(str(milky_data["message_seq"]), milky_data["user_id"], code, 0)
                    .build()
                )
            case "friend_nudge":
                builder.data["target_id"] = milky_self_id
                return builder.init(milky_time, milky_self_id, milky_data["user_id"], 0).as_poke().build()
            case "group_nudge":
                builder.data["target_id"] = milky_data["receiver_id"]
                return (
                    builder.init(milky_time, milky_self_id, milky_data["sender_id"], milky_data["group_id"])
                    .as_poke()
                    .build()
                )
            case "friend_request":
                return (
                    builder.init(milky_time, milky_self_id, milky_data["initiator_id"], 0)
                    .as_friend_add_request(milky_data.get("comment", ""), milky_data["initiator_uid"])
                    .build()
                )
            case "group_join_request":
                flag = f"{milky_data['group_id']}:{milky_data['notification_seq']}"
                return (
                    builder.init(milky_time, milky_self_id, milky_data["initiator_id"], milky_data["group_id"])
                    .as_group_add_request(milky_data.get("comment", ""), flag, "add")
                    .build()
                )
            case "group_invited_join_request":
                flag = f"{milky_data['group_id']}:{milky_data['notification_seq']}"
                return (
                    builder.init(milky_time, milky_self_id, milky_data["initiator_id"], milky_data["group_id"])
                    .as_group_add_request("", flag, "invite")
                    .build()
                )
            case _:
                logger.debug(f"忽略未知事件类型：{milky_event_type}")
                return None

    async def http_send(self, endpoint: str, data: dict) -> dict:
        if not data:
            data = {}
        http_url = self.url.replace("ws://", "http://").replace("wss://", "https://")
        if self.auth:
            response = await httpx_post(
                f"{http_url}/api/{endpoint}", json=data, headers={"Authorization": f"Bearer {self.auth}"}
            )
        else:
            response = await httpx_post(f"{http_url}/api/{endpoint}", json=data)
        try:
            return response.json()
        except json.JSONDecodeError:
            raise errors.ApiError(
                f"协议端响应异常 (HTTP {response.status_code}): {response.text[:200] or '空响应体'}"
            ) from None
