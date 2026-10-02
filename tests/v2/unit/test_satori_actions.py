import asyncio
from typing import Any

import pytest
from hyperot_adapter_satori.actions import (
    ChannelIndex,
    SatoriActions,
    SatoriChannelListAction,
    SatoriMessageListAction,
    SatoriUploadFileAction,
)
from hyperot_adapter_satori.segments import SatoriSegmentCodec

from hyperot.v2.actions import (
    ApproveFriendRequestAction,
    ApproveGroupRequestAction,
    DownloadFileAction,
    FetchMessageAction,
    GetGroupListAction,
    GetGroupMemberAction,
    MuteMemberAction,
    PokeAction,
    ReactMessageAction,
    RecallMessageAction,
    RejectGroupRequestAction,
    SendMessageAction,
    SetGroupMuteAction,
    SetMemberRoleAction,
    UnmuteMemberAction,
)
from hyperot.v2.adapter import ActionRegistry
from hyperot.v2.common import CapabilityNotSupportedError, MemberRole, SceneType
from hyperot.v2.messages import Mention, Message, Text


class FakeTransport:
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []

    def resolve_identity(self) -> tuple[str, str]:
        return "qq", "10000"

    def logins(self) -> list[dict]:
        return [{"platform": "qq", "user": {"id": "10000"}, "status": 1}]

    def login_status(self, platform: str, user_id: str) -> int | None:
        return 1

    def proxy_urls(self) -> list[str]:
        return ["https://cdn.example.com/"]

    def proxy_url(self, url: str) -> str:
        return f"http://127.0.0.1:5140/proxy/{url}"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def receive(self) -> dict:
        return {}

    async def call(self, route: str, params: dict, timeout: float):
        self.calls.append((route, params))
        value = self.responses.get(route, {})
        return value(params) if callable(value) else value

    async def upload(self, files, timeout: float) -> dict[str, str]:
        self.calls.append(("upload.create", {}))
        return {name: f"internal:satori/{name}" for name, *_ in files}


def _registry(responses: dict[str, Any] | None = None) -> tuple[FakeTransport, ActionRegistry]:
    transport = FakeTransport(responses)
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    return transport, registry


def _run(registry: ActionRegistry, action) -> Any:
    async def scenario():
        return await registry.get(type(action))(action)

    return asyncio.run(scenario())


def test_send_to_a_channel_scene():
    transport = FakeTransport({"message.create": [{"id": "m1"}]})
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0, channel_index=ChannelIndex()).register_all(registry)
    result = _run(registry, SendMessageAction(scene_type=SceneType.GUILD, scene_id="chan1", message=Message(Text(text="hi"))))
    assert result.message_id == "chan1:m1"
    assert transport.calls == [("message.create", {"channel_id": "chan1", "content": "hi"})]


def test_send_to_a_guild_resolves_its_channel():
    transport = FakeTransport({"channel.list": {"data": [{"id": "chan1", "type": 0, "name": "general"}], "next": None},
                                "message.create": [{"id": "m9"}]})
    registry = ActionRegistry()
    actions = SatoriActions(transport, SatoriSegmentCodec(), 30.0)
    actions.register_all(registry)
    result = _run(registry, SendMessageAction(scene_type=SceneType.GROUP, scene_id="guild1", message=Message(Text(text="hi"))))
    assert ("message.create", {"channel_id": "chan1", "content": "hi"}) in transport.calls
    assert result.message_id == "chan1:m9"


def test_send_to_a_user_creates_a_private_channel():
    transport = FakeTransport(
        {
            "user.channel.create": {"id": "direct1", "type": 1},
            "message.create": [{"id": "m2"}],
        }
    )
    registry = ActionRegistry()
    actions = SatoriActions(transport, SatoriSegmentCodec(), 30.0)
    actions.register_all(registry)
    message = Message(Mention(user_id="10000"), Text(text=" hi"))
    _run(registry, SendMessageAction(scene_type=SceneType.USER, scene_id="20001", message=message))
    assert transport.calls == [
        ("user.channel.create", {"user_id": "20001"}),
        ("message.create", {"channel_id": "direct1", "content": '<at id="10000"/> hi'}),
    ]


def test_send_to_a_known_channel_skips_the_lookup():
    transport = FakeTransport({"message.create": [{"id": "m3"}]})
    index = ChannelIndex()
    index.remember("direct1")
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0, channel_index=index).register_all(registry)
    _run(registry, SendMessageAction(scene_type=SceneType.USER, scene_id="direct1", message=Message(Text(text="hi"))))
    assert transport.calls == [("message.create", {"channel_id": "direct1", "content": "hi"})]


def test_recall_and_fetch_use_the_packed_message_id():
    transport = FakeTransport({"message.get": {"id": "m1", "content": "old"}})
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    _run(registry, RecallMessageAction(message_id="chan1:m1"))
    fetched = _run(registry, FetchMessageAction(message_id="chan1:m1"))
    assert str(fetched) == "old"
    assert transport.calls == [
        ("message.delete", {"channel_id": "chan1", "message_id": "m1"}),
        ("message.get", {"channel_id": "chan1", "message_id": "m1"}),
    ]


def test_recall_without_a_channel_is_rejected():
    _transport, registry = _registry()
    with pytest.raises(Exception, match="needs the channel"):
        _run(registry, RecallMessageAction(message_id="m1"))


def test_react_adds_and_removes():
    transport, registry = _registry()
    _run(registry, ReactMessageAction(message_id="chan1:m1", reaction="thumbsup", enabled=True))
    _run(registry, ReactMessageAction(message_id="chan1:m1", reaction="thumbsup", enabled=False))
    assert transport.calls == [
        ("reaction.create", {"channel_id": "chan1", "message_id": "m1", "emoji_id": "thumbsup"}),
        ("reaction.delete", {"channel_id": "chan1", "message_id": "m1", "emoji_id": "thumbsup"}),
    ]


