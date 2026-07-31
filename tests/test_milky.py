import asyncio
import json

import pytest

from hyperot.common import Message
from hyperot.LecAdapters.MilkyLib.Res import SegmentBase as MilkySegmentBase
from hyperot.LecAdapters.MilkyLib.translator import (
    MilkyHttpConnection,
    MilkyOutGoingSegBuilder,
    message_translator,
    milky_seg_from_dict,
    msg_deid,
    msg_enid,
    node_list_to_milky_forward,
)
from hyperot.segments import At, Text
from hyperot.utils import errors


def test_msg_enid_deid_roundtrip():
    for scene, seq, peer in [(0, 1, 123), (1, 42, 999), (0, 0, 1)]:
        assert msg_deid(msg_enid(scene, seq, peer)) == (scene, seq, peer)


def test_message_translator_basic():
    ob = message_translator(
        [
            {"type": "text", "data": {"text": "hi"}},
            {"type": "image", "data": {"temp_url": "http://a/b.png"}},
            {"type": "mention", "data": {"user_id": 123}},
            {"type": "mention_all", "data": {}},
        ],
        9,
        1,
    )
    assert ob == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "image", "data": {"file": "http://a/b.png", "url": "http://a/b.png", "summary": "[Image]"}},
        {"type": "at", "data": {"qq": 123}},
        {"type": "at", "data": {"qq": "all"}},
    ]


def test_message_translator_reply():
    ob = message_translator([{"type": "reply", "data": {"message_seq": 42}}], 9, 1)
    assert ob == [{"type": "reply", "data": {"id": str(msg_enid(1, 42, 9))}}]


def test_message_translator_media():
    ob = message_translator(
        [
            {"type": "face", "data": {"face_id": "1"}},
            {"type": "record", "data": {"temp_url": "http://a/r.mp3"}},
            {"type": "video", "data": {"temp_url": "http://a/v.mp4"}},
            {"type": "forward", "data": {"forward_id": "fwd1"}},
        ],
        9,
    )
    assert ob == [
        {"type": "face", "data": {"id": "1"}},
        {"type": "record", "data": {"file": "http://a/r.mp3", "url": "http://a/r.mp3"}},
        {"type": "video", "data": {"file": "http://a/v.mp4", "url": "http://a/v.mp4"}},
        {"type": "forward", "data": {"id": "fwd1"}},
    ]


def test_message_translator_market_face_and_apps():
    ob = message_translator(
        [
            {"type": "market_face", "data": {"emoji_id": "e1", "emoji_package_id": 7, "key": "k"}},
            {"type": "light_app", "data": {"app_name": "app", "json_payload": "{}"}},
            {"type": "xml", "data": {"service_id": 2, "xml_payload": "<x/>"}},
        ],
        9,
    )
    assert ob[0] == {"type": "mface", "data": {"face_id": "e1", "tab_id": "7", "key": "k"}}
    assert ob[1]["type"] == "json"
    assert ob[2]["type"] == "json"


def test_message_translator_unsupported_segments_skipped():
    ob = message_translator(
        [
            {"type": "file", "data": {"file_id": "f"}},
            {"type": "unknown_seg", "data": {}},
            {"type": "text", "data": {"text": "x"}},
        ],
        9,
    )
    assert ob == [{"type": "text", "data": {"text": "x"}}]


def test_outgoing_builder():
    b = MilkyOutGoingSegBuilder()
    b.text("hi").mention(1).mention_all().face("f").reply(3)
    assert b.build() == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "mention", "data": {"user_id": 1}},
        {"type": "mention_all", "data": {}},
        {"type": "face", "data": {"face_id": "f"}},
        {"type": "reply", "data": {"message_seq": 3}},
    ]


def test_milky_seg_from_dict():
    assert milky_seg_from_dict({"type": "text", "data": {"text": "hi"}}) == {"type": "text", "data": {"text": "hi"}}
    assert milky_seg_from_dict({"type": "at", "data": {"qq": "42"}}) == {"type": "mention", "data": {"user_id": 42}}
    assert milky_seg_from_dict({"type": "at", "data": {"qq": "all"}}) == {"type": "mention_all", "data": {}}
    assert milky_seg_from_dict({"type": "face", "data": {"id": "1"}}) == {
        "type": "face",
        "data": {"face_id": "1", "is_large": False},
    }
    assert milky_seg_from_dict({"type": "reply", "data": {"id": str(msg_enid(1, 42, 9))}}) == {
        "type": "reply",
        "data": {"message_seq": 42},
    }


