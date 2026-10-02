import asyncio
import json
import re

import pytest

from hyperot import network
from hyperot.adapters.onebot import OneBotActions, OneBotListener
from hyperot.adapters.onebot.listener import reports
from hyperot.adapters.onebot.packet import Packet
from hyperot.common import Message
from hyperot.events import HyperListenerStartNotify
from hyperot.segments import Text
from hyperot.utils import errors


def _actions() -> OneBotActions:
    return OneBotActions(network.WebsocketConnection("ws://x"))


def _group_message() -> dict:
    return {
        "time": 1,
        "self_id": 100,
        "user_id": 3,
        "post_type": "message",
        "message_type": "group",
        "group_id": 4,
        "message_id": 9,
        "message": [{"type": "text", "data": {"text": "hi"}}],
        "sender": {"user_id": 3, "nickname": "n"},
    }


def test_packet_wire_format(monkeypatch):
    sent = []

    async def fake_send(payload: str):
        sent.append(json.loads(payload))

    connection = network.WebsocketConnection("ws://x")
    monkeypatch.setattr(connection, "send", fake_send)
    packet = Packet("send_msg", group_id=1, message=[{"type": "text", "data": {"text": "hi"}}])

    asyncio.run(packet.send_to(connection))

    assert re.fullmatch(r"send_msg_[0-9a-f]{8}", packet.echo)
    assert sent == [
        {
            "action": "send_msg",
            "params": {"group_id": 1, "message": [{"type": "text", "data": {"text": "hi"}}]},
            "echo": packet.echo,
        }
    ]


def test_action_round_trip_uses_the_matching_response(monkeypatch):
    captured = []

    async def fake_send_to(self, _connection):
        captured.append((self.endpoint, self.paras))
        await reports.put(self.echo, {"status": "ok", "retcode": 0, "data": {"message_id": 42}})

    monkeypatch.setattr(Packet, "send_to", fake_send_to)
    result = asyncio.run(_actions().send_msg(Message(Text("hi")), group_id=123))

    assert captured == [("send_msg", {"group_id": 123, "message": [{"type": "text", "data": {"text": "hi"}}]})]
    assert result.data.message_id == 42


def test_http_connection_routes_echo_responses(monkeypatch):
    class Response:
        def json(self):
            return {"status": "ok", "retcode": 0, "data": {}}

    calls = {}

    async def fake_post(url, json=None, headers=None):
        calls.update(url=url, json=json, headers=headers)
        return Response()

    monkeypatch.setattr(network, "httpx_post", fake_post)
    connection = network.HTTPConnection("http://127.0.0.1:5004", "http://127.0.0.1:8080", auth="tok")

    asyncio.run(connection.send("get_login_info", {}, "echo-1"))

    assert calls == {
        "url": "http://127.0.0.1:5004/get_login_info",
        "json": {},
        "headers": {"Authorization": "Bearer tok"},
    }
    assert asyncio.run(connection.recv()) == {"status": "ok", "retcode": 0, "data": {}, "echo": "echo-1"}


def test_listener_dispatches_events_and_routes_replies(monkeypatch):
    listener = OneBotListener()
    dispatched = []

    async def handler(event, _actions):
        dispatched.append(type(event).__name__)

    monkeypatch.setattr(listener, "handler", handler)
    actions = _actions()

    async def run():
        await listener._handler({"echo": "e1", "status": "ok", "retcode": 0, "data": {}}, actions)
        reply = await reports.get("e1")
        await listener._handler(
            {"post_type": "meta_event", "meta_event_type": "lifecycle", "time": 1, "self_id": 100},
            actions,
        )
        await listener._handler(
            {
                **_group_message(),
                "user_id": 100,
                "message_type": "private",
                "sender": {"user_id": 100, "nickname": "self"},
            },
            actions,
        )
        await listener._handler(_group_message(), actions)
        await listener._handler(HyperListenerStartNotify(time_now=1, notify_type="listener_start"), actions)
        return reply

    reply = asyncio.run(run())

    assert reply["echo"] == "e1"
    assert dispatched == ["GroupMessageEvent", "HyperListenerStartNotify"]


def test_listener_requires_a_handler():
    with pytest.raises(errors.ListenerNotRegisteredError):
        asyncio.run(OneBotListener().run())