def test_paginated_lists_follow_the_next_token():
    remaining = [
        {"data": [{"id": "g1", "name": "one"}], "next": "p2"},
        {"data": [{"id": "g2", "name": "two"}], "next": None},
    ]
    transport = FakeTransport({"guild.list": lambda _params: remaining.pop(0)})
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    groups = _run(registry, GetGroupListAction())
    assert [group.group_id for group in groups] == ["g1", "g2"]
    assert [params.get("next") for _route, params in transport.calls] == [None, "p2"]


def test_member_profile_reads_nick_and_roles():
    transport = FakeTransport(
        {
            "guild.member.get": {
                "user": {"id": "20001", "nick": "someone"},
                "nick": "card",
                "roles": [{"id": "r1", "name": "admin"}],
            }
        }
    )
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    member = _run(registry, GetGroupMemberAction(group_id="guild1", user_id="20001"))
    assert (member.user_id, member.card, member.role) == ("20001", "card", MemberRole.ADMIN)


def test_set_member_role_matches_a_role_by_name():
    transport = FakeTransport({"guild.role.list": {"data": [{"id": "r9", "name": "管理员"}], "next": None}})
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    _run(registry, SetMemberRoleAction(group_id="guild1", user_id="20001", role=MemberRole.ADMIN))
    assert transport.calls[-1] == (
        "guild.member.role.set",
        {"guild_id": "guild1", "user_id": "20001", "role_id": "r9"},
    )


def test_set_member_role_to_member_unsets_every_role():
    transport = FakeTransport({"guild.role.list": {"data": [{"id": "r1", "name": "admin"}], "next": None}})
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    _run(registry, SetMemberRoleAction(group_id="guild1", user_id="20001", role=MemberRole.MEMBER))
    assert transport.calls[-1] == (
        "guild.member.role.unset",
        {"guild_id": "guild1", "user_id": "20001", "role_id": "r1"},
    )


def test_mute_uses_milliseconds():
    transport, registry = _registry()
    _run(registry, MuteMemberAction(group_id="guild1", user_id="20001", duration=600))
    _run(registry, UnmuteMemberAction(group_id="guild1", user_id="20001"))
    assert transport.calls == [
        ("guild.member.mute", {"guild_id": "guild1", "user_id": "20001", "duration": 600000}),
        ("guild.member.mute", {"guild_id": "guild1", "user_id": "20001", "duration": 0}),
    ]


def test_mute_all_uses_the_channel_route():
    transport = FakeTransport({"channel.list": {"data": [{"id": "chan1", "type": 0}], "next": None}})
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    _run(registry, SetGroupMuteAction(group_id="guild1", muted=True))
    _run(registry, SetGroupMuteAction(group_id="guild1", muted=False))
    mutes = [call for call in transport.calls if call[0] == "channel.mute"]
    assert mutes[0][1]["duration"] == 30 * 24 * 3600 * 1000
    assert mutes[1][1]["duration"] == 0


def test_request_approvals_pick_the_right_route():
    transport, registry = _registry()
    _run(registry, ApproveFriendRequestAction(request_id="friend:req1"))
    _run(registry, ApproveGroupRequestAction(request_id="member:guild1:req2"))
    _run(registry, RejectGroupRequestAction(request_id="guild:guild1:req3", reason="no"))
    assert transport.calls == [
        ("friend.approve", {"message_id": "req1", "approve": True}),
        ("guild.member.approve", {"message_id": "req2", "guild_id": "guild1", "approve": True}),
        ("guild.approve", {"message_id": "req3", "guild_id": "guild1", "approve": False, "comment": "no"}),
    ]


def test_download_proxies_internal_and_listed_urls():
    _transport, registry = _registry()
    internal = _run(registry, DownloadFileAction(file_id="internal:qq/10000/_tmp/a.png"))
    listed = _run(registry, DownloadFileAction(file_id="https://cdn.example.com/a.png"))
    public = _run(registry, DownloadFileAction(file_id="https://other.example.com/a.png"))
    assert internal.url == "http://127.0.0.1:5140/proxy/internal:qq/10000/_tmp/a.png"
    assert listed.url == "http://127.0.0.1:5140/proxy/https://cdn.example.com/a.png"
    assert public.url == "https://other.example.com/a.png"


def test_channel_and_message_listing():
    transport = FakeTransport(
        {
            "channel.list": {"data": [{"id": "chan1", "type": 0, "name": "general", "parent_id": "cat"}], "next": None},
            "message.list": {"data": [{"id": "m1", "content": "hello"}], "next": None},
        }
    )
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    channels = _run(registry, SatoriChannelListAction(guild_id="guild1"))
    assert (channels[0].id, channels[0].type, channels[0].name, channels[0].parent_id) == ("chan1", 0, "general", "cat")
    messages = _run(registry, SatoriMessageListAction(channel_id="chan1"))
    assert [str(message) for message in messages] == ["hello"]


def test_upload_returns_the_sdk_urls(tmp_path):
    upload = tmp_path / "x.png"
    upload.write_bytes(b"data")
    _transport, registry = _registry()
    urls = _run(registry, SatoriUploadFileAction(files=(("pic", str(upload)),)))
    assert urls == {"pic": "internal:satori/pic"}


def test_unsupported_actions_stay_unregistered():
    _transport, registry = _registry()
    with pytest.raises(CapabilityNotSupportedError):
        _run(registry, PokeAction(scene_type=SceneType.GROUP, scene_id="guild1", user_id="20001"))
