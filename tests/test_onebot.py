import asyncio
import json
import re

import pytest

from hyperot.common import Message
from hyperot.events import HyperListenerStartNotify
from hyperot.LecAdapters.OneBotLib.Res import SegmentBase as OneBotSegmentBase
from hyperot.LecAdapters.OneBotLib.Res import message_types as ob_message_types
from hyperot.segments import Forward, Node, Text
from hyperot.utils import errors


class _FakeWS:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload)

    async def recv(self) -> str:
        return self._payload


# ---------- Packet ----------


def test_packet_fields():
    from hyperot.LecAdapters.OneBotLib.Manager import Packet

    p = Packet("send_msg", group_id=1, message=[])
    assert p.endpoint == "send_msg"
    assert p.paras == {"group_id": 1, "message": []}
    assert re.fullmatch(r"send_msg_\d{4}", p.echo)


def test_packet_send_to_websocket(monkeypatch):
    from hyperot import network
    from hyperot.LecAdapters.OneBotLib.Manager import Packet

    sent = []
    conn = network.WebsocketConnection("ws://x")

    async def fake_send(payload: str):
        sent.append(json.loads(payload))

    monkeypatch.setattr(conn, "send", fake_send)
    p = Packet("send_msg", group_id=1, message=[{"type": "text", "data": {"text": "hi"}}])
    asyncio.run(p.send_to(conn))
    assert sent == [
        {
            "action": "send_msg",
            "params": {"group_id": 1, "message": [{"type": "text", "data": {"text": "hi"}}]},
            "echo": p.echo,
        }
    ]


def test_packet_send_to_http(monkeypatch):
    from hyperot import network
    from hyperot.LecAdapters.OneBotLib.Manager import Packet

    sent = []
    conn = network.HTTPConnection("http://x:5004", "http://listener:8080")

    async def fake_send(endpoint, data, echo):
        sent.append((endpoint, data, echo))

    monkeypatch.setattr(conn, "send", fake_send)
    p = Packet("get_login_info", no_cache=True)
    asyncio.run(p.send_to(conn))
    assert sent == [("get_login_info", {"no_cache": True}, p.echo)]


# ---------- WebsocketConnection ----------


def test_ws_raise_when_not_connected():
    from hyperot import network

    conn = network.WebsocketConnection("ws://x")
    with pytest.raises(RuntimeError):
        asyncio.run(conn.recv())
    with pytest.raises(RuntimeError):
        asyncio.run(conn.send("{}"))
    with pytest.raises(RuntimeError):
        asyncio.run(conn.close())


def test_ws_recv_parses_json():
    from hyperot import network

    conn = network.WebsocketConnection("ws://x")
    conn.ws = _FakeWS({"post_type": "meta_event", "time": 1})
    assert asyncio.run(conn.recv()) == {"post_type": "meta_event", "time": 1}


def test_ws_connect_passes_auth(monkeypatch):
    from hyperot import network

    captured = {}

    async def fake_wsc(url, header=None):
        captured["url"] = url
        captured["header"] = header
        return _FakeWS({})

    monkeypatch.setattr(network, "wsc", fake_wsc)
    conn = network.WebsocketConnection("ws://x", auth="secret")
    asyncio.run(conn.connect())
    assert captured == {"url": "ws://x", "header": {"Authorization": "Bearer secret"}}

    conn = network.WebsocketConnection("ws://x")
    asyncio.run(conn.connect())
    assert captured["header"] is None


# ---------- HTTPConnection ----------


def test_http_send_put_echo_response(monkeypatch):
    from hyperot import network

    class Rsp:
        def json(self):
            return {"status": "ok", "retcode": 0, "data": {}}

    calls = {}

    async def fake_post(url, json=None, data=None, headers=None):
        calls["url"] = url
        calls["headers"] = headers
        return Rsp()

    monkeypatch.setattr(network, "httpx_post", fake_post)
    conn = network.HTTPConnection("http://x:5004", "http://listener:8080", auth="tok")
    asyncio.run(conn.send("get_login_info", {}, "echo123"))
    res = conn.reports.get_nowait()
    assert res["echo"] == "echo123"
    assert calls["url"] == "http://x:5004/get_login_info"
    assert calls["headers"] == {"Authorization": "Bearer tok"}


# ---------- Actions ----------


