import asyncio
import json

import pytest

from hyperot.adapters.milky import MilkyActions
from hyperot.adapters.milky.packet import Packet
from hyperot.adapters.milky.translator import (
    MilkyHttpConnection,
    message_translator,
    milky_seg_from_dict,
    msg_deid,
    msg_enid,
)
from hyperot.protocol.segments import register_milky_converter
from hyperot.segments import At, Image, Text
from hyperot.utils import errors

register_milky_converter(milky_seg_from_dict)


def _event(event_type: str, data: dict) -> dict:
    return {"event_type": event_type, "time": 1, "self_id": 2, "data": data}


def _connection(payload: dict) -> MilkyHttpConnection:
    class FakeWS:
        async def recv(self) -> str:
            return json.dumps(payload)

    connection = MilkyHttpConnection("ws://example.com")
    connection.ws = FakeWS()
    return connection


def _actions() -> MilkyActions:
    return MilkyActions(MilkyHttpConnection("ws://example.com"))


def test_incoming_group_message_keeps_scene_and_sender():
    payload = _event(
        "message_receive",
        {
            "message_scene": "group",
            "sender_id": 3,
            "peer_id": 4,
            "message_seq": 5,
            "segments": [{"type": "text", "data": {"text": "yo"}}],
            "group_member": {
                "nickname": "n",
                "sex": "male",
                "card": "c",
                "level": 1,
                "role": "admin",
                "title": "",
            },
        },
    )

    event = asyncio.run(_connection(payload).recv())

    assert event is not None
    assert event["post_type"] == "message"
    assert event["message_type"] == "group"
    assert event["group_id"] == 4
    assert event["message_id"] == str(msg_enid(1, 5, 4))
    assert event["sender"]["card"] == "c"


def test_message_translation_covers_reply_media_and_unknown_segments():
    incoming = message_translator(
        [
            {"type": "text", "data": {"text": "hi"}},
            {"type": "image", "data": {"temp_url": "http://x/a.png"}},
            {"type": "mention", "data": {"user_id": 123}},
            {"type": "reply", "data": {"message_seq": 42}},
            {"type": "unknown", "data": {}},
        ],
        9,
        1,
    )

    assert incoming == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "image", "data": {"file": "http://x/a.png", "url": "http://x/a.png", "summary": "[图片]"}},
        {"type": "at", "data": {"qq": 123}},
        {"type": "reply", "data": {"id": str(msg_enid(1, 42, 9))}},
    ]
    assert milky_seg_from_dict({"type": "at", "data": {"qq": "42"}}) == {
        "type": "mention",
        "data": {"user_id": 42},
    }
    assert Text("hi").milky_outgoing_seg() == {"type": "text", "data": {"text": "hi"}}
    assert At(qq="all").milky_outgoing_seg() == {"type": "mention_all", "data": {}}
    assert Image(file="u").milky_outgoing_seg()["data"]["uri"] == "u"
    assert msg_deid(msg_enid(0, 1, 2)) == (0, 1, 2)


def test_actions_map_to_milky_endpoints(monkeypatch):
    captured = []

    async def fake_send_to(self, _connection):
        captured.append((self.endpoint, self.paras))
        return {"status": "ok", "retcode": 0, "data": {"message_seq": 7, "time": 1}}

    monkeypatch.setattr(Packet, "send_to", fake_send_to)
    actions = _actions()

    result = asyncio.run(actions.send_msg(Text("hi"), group_id=123))
    asyncio.run(actions.del_msg(msg_enid(1, 7, 123)))
    asyncio.run(actions.set_group_add_request("4:9", "add", True))

    assert result.data.message_id == msg_enid(1, 7, 123)
    assert captured == [
        ("send_group_message", {"group_id": 123, "message": [{"type": "text", "data": {"text": "hi"}}]}),
        ("recall_group_message", {"group_id": 123, "message_seq": 7}),
        ("accept_group_request", {"notification_seq": 9, "notification_type": "join_request", "group_id": 4}),
    ]


def test_http_error_is_reported(monkeypatch):
    class Response:
        status_code = 500
        text = ""

        def json(self):
            raise json.JSONDecodeError("Expecting value", "", 0)

    async def fake_post(*_args, **_kwargs):
        return Response()

    from hyperot.adapters.milky import translator

    monkeypatch.setattr(translator, "httpx_post", fake_post)

    with pytest.raises(errors.ApiError):
        asyncio.run(MilkyHttpConnection("ws://example.com").http_send("get_login_info", {}))
