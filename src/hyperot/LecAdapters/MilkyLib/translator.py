import json

from websockets.asyncio.client import connect as wsc

from hyperot.network import WebsocketConnection, httpx_post

from ...adapters.obuilder import OneBotEventBuilder, OneBotJsonMessageBuilder
from ...common import Message
from ...utils import errors


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
        self.segments.append({"type": "reply", "data": {"seq": seq}})
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
                builder.reply(message_id=str(msg_enid(scene, seg_data["seq"], peer_id)))
            case "face":
                builder.faces(face_id=seg_data["face_id"])
            case "record":
                builder.record(file=seg_data["temp_url"])
            case "video":
                builder.video(file=seg_data["temp_url"])
            case "forward":
                builder.forward(forward_id=seg_data["forward_id"])
            case "market_face":
                raise NotImplementedError  # Impl later
            case _:
                raise NotImplementedError  # Maybe never :(

    return builder.build()


def to_milky_message(message: Message) -> list[dict]:
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

    async def recv(self) -> dict:
        milky_rp = json.loads(await self.ws.recv())
        milky_event_type = milky_rp["type"]
        milky_time = milky_rp["time"]
        milky_self_id = milky_rp["self_id"]
        milky_data = milky_rp["data"]
        builder = OneBotEventBuilder()
        match milky_event_type:
            case "bot_offline":
                raise errors.BotOfflineError("Bot offline")
            case "message_receive":
                if milky_data["message_scene"] == "friend":
                    return (
                        builder.init(milky_time, milky_self_id, milky_data["sender_id"], 0)
                        .as_private_message(
                            message_translator(milky_data["segments"], milky_data["peer_id"], 0),
                            str(msg_enid(0, milky_data["message_seq"], milky_data["sender_id"])),
                        )
                        .private_sender(milky_data["friend"]["nickname"], milky_data["friend"]["sex"], 0)
                        .build()
                    )
                elif milky_data["message_scene"] == "group":
                    return (
                        builder.init(milky_time, milky_self_id, milky_data["sender_id"], milky_data["peer_id"])
                        .as_group_message(
                            message_translator(milky_data["segments"], milky_data["peer_id"], 1),
                            str(msg_enid(0, milky_data["message_seq"], milky_data["sender_id"])),
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
                else:
                    raise NotImplementedError
            case _:
                raise NotImplementedError

    async def http_send(self, endpoint: str, data: dict) -> dict:
        if not data:
            data = {}
        if self.auth:
            response = await httpx_post(
                f"{self.url}/api/{endpoint}", json=data, headers={"Authorization": f"Bearer {self.auth}"}
            )
        else:
            response = await httpx_post(f"{self.url}/api/{endpoint}", json=data)
        res = response.json()
        return res