def _actions():
    from hyperot import network
    from hyperot.LecAdapters import OneBot

    return OneBot.Actions(network.WebsocketConnection("ws://x")), OneBot


def _fake_send_to(captured, response):
    from hyperot.LecAdapters.OneBotLib import Manager as Mgr

    async def fake(self, connection):
        captured.append((self.endpoint, self.paras))
        await Mgr.reports.put(self.echo, response)

    return fake


def test_actions_send_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {"message_id": 42}}),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.send_msg(Message(Text("hi")), group_id=123))
    assert captured[-1] == ("send_msg", {"group_id": 123, "message": [{"type": "text", "data": {"text": "hi"}}]})
    assert ret.data.message_id == 42

    asyncio.run(actions.send_msg("plain", user_id=321))
    assert captured[-1] == (
        "send_msg",
        {"user_id": 321, "message": [{"type": "text", "data": {"text": "plain"}}]},
    )

    with pytest.raises(errors.ArgsInvalidError):
        asyncio.run(actions.send_msg("x"))


def test_actions_group_private_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    asyncio.run(actions.send_group_msg("hi", group_id=1))
    assert captured[-1][1] == {"group_id": 1, "message": [{"type": "text", "data": {"text": "hi"}}]}

    asyncio.run(actions.send_private_msg("hi", user_id=2))
    assert captured[-1][1] == {"user_id": 2, "message": [{"type": "text", "data": {"text": "hi"}}]}


def test_actions_del_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    asyncio.run(actions.del_msg(123))
    assert captured == [("delete_msg", {"message_id": 123})]


def test_actions_kick_ban(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    asyncio.run(actions.set_group_kick(4, 3))
    asyncio.run(actions.set_group_ban(4, 3))
    asyncio.run(actions.set_group_ban(4, 3, duration=120))
    assert captured == [
        ("set_group_kick", {"group_id": 4, "user_id": 3}),
        ("set_group_ban", {"group_id": 4, "user_id": 3, "duration": 60}),
        ("set_group_ban", {"group_id": 4, "user_id": 3, "duration": 120}),
    ]


def test_actions_login_and_version(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    captured.clear()
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {"status": "ok", "retcode": 0, "data": {"user_id": 123, "nickname": "bot"}},
        ),
    )
    login = asyncio.run(actions.get_login_info())
    assert captured == [("get_login_info", {})]
    assert login.data.user_id == 123
    assert login.data.nickname == "bot"

    captured.clear()
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {
                "status": "ok",
                "retcode": 0,
                "data": {"app_name": "OneBot", "app_version": "1.0", "protocol_version": "v11"},
            },
        ),
    )
    ver = asyncio.run(actions.get_version_info())
    assert captured == [("get_version_info", {})]
    assert ver.data.app_name == "OneBot"
    assert ver.data.protocol_version == "v11"


def test_actions_send_forward_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {"res_id": "fwd1"}}),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.send_forward_msg(Message(Text("hi"))))
    assert captured == [("send_forward_msg", {"messages": [{"type": "text", "data": {"text": "hi"}}]})]
    assert ret.data.res_id == "fwd1"


def test_actions_get_forward_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "message": [
                        {
                            "type": "node",
                            "data": {
                                "user_id": "1",
                                "nickname": "n",
                                "content": [{"type": "text", "data": {"text": "hi"}}],
                            },
                        }
                    ]
                },
            },
        ),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.get_forward_msg("fwd1"))
    assert captured == [("get_forward_msg", {"id": "fwd1"})]
    assert isinstance(ret.data[0], Node)
    assert str(ret.data[0].content) == "hi"


def test_actions_forward_solve(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "message": [
                        {
                            "type": "node",
                            "data": {
                                "user_id": "1",
                                "nickname": "n",
                                "content": [{"type": "text", "data": {"text": "hi"}}],
                            },
                        }
                    ]
                },
            },
        ),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.forward_solve(Message(Forward(content=[], id="fwd1"))))
    assert captured == [("get_forward_msg", {"id": "fwd1"})]
    assert str(ret[0].content) == "hi"

    with pytest.raises(ValueError):
        asyncio.run(actions.forward_solve(Message(Text("hi"))))


