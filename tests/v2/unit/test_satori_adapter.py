import asyncio
from typing import Any

from hyperot_adapter_satori import create_adapter
from hyperot_adapter_satori.actions import SatoriActions
from hyperot_adapter_satori.events import SatoriMessageReceivedEvent

from hyperot.v2.actions import GetBotStatusAction, SendMessageAction
from hyperot.v2.adapter import ActionRegistry
from hyperot.v2.common import SceneType
from hyperot.v2.events import BotOfflineEvent, BotOnlineEvent
from hyperot.v2.messages import Message, Text

MESSAGE_EVENT = {
    "sn": 1,
    "type": "message-created",
    "timestamp": 1700000000000,
    "login": {"platform": "qq", "user": {"id": "10000"}, "status": 1},
    "channel": {"id": "chan1", "type": 0, "name": "general"},
    "guild": {"id": "guild1", "name": "group"},
    "user": {"id": "20001"},
    "message": {"id": "m1", "content": "hello"},
}

LOGIN_EVENT = {
    "sn": 2,
    "type": "login-added",
    "timestamp": 1700000000000,
    "login": {"platform": "qq", "user": {"id": "10000"}, "status": 1},
}


class FakeTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.calls: list[tuple[str, dict]] = []
        self.logins: list[dict] = []

    def resolve_identity(self) -> tuple[str, str]:
        return "qq", "10000"

    def logins(self) -> list[dict]:
        return list(self.logins)

    def login_status(self, platform: str, user_id: str) -> int | None:
        return 1

    def proxy_urls(self) -> list[str]:
        return []

    def proxy_url(self, url: str) -> str:
        return url

    def remember_login(self, login: dict) -> None:
        self.logins.append(login)

    def forget_login(self, login: dict) -> None:
        key = (login.get("platform"), (login.get("user") or {}).get("id"))
        self.logins = [
            known
            for known in self.logins
            if (known.get("platform"), (known.get("user") or {}).get("id")) != key
        ]

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def receive(self) -> dict:
        if not self.payloads:
            await asyncio.Event().wait()
        return self.payloads.pop(0)

    async def call(self, route: str, params: dict, timeout: float):
        self.calls.append((route, params))
        return {"data": []}

    async def upload(self, files, timeout: float) -> dict[str, str]:
        return {}


def _started_adapter(payloads: list[dict]) -> tuple[Any, FakeTransport]:
    adapter = create_adapter()
    transport = FakeTransport(payloads)
    registry = ActionRegistry()
    SatoriActions(
        transport,
        adapter.segment_codec,
        30.0,
        channel_index=adapter._channel_index,
        online_provider=adapter._is_online,
    ).register_all(registry)
    adapter.actions = registry
    adapter._transports = [transport]
    adapter._action_transport = transport
    adapter._running = True
    return adapter, transport


def test_receive_translates_and_remembers_the_channel():
    adapter, _transport = _started_adapter([MESSAGE_EVENT])
    event = asyncio.run(adapter.receive())
    assert isinstance(event, SatoriMessageReceivedEvent)
    assert (event.scene_type, event.scene_id) == (SceneType.GUILD, "chan1")
    assert adapter._channel_index.channel_for_guild("guild1") == "chan1"


def test_login_events_teach_the_transports_about_the_login():
    adapter, transport = _started_adapter([LOGIN_EVENT])
    event = asyncio.run(adapter.receive())
    assert isinstance(event, BotOnlineEvent)
    assert transport.logins == [{"platform": "qq", "user": {"id": "10000"}, "status": 1}]


def test_offline_login_is_forgotten():
    adapter, transport = _started_adapter([{**LOGIN_EVENT, "type": "login-removed", "login": {**LOGIN_EVENT["login"], "status": 0}}])
    event = asyncio.run(adapter.receive())
    assert isinstance(event, BotOfflineEvent)
    assert transport.logins == []


def test_private_channel_events_do_not_register_the_user_as_a_channel():
    adapter, _transport = _started_adapter(
        [
            {
                **LOGIN_EVENT,
                "type": "channel-updated",
                "channel": {"id": "direct1", "type": 1},
                "user": {"id": "20001"},
            }
        ]
    )
    asyncio.run(adapter.receive())
    assert not adapter._channel_index.is_channel("20001")


def test_guild_channel_events_register_the_channel():
    adapter, _transport = _started_adapter(
        [
            {
                **LOGIN_EVENT,
                "type": "channel-added",
                "channel": {"id": "chan1", "type": 0},
                "guild": {"id": "guild1"},
            }
        ]
    )
    asyncio.run(adapter.receive())
    assert adapter._channel_index.channel_for_guild("guild1") == "chan1"


def test_send_to_a_guild_uses_the_channel_learned_from_an_event():
    adapter, transport = _started_adapter([MESSAGE_EVENT])
    asyncio.run(adapter.receive())

    async def scenario() -> None:
        return await adapter.execute(
            SendMessageAction(scene_type=SceneType.GROUP, scene_id="guild1", message=Message(Text(text="hi")))
        )

    result = asyncio.run(scenario())
    assert transport.calls[-1] == ("message.create", {"channel_id": "chan1", "content": "hi"})
    assert result.message_id.startswith("chan1:")


def test_bot_status_follows_the_login():
    adapter, _transport = _started_adapter([])

    async def scenario():
        return await adapter.execute(GetBotStatusAction())

    assert asyncio.run(scenario()).online
