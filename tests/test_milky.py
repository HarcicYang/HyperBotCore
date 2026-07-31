import asyncio
import json

import pytest

from hyperot.LecAdapters.MilkyLib.Res import SegmentBase as MilkySegmentBase
from hyperot.LecAdapters.MilkyLib.translator import (
    MilkyHttpConnection,
    MilkyOutGoingSegBuilder,
    message_translator,
    msg_deid,
    msg_enid,
)
from hyperot.utils.errors import BotOfflineError


def test_msg_enid_deid_roundtrip():
    for scene, seq, peer in [(0, 1, 123), (1, 42, 999), (0, 0, 1)]:
        assert msg_deid(msg_enid(scene, seq, peer)) == (scene, seq, peer)


def test_message_translator_text_image_mention():
    ob = message_translator(
        [
            {"type": "text", "data": {"text": "hi"}},
            {"type": "image", "data": {"temp_url": "http://a/b.png"}},
            {"type": "mention", "data": {"user_id": 123}},
        ],
        9,
        1,
    )
    assert ob == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "image", "data": {"file": "http://a/b.png", "url": "http://a/b.png", "summary": "[Image]"}},
        {"type": "at", "data": {"qq": 123}},
    ]


def test_message_translator_mention_all():
    ob = message_translator([{"type": "mention_all", "data": {}}], 9)
    assert ob == [{"type": "at", "data": {"qq": "all"}}]


def test_message_translator_unsupported_segment():
    with pytest.raises(NotImplementedError):
        message_translator([{"type": "unknown_seg", "data": {}}], 9)


def test_outgoing_builder():
    b = MilkyOutGoingSegBuilder()
    b.text("hi").mention(1).mention_all().face("f").reply(3)
    assert b.build() == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "mention", "data": {"user_id": 1}},
        {"type": "mention_all", "data": {}},
        {"type": "face", "data": {"face_id": "f"}},
        {"type": "reply", "data": {"seq": 3}},
    ]


def test_outgoing_builder_image_video_forward():
    b = MilkyOutGoingSegBuilder()
    b.image("http://a/i.png").video("http://a/v.mp4", thumb_uri="http://a/t.jpg")
    b.forward([MilkyOutGoingSegBuilder.outgoing_forward(1, "n", [])])
    assert b.build() == [
        {"type": "image", "data": {"uri": "http://a/i.png", "summary": "[Image]", "sub_type": "normal"}},
        {"type": "video", "data": {"uri": "http://a/v.mp4", "thumb_uri": "http://a/t.jpg"}},
        {"type": "forward", "data": {"messages": [{"user_id": 1, "sender_name": "n", "segments": []}]}},
    ]


class _FakeWS:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload)

    async def recv(self) -> str:
        return self._payload


def _conn(payload: dict) -> MilkyHttpConnection:
    conn = MilkyHttpConnection("ws://example.com")
    conn.ws = _FakeWS(payload)
    return conn


def test_recv_group_message():
    conn = _conn(
        {
            "type": "message_receive",
            "time": 1,
            "self_id": 2,
            "data": {
                "message_scene": "group",
                "sender_id": 3,
                "peer_id": 4,
                "message_seq": 5,
                "segments": [{"type": "text", "data": {"text": "yo"}}],
                "group_member": {
                    "nickname": "n",
                    "sex": "m",
                    "card": "c",
                    "level": "1",
                    "role": "member",
                    "title": "t",
                },
            },
        }
    )
    ev = asyncio.run(conn.recv())
    assert ev["post_type"] == "message"
    assert ev["message_type"] == "group"
    assert ev["message_id"] == str(msg_enid(0, 5, 3))
    assert ev["message"] == [{"type": "text", "data": {"text": "yo"}}]
    assert ev["sender"]["card"] == "c"


def test_recv_private_message():
    conn = _conn(
        {
            "type": "message_receive",
            "time": 1,
            "self_id": 2,
            "data": {
                "message_scene": "friend",
                "sender_id": 3,
                "peer_id": 0,
                "message_seq": 1,
                "segments": [],
                "friend": {"nickname": "n", "sex": "m"},
            },
        }
    )
    ev = asyncio.run(conn.recv())
    assert ev["post_type"] == "message"
    assert ev["message_type"] == "private"
    assert ev["sender"]["nickname"] == "n"


def test_recv_bot_offline():
    conn = _conn({"type": "bot_offline", "time": 1, "self_id": 2, "data": {}})
    with pytest.raises(BotOfflineError):
        asyncio.run(conn.recv())


def test_recv_unknown_event():
    conn = _conn({"type": "unknown_event", "time": 1, "self_id": 2, "data": {}})
    with pytest.raises(NotImplementedError):
        asyncio.run(conn.recv())


class MilkyText(MilkySegmentBase, st="text"):
    text: str


class MilkyAt(MilkySegmentBase, st="at"):
    qq: str


def test_milky_outgoing_seg_text():
    assert MilkyText("hi").milky_outgoing_seg() == {"type": "text", "data": {"text": "hi"}}


def test_milky_outgoing_seg_at():
    assert MilkyAt(qq="42").milky_outgoing_seg() == {"type": "mention", "data": {"user_id": "42"}}


def test_http_send_without_auth(monkeypatch):
    async def run():
        conn = MilkyHttpConnection("ws://example.com")

        class Rsp:
            def json(self):
                return {"status": "ok"}

        async def fake_post(url, json=None, headers=None):
            assert url == "ws://example.com/api/send_private_msg"
            assert headers is None
            return Rsp()

        import hyperot.LecAdapters.MilkyLib.translator as tr

        monkeypatch.setattr(tr, "httpx_post", fake_post)
        res = await conn.http_send("send_private_msg", {"user_id": 1})
        assert res == {"status": "ok"}

    asyncio.run(run())


def test_http_send_with_auth(monkeypatch):
    async def run():
        conn = MilkyHttpConnection("ws://example.com", auth="secret")

        class Rsp:
            def json(self):
                return {"status": "ok"}

        async def fake_post(url, json=None, headers=None):
            assert headers == {"Authorization": "Bearer secret"}
            return Rsp()

        import hyperot.LecAdapters.MilkyLib.translator as tr

        monkeypatch.setattr(tr, "httpx_post", fake_post)
        assert (await conn.http_send("send_private_msg", {"user_id": 1})) == {"status": "ok"}

    asyncio.run(run())