def test_actions_send_group_forward_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {"res_id": "fwd2"}}),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.send_group_forward_msg(4, Message(Text("hi"))))
    assert captured == [
        ("send_group_forward_msg", {"group_id": 4, "messages": [{"type": "text", "data": {"text": "hi"}}]})
    ]
    assert ret.data.res_id == "fwd2"


def test_actions_group_add_request(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    asyncio.run(actions.set_group_add_request("f1", "add", True))
    asyncio.run(actions.set_group_add_request("f1", "invite", False, reason="no"))
    assert captured == [
        ("set_group_add_request", {"flag": "f1", "sub_type": "add", "approve": True, "reason": "Not Mentioned"}),
        ("set_group_add_request", {"flag": "f1", "sub_type": "invite", "approve": False, "reason": "no"}),
    ]


def test_actions_get_stranger_info(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {"status": "ok", "retcode": 0, "data": {"user_id": 3, "nickname": "n", "sex": "male", "age": 20}},
        ),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.get_stranger_info(3))
    assert captured == [("get_stranger_info", {"user_id": 3, "no_cache": True})]
    assert ret.data.nickname == "n"
    assert ret.data.age == 20


def test_actions_get_group_member_info(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "group_id": 4,
                    "user_id": 3,
                    "nickname": "n",
                    "card": "c",
                    "sex": "male",
                    "age": 20,
                    "area": "a",
                    "join_time": 1,
                    "last_sent_time": 2,
                    "level": "1",
                    "role": "admin",
                    "unfriendly": False,
                    "title": "t",
                    "title_expire_time": 0,
                    "card_changeable": False,
                },
            },
        ),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.get_group_member_info(4, 3))
    assert captured == [("get_group_member_info", {"group_id": 4, "user_id": 3, "no_cache": True})]
    assert ret.data.nickname == "n"
    assert ret.data.role == "admin"
    assert ret.data.unfriendly is False
    assert ret.data.card == "c"


def test_actions_get_group_info(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {
                "status": "ok",
                "retcode": 0,
                "data": {"group_id": 4, "group_name": "测试群", "member_count": 7, "max_member_count": 200},
            },
        ),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.get_group_info(4))
    assert captured == [("get_group_info", {"group_id": 4, "no_cache": True})]
    assert ret.data.group_name == "测试群"
    assert ret.data.member_count == 7