def test_milky_seg_from_dict_forward():
    content = Message(Text("hi"))
    node = {"type": "node", "data": {"user_id": "1", "nickname": "n", "content": content}}
    seg = milky_seg_from_dict({"type": "forward", "data": {"content": [node]}})
    assert seg == {
        "type": "forward",
        "data": {
            "messages": [
                {
                    "user_id": "1",
                    "sender_name": "n",
                    "segments": [{"type": "text", "data": {"text": "hi"}}],
                }
            ]
        },
    }


def test_node_list_to_milky_forward():
    content = Message(Text("hi"), At(qq="2"))
    msg = Message({"type": "node", "data": {"user_id": "1", "nickname": "n", "content": content}})
    assert node_list_to_milky_forward(msg) == {
        "type": "forward",
        "data": {
            "messages": [
                {
                    "user_id": "1",
                    "sender_name": "n",
                    "segments": [
                        {"type": "text", "data": {"text": "hi"}},
                        {"type": "mention", "data": {"user_id": 2}},
                    ],
                }
            ]
        },
    }


class _FakeWS:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload)

    async def recv(self) -> str:
        return self._payload


def _conn(payload: dict) -> MilkyHttpConnection:
    conn = MilkyHttpConnection("ws://example.com")
    conn.ws = _FakeWS(payload)
    return conn


def _event(event_type: str, data: dict) -> dict:
    return {"event_type": event_type, "time": 1, "self_id": 2, "data": data}