def test_actions_get_status(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    ret = asyncio.run(actions.get_status())
    assert captured == [("get_status", {})]
    assert ret.status == "ok"


def test_actions_essence_title(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    asyncio.run(actions.set_essence_msg(9))
    asyncio.run(actions.set_group_special_title(4, 3, "title"))
    assert captured == [
        ("set_essence_msg", {"message_id": 9}),
        ("set_group_special_title", {"group_id": 4, "user_id": 3, "special_title": "title"}),
    ]


def test_actions_get_msg(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(
        Mgr.Packet,
        "send_to",
        _fake_send_to(
            captured,
            {
                "status": "ok",
                "retcode": 0,
                "data": {
                    "time": 1,
                    "message_type": "group",
                    "message_id": 9,
                    "real_id": 9,
                    "sender": {
                        "user_id": 3,
                        "nickname": "n",
                        "sex": "male",
                        "age": 0,
                        "card": "c",
                        "area": "a",
                        "level": "1",
                        "role": "member",
                        "title": "t",
                    },
                    "message": [{"type": "text", "data": {"text": "hi"}}],
                },
            },
        ),
    )
    actions, _ = _actions()

    ret = asyncio.run(actions.get_msg(9))
    assert captured == [("get_msg", {"message_id": 9})]
    assert ret.data.message_type == "group"
    assert ret.data.sender.card == "c"
    assert str(ret.data.message) == "hi"


def test_actions_send_callback(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    asyncio.run(actions.send_callback(4, 2, {"a": 1}))
    assert captured == [("send_group_bot_callback", {"group_id": 4, "bot_id": 2, "a": 1})]


def test_actions_custom(monkeypatch):
    import hyperot.LecAdapters.OneBotLib.Manager as Mgr

    captured = []
    monkeypatch.setattr(Mgr.Packet, "send_to", _fake_send_to(captured, {"status": "ok", "retcode": 0, "data": {}}))
    actions, _ = _actions()

    echo = asyncio.run(actions.custom.get_cookies(domain="docs.qq.com"))
    assert captured == [("get_cookies", {"domain": "docs.qq.com"})]
    assert re.fullmatch(r"get_cookies_\d{4}", echo)


# ---------- __handler ----------


def test_handler_echo_goes_to_reports(monkeypatch):
    from hyperot.LecAdapters import OneBot
    from hyperot.LecAdapters.OneBotLib import Manager as Mgr

    called = []

    async def fake_handler(event, actions):
        called.append(event)

    monkeypatch.setattr(OneBot, "handler", fake_handler)
    actions, _ = _actions()

    async def run():
        await OneBot.__handler({"echo": "e1", "status": "ok", "retcode": 0, "data": {}}, actions)
        return await Mgr.reports.get("e1")

    res = asyncio.run(run())
    assert res["echo"] == "e1"
    assert called == []


def test_handler_ignores_meta_and_self(monkeypatch):
    from hyperot.LecAdapters import OneBot

    called = []

    async def fake_handler(event, actions):
        called.append(event)

    monkeypatch.setattr(OneBot, "handler", fake_handler)
    actions, _ = _actions()

    asyncio.run(
        OneBot.__handler(
            {"post_type": "meta_event", "meta_event_type": "lifecycle", "time": 1, "self_id": 100},
            actions,
        )
    )
    asyncio.run(
        OneBot.__handler(
            {
                "time": 1,
                "self_id": 100,
                "user_id": 100,
                "post_type": "message",
                "message_type": "private",
                "message": [],
                "sender": {"user_id": 100, "nickname": "self"},
            },
            actions,
        )
    )
    assert called == []


def test_handler_dispatches_event(monkeypatch):
    from hyperot.LecAdapters import OneBot

    called = []

    async def fake_handler(event, actions):
        called.append(type(event).__name__)

    monkeypatch.setattr(OneBot, "handler", fake_handler)
    actions, _ = _actions()

    asyncio.run(
        OneBot.__handler(
            {
                "time": 1,
                "self_id": 100,
                "user_id": 3,
                "post_type": "message",
                "message_type": "group",
                "group_id": 4,
                "message": [{"type": "text", "data": {"text": "hi"}}],
                "sender": {"user_id": 3, "nickname": "n"},
            },
            actions,
        )
    )
    assert called == ["GroupMessageEvent"]


def test_handler_hypernotify(monkeypatch):
    from hyperot.LecAdapters import OneBot

    called = []

    async def fake_handler(event, actions):
        called.append(type(event).__name__)

    monkeypatch.setattr(OneBot, "handler", fake_handler)
    actions, _ = _actions()

    asyncio.run(OneBot.__handler(HyperListenerStartNotify(time_now=1, notify_type="listener_start"), actions))
    assert called == ["HyperListenerStartNotify"]


# ---------- run() ----------


def test_run_requires_registered_handler():
    from hyperot.LecAdapters import OneBot

    with pytest.raises(errors.ListenerNotRegisteredError):
        asyncio.run(OneBot.run())


# ---------- OneBotLib.Res ----------


class OneBotText(OneBotSegmentBase, st="ob_text", su="<text>"):
    text: str


class OneBotAt(OneBotSegmentBase, st="ob_at", su="@<qq>"):
    qq: str


class WithDefault(OneBotSegmentBase, st="ob_default", su="[Default: <flag>]"):
    flag: str = "d"


class Coerced(OneBotSegmentBase, st="ob_coerced", su=""):
    n: int


def test_res_registers_and_serializes():
    assert ob_message_types["ob_text"]["type"] is OneBotText
    assert ob_message_types["ob_text"]["args"] == ["text"]
    assert OneBotText("hi").to_json() == {"type": "ob_text", "data": {"text": "hi"}}
    assert str(OneBotText("hi")) == "hi"
    assert str(OneBotAt(qq="1")) == "@1"
    assert str(WithDefault()) == "[Default: d]"


def test_res_kwargs_type_coercion():
    assert Coerced(n="42").to_json() == {"type": "ob_coerced", "data": {"n": 42}}


def test_res_class_default_value():
    assert WithDefault().to_json() == {"type": "ob_default", "data": {"flag": "d"}}


def test_res_equality():
    assert OneBotText("hi") == OneBotText("hi")
    assert OneBotText("hi") != OneBotText("yo")