def test_recv_group_message():
    conn = _conn(
        _event(
            "message_receive",
            {
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
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["post_type"] == "message"
    assert ev["message_type"] == "group"
    assert ev["message_id"] == str(msg_enid(1, 5, 4))
    assert ev["message"] == [{"type": "text", "data": {"text": "yo"}}]
    assert ev["sender"]["card"] == "c"


def test_recv_private_message():
    conn = _conn(
        _event(
            "message_receive",
            {
                "message_scene": "friend",
                "sender_id": 3,
                "peer_id": 3,
                "message_seq": 1,
                "segments": [],
                "friend": {"nickname": "n", "sex": "m"},
            },
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["message_type"] == "private"
    assert ev["message_id"] == str(msg_enid(0, 1, 3))
    assert ev["sender"]["nickname"] == "n"


def test_recv_temp_message_as_private():
    conn = _conn(
        _event(
            "message_receive",
            {
                "message_scene": "temp",
                "sender_id": 3,
                "peer_id": 4,
                "message_seq": 1,
                "segments": [{"type": "text", "data": {"text": "t"}}],
            },
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["message_type"] == "private"
    assert ev["user_id"] == 3


def test_recv_bot_offline():
    conn = _conn(_event("bot_offline", {"reason": "网络断开"}))
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["post_type"] == "notice"
    assert ev["notice_type"] == "bot_online"
    assert ev["reason"] == "网络断开"


def test_recv_message_recall():
    conn = _conn(
        _event(
            "message_recall",
            {"message_scene": "group", "peer_id": 4, "message_seq": 5, "sender_id": 3, "operator_id": 6},
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["notice_type"] == "group_recall"
    assert ev["group_id"] == 4
    assert ev["message_id"] == "5"
    assert ev["operator_id"] == 6

    conn = _conn(
        _event(
            "message_recall",
            {"message_scene": "friend", "peer_id": 3, "message_seq": 5, "sender_id": 3, "operator_id": 3},
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["notice_type"] == "friend_recall"
    assert ev["message_id"] == 5


def test_recv_group_admin_change():
    conn = _conn(_event("group_admin_change", {"group_id": 4, "user_id": 3, "operator_id": 6, "is_set": True}))
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["notice_type"] == "group_admin"
    assert ev["sub_type"] == "set"

    conn = _conn(_event("group_admin_change", {"group_id": 4, "user_id": 3, "operator_id": 6, "is_set": False}))
    assert asyncio.run(conn.recv())["sub_type"] == "unset"


def test_recv_group_essence_message_change():
    conn = _conn(
        _event("group_essence_message_change", {"group_id": 4, "message_seq": 5, "operator_id": 6, "is_set": True})
    )
    ev = asyncio.run(conn.recv())
    assert ev is not None
    assert ev["notice_type"] == "essence"
    assert ev["sub_type"] == "add"
    assert ev["message_id"] == "5"


def test_recv_group_member_increase_decrease():
    conn = _conn(_event("group_member_increase", {"group_id": 4, "user_id": 3, "operator_id": 6}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_increase"
    assert ev["sub_type"] == "approve"
    assert ev["operator_id"] == 6

    conn = _conn(_event("group_member_increase", {"group_id": 4, "user_id": 3, "invitor_id": 7}))
    assert asyncio.run(conn.recv())["sub_type"] == "invite"

    conn = _conn(_event("group_member_decrease", {"group_id": 4, "user_id": 3, "operator_id": 6}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_decrease"
    assert ev["sub_type"] == "kick"

    conn = _conn(_event("group_member_decrease", {"group_id": 4, "user_id": 3}))
    assert asyncio.run(conn.recv())["sub_type"] == "leave"


def test_recv_group_mute_and_whole_mute():
    conn = _conn(_event("group_mute", {"group_id": 4, "user_id": 3, "operator_id": 6, "duration": 60}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_ban"
    assert ev["sub_type"] == "ban"
    assert ev["duration"] == 60

    conn = _conn(_event("group_mute", {"group_id": 4, "user_id": 3, "operator_id": 6, "duration": 0}))
    assert asyncio.run(conn.recv())["sub_type"] == "lift_ban"

    conn = _conn(_event("group_whole_mute", {"group_id": 4, "operator_id": 6, "is_mute": True}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_whole_mute"
    assert ev["sub_type"] == "mute"

    conn = _conn(_event("group_whole_mute", {"group_id": 4, "operator_id": 6, "is_mute": False}))
    assert asyncio.run(conn.recv())["sub_type"] == "unmute"


def test_recv_group_name_change_and_invitation():
    conn = _conn(_event("group_name_change", {"group_id": 4, "new_group_name": "新名", "operator_id": 6}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_name_change"
    assert ev["new_group_name"] == "新名"

    conn = _conn(
        _event("group_invitation", {"group_id": 4, "invitation_seq": 9, "initiator_id": 3, "source_group_id": 8})
    )
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_invitation"
    assert ev["invitation_seq"] == 9
    assert ev["source_group_id"] == 8


def test_recv_file_upload():
    conn = _conn(
        _event(
            "group_file_upload",
            {"group_id": 4, "user_id": 3, "file_id": "f1", "file_name": "a.txt", "file_size": 10},
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "group_upload"
    assert ev["file"] == {"id": "f1", "name": "a.txt", "size": 10, "busid": 0}

    conn = _conn(
        _event(
            "friend_file_upload",
            {"user_id": 3, "file_id": "f2", "file_name": "b.txt", "file_size": 20, "file_hash": "h"},
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "friend_upload"
    assert ev["file"] == {"id": "f2", "name": "b.txt", "size": 20, "busid": 0, "hash": "h"}


def test_recv_group_message_reaction():
    conn = _conn(
        _event(
            "group_message_reaction", {"group_id": 4, "user_id": 3, "message_seq": 5, "face_id": "102", "is_add": True}
        )
    )
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "reaction"
    assert ev["sub_type"] == "add"
    assert ev["message_id"] == "5"
    assert ev["code"] == 102


def test_recv_nudge():
    conn = _conn(_event("group_nudge", {"group_id": 4, "sender_id": 3, "receiver_id": 2}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "notify"
    assert ev["sub_type"] == "poke"
    assert ev["target_id"] == 2
    assert ev["user_id"] == 3

    conn = _conn(_event("friend_nudge", {"user_id": 3, "is_self_send": False, "is_self_receive": True}))
    ev = asyncio.run(conn.recv())
    assert ev["notice_type"] == "notify"
    assert ev["sub_type"] == "poke"
    assert ev["target_id"] == 2


def test_recv_requests():
    conn = _conn(_event("friend_request", {"initiator_id": 3, "initiator_uid": "uid3", "comment": "hi", "via": ""}))
    ev = asyncio.run(conn.recv())
    assert ev["post_type"] == "request"
    assert ev["request_type"] == "friend"
    assert ev["flag"] == "uid3"
    assert ev["user_id"] == 3

    conn = _conn(
        _event("group_join_request", {"group_id": 4, "notification_seq": 9, "initiator_id": 3, "comment": "add me"})
    )
    ev = asyncio.run(conn.recv())
    assert ev["post_type"] == "request"
    assert ev["request_type"] == "group"
    assert ev["sub_type"] == "add"
    assert ev["flag"] == "4:9"
    assert ev["comment"] == "add me"

    conn = _conn(_event("group_invited_join_request", {"group_id": 4, "notification_seq": 9, "initiator_id": 3}))
    ev = asyncio.run(conn.recv())
    assert ev["request_type"] == "group"
    assert ev["sub_type"] == "invite"
    assert ev["flag"] == "4:9"


def test_recv_unknown_event_returns_none():
    conn = _conn(_event("peer_pin_change", {"message_scene": "friend", "peer_id": 3, "is_pinned": True}))
    assert asyncio.run(conn.recv()) is None


def test_http_send_url_and_auth(monkeypatch):
    calls = {}

    async def fake_post(url, json=None, headers=None):
        calls["url"] = url
        calls["headers"] = headers

        class Rsp:
            def json(self):
                return {"status": "ok", "retcode": 0, "data": {"message_seq": 1, "time": 1}}

        return Rsp()

    import hyperot.LecAdapters.MilkyLib.translator as tr

    monkeypatch.setattr(tr, "httpx_post", fake_post)
    conn = MilkyHttpConnection("ws://example.com", auth="secret")
    res = asyncio.run(conn.http_send("send_private_msg", {"user_id": 1}))
    assert res["data"]["message_seq"] == 1
    assert calls["url"] == "http://example.com/api/send_private_msg"
    assert calls["headers"] == {"Authorization": "Bearer secret"}


def test_http_send_without_auth(monkeypatch):
    calls = {}

    async def fake_post(url, json=None, headers=None):
        calls["url"] = url
        calls["headers"] = headers

        class Rsp:
            def json(self):
                return {"status": "ok", "retcode": 0, "data": {}}

        return Rsp()

    import hyperot.LecAdapters.MilkyLib.translator as tr

    monkeypatch.setattr(tr, "httpx_post", fake_post)
    conn = MilkyHttpConnection("ws://example.com")
    res = asyncio.run(conn.http_send("get_login_info", {}))
    assert res["status"] == "ok"
    assert calls["url"] == "http://example.com/api/get_login_info"
    assert calls["headers"] is None


class MilkyText(MilkySegmentBase, st="text"):
    text: str


class MilkyAt(MilkySegmentBase, st="at"):
    qq: str


class MilkyImage(MilkySegmentBase, st="image"):
    file: str
    summary: str = "[Image]"


def test_milky_outgoing_seg_text():
    assert MilkyText("hi").milky_outgoing_seg() == {"type": "text", "data": {"text": "hi"}}


def test_milky_outgoing_seg_at():
    assert MilkyAt(qq="42").milky_outgoing_seg() == {"type": "mention", "data": {"user_id": 42}}
    assert MilkyAt(qq="all").milky_outgoing_seg() == {"type": "mention_all", "data": {}}


def test_milky_outgoing_seg_image():
    assert MilkyImage(file="http://a/b.png").milky_outgoing_seg() == {
        "type": "image",
        "data": {"uri": "http://a/b.png", "summary": "[Image]", "sub_type": "normal"},
    }


def _actions() -> tuple:
    from hyperot.LecAdapters import Milky

    return Milky.Actions(MilkyHttpConnection("ws://example.com")), Milky


def test_actions_send_msg(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    captured = {}

    async def fake_send_to(self, connection):
        captured["endpoint"] = self.endpoint
        captured["paras"] = self.paras
        return {"status": "ok", "retcode": 0, "data": {"message_seq": 7, "time": 1}}

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    ret = asyncio.run(actions.send_msg(MilkyText("hi"), group_id=123))
    assert captured["endpoint"] == "send_group_message"
    assert captured["paras"] == {"group_id": 123, "message": [{"type": "text", "data": {"text": "hi"}}]}
    assert ret.data.message_id == msg_enid(1, 7, 123)

    asyncio.run(actions.send_msg(MilkyText("hi"), user_id=321))
    assert captured["endpoint"] == "send_private_message"
    assert captured["paras"] == {"user_id": 321, "message": [{"type": "text", "data": {"text": "hi"}}]}

    with pytest.raises(errors.ArgsInvalidError):
        asyncio.run(actions.send_msg(MilkyText("hi")))


def test_actions_del_msg(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    captured = []

    async def fake_send_to(self, connection):
        captured.append((self.endpoint, self.paras))
        return {"status": "ok", "retcode": 0, "data": {}}

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    asyncio.run(actions.del_msg(msg_enid(1, 5, 4)))
    asyncio.run(actions.del_msg(msg_enid(0, 5, 3)))
    assert captured == [
        ("recall_group_message", {"group_id": 4, "message_seq": 5}),
        ("recall_private_message", {"user_id": 3, "message_seq": 5}),
    ]


def test_actions_set_group_add_request(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    captured = []

    async def fake_send_to(self, connection):
        captured.append((self.endpoint, self.paras))
        return {"status": "ok", "retcode": 0, "data": {}}

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    asyncio.run(actions.set_group_add_request("4:9", "add", True))
    asyncio.run(actions.set_group_add_request("4:9", "invite", False, reason="no"))
    assert captured == [
        ("accept_group_request", {"notification_seq": 9, "notification_type": "join_request", "group_id": 4}),
        (
            "reject_group_request",
            {"notification_seq": 9, "notification_type": "invited_join_request", "group_id": 4, "reason": "no"},
        ),
    ]


def test_actions_get_login_info_and_version(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    captured = []

    async def fake_send_to(self, connection):
        captured.append(self.endpoint)
        if self.endpoint == "get_login_info":
            return {"status": "ok", "retcode": 0, "data": {"uin": 123, "nickname": "bot"}}
        return {
            "status": "ok",
            "retcode": 0,
            "data": {"impl_name": "MilkyImpl", "impl_version": "1.0", "milky_version": "1.2"},
        }

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    login = asyncio.run(actions.get_login_info())
    assert login.data.user_id == 123
    assert login.data.nickname == "bot"

    ver = asyncio.run(actions.get_version_info())
    assert ver.data.app_name == "MilkyImpl"
    assert ver.data.protocol_version == "1.2"


def test_actions_custom(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    captured = []

    async def fake_send_to(self, connection):
        captured.append((self.endpoint, self.paras))
        return {"status": "ok", "retcode": 0, "data": {"groups": []}}

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    res = asyncio.run(actions.custom.get_group_member_list(group_id=1))
    assert res == {"groups": []}
    assert captured == [("get_group_member_list", {"group_id": 1})]


def test_actions_get_group_member_info(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    async def fake_send_to(self, connection):
        return {
            "status": "ok",
            "retcode": 0,
            "data": {
                "member": {
                    "group_id": 4,
                    "user_id": 3,
                    "nickname": "n",
                    "card": "c",
                    "sex": "male",
                    "role": "member",
                    "title": "t",
                }
            },
        }

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    ret = asyncio.run(actions.get_group_member_info(4, 3))
    assert ret.data.user_id == 3
    assert ret.data.nickname == "n"
    assert ret.data.area == ""
    assert ret.data.unfriendly is False


def test_actions_get_group_info(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    async def fake_send_to(self, connection):
        return {
            "status": "ok",
            "retcode": 0,
            "data": {"group": {"group_id": 4, "group_name": "测试群", "member_count": 7, "max_member_count": 200}},
        }

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    ret = asyncio.run(actions.get_group_info(4))
    assert ret.data.group_name == "测试群"
    assert ret.data.member_count == 7
    assert ret.data.max_member_count == 200


def test_http_send_non_json_response(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.translator as tr

    class Rsp:
        status_code = 500
        text = ""

        def json(self):
            raise json.JSONDecodeError("Expecting value", "", 0)

    async def fake_post(url, json=None, headers=None):
        return Rsp()

    monkeypatch.setattr(tr, "httpx_post", fake_post)
    conn = MilkyHttpConnection("ws://example.com")
    with pytest.raises(errors.ApiError):
        asyncio.run(conn.http_send("some_api", {}))


def test_actions_send_forward_unsupported(monkeypatch):
    import hyperot.LecAdapters.MilkyLib.Manager as Mgr

    async def fake_send_to(self, connection):
        return {"status": "ok", "retcode": 0, "data": {}}

    monkeypatch.setattr(Mgr.Packet, "send_to", fake_send_to)
    actions, _ = _actions()

    with pytest.raises(NotImplementedError):
        asyncio.run(actions.send_forward_msg(Message(Text("x"))))
    with pytest.raises(NotImplementedError):
        asyncio.run(actions.send_callback(1, 2, {}))
