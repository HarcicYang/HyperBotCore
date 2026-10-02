import asyncio
import errno
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from hyperot_adapter_satori import create_adapter
from hyperot_adapter_satori import transport as satori_transport
from hyperot_adapter_satori.config import WebHookConfig, WebSocketConfig
from hyperot_adapter_satori.transport import WebHookEventTransport, WebSocketEventTransport

from hyperot.v2.common import (
    ActionRejectedError,
    AdapterConnectionError,
    AdapterDisconnectedError,
    CapabilityNotSupportedError,
)


def _websocket_config(**overrides) -> WebSocketConfig:
    payload = {"type": "WebSocket", "url": "ws://127.0.0.1:5140", "access_token": "tok"}
    payload.update(overrides)
    return WebSocketConfig.model_validate(payload)


class FakeWebSocket:
    def __init__(self, frames: list[str]) -> None:
        self.frames = list(frames)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for frame in self.frames:
            yield frame


def _refuse(monkeypatch, exc: BaseException) -> None:
    async def fake_connect(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr(satori_transport, "ws_connect", fake_connect)


def test_refused_websocket_reports_the_endpoint(monkeypatch):
    _refuse(monkeypatch, ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5140)"))
    transport = WebSocketEventTransport(_websocket_config(), 30.0)

    with pytest.raises(AdapterConnectionError) as caught:
        asyncio.run(transport.start())

    message = str(caught.value)
    assert "ws://127.0.0.1:5140/v1/events" in message
    assert "running and listening on 127.0.0.1:5140" in message


def test_failed_adapter_start_leaves_it_stopped(monkeypatch):
    _refuse(monkeypatch, ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5140)"))
    adapter = create_adapter()
    config = adapter.config_type.model_validate(
        {"connections": [{"type": "WebSocket", "url": "ws://127.0.0.1:5140"}]}
    )

    async def scenario() -> None:
        with pytest.raises(AdapterConnectionError):
            await adapter.start(config)
        assert adapter._transports == []
        await adapter.stop()
        with pytest.raises(AdapterDisconnectedError, match="not started"):
            await adapter.receive()

    asyncio.run(scenario())


def test_identify_carries_the_token(monkeypatch):
    socket = FakeWebSocket([])
    captured: dict = {}

    async def fake_connect(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("additional_headers")
        return socket

    monkeypatch.setattr(satori_transport, "ws_connect", fake_connect)
    transport = WebSocketEventTransport(_websocket_config(), 30.0)
    asyncio.run(transport.start())
    try:
        assert captured["url"] == "ws://127.0.0.1:5140/v1/events"
        assert captured["headers"] == {"Authorization": "Bearer tok"}
        assert socket.sent[0] == json.dumps({"op": 3, "body": {"token": "tok"}})
        # The heartbeat follows the identify signal.
        assert json.loads(socket.sent[1]) == {"op": 1}
    finally:
        asyncio.run(transport.stop())
    assert socket.closed


def test_websocket_queues_events_and_remembers_logins(monkeypatch):
    frames = [
        json.dumps(
            {
                "op": 4,
                "body": {
                    "logins": [{"platform": "qq", "user": {"id": "10000"}, "status": 1}],
                    "proxy_urls": ["https://cdn/"],
                },
            }
        ),
        json.dumps({"op": 2}),
        json.dumps({"op": 0, "body": {"type": "message-created"}}),
    ]
    socket = FakeWebSocket(frames)

    async def fake_connect(*_args, **_kwargs):
        return socket

    monkeypatch.setattr(satori_transport, "ws_connect", fake_connect)
    transport = WebSocketEventTransport(_websocket_config(), 30.0)
    asyncio.run(transport.start())
    try:
        event = asyncio.run(transport.receive())
        assert event == {"type": "message-created"}
        assert transport.resolve_identity() == ("qq", "10000")
        assert transport.proxy_urls() == ["https://cdn/"]
    finally:
        asyncio.run(transport.stop())


def test_identity_prefers_the_configured_login():
    transport = WebSocketEventTransport(_websocket_config(platform="telegram", user_id="42"), 30.0)
    transport.remember_login({"platform": "qq", "user": {"id": "10000"}, "status": 1})
    transport.remember_login({"platform": "telegram", "user": {"id": "42"}, "status": 0})
    assert transport.resolve_identity() == ("telegram", "42")


def test_identity_prefers_online_logins():
    transport = WebSocketEventTransport(_websocket_config(), 30.0)
    transport.remember_login({"platform": "discord", "user": {"id": "1"}, "status": 0})
    transport.remember_login({"platform": "qq", "user": {"id": "2"}, "status": 1})
    assert transport.resolve_identity() == ("qq", "2")


def test_identity_without_logins_raises():
    transport = WebSocketEventTransport(_websocket_config(), 30.0)
    with pytest.raises(AdapterDisconnectedError, match="no login"):
        transport.resolve_identity()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, ActionRejectedError),
        (401, AdapterConnectionError),
        (403, ActionRejectedError),
        (404, CapabilityNotSupportedError),
        (405, ActionRejectedError),
        (500, AdapterConnectionError),
    ],
)
def test_http_status_mapping(status, expected):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "boom"})

    client = satori_transport.SatoriHttpClient("http://127.0.0.1:5140", "tok", 30.0)
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    with pytest.raises(expected):
        asyncio.run(client.call("guild.get", {"guild_id": "1"}, 30.0, ("qq", "10000")))


def test_http_call_sends_the_satori_headers():
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json={"id": "guild1"})

    client = satori_transport.SatoriHttpClient("http://127.0.0.1:5140", "tok", 30.0)
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    data = asyncio.run(client.call("guild.get", {"guild_id": "1"}, 30.0, ("qq", "10000")))
    assert data == {"id": "guild1"}
    assert seen["url"] == "http://127.0.0.1:5140/v1/guild.get"
    assert seen["headers"]["satori-platform"] == "qq"
    assert seen["headers"]["satori-user-id"] == "10000"
    assert seen["headers"]["authorization"] == "Bearer tok"


def test_non_json_response_is_reported():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    client = satori_transport.SatoriHttpClient("http://127.0.0.1:5140", "", 30.0)
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(handler))
    with pytest.raises(AdapterConnectionError, match="non-JSON"):
        asyncio.run(client.call("guild.get", {}, 30.0, ("qq", "1")))


def _webhook_config() -> WebHookConfig:
    return WebHookConfig.model_validate(
        {
            "type": "WebHook",
            "api_url": "http://127.0.0.1:5140",
            "host": "127.0.0.1",
            "port": 15140,
            "token": "secret",
            "register_webhook": False,
        }
    )


def _webhook_transport() -> WebHookEventTransport:
    transport = WebHookEventTransport(_webhook_config(), 30.0)

    async def fake_call(route, params, timeout, identity=None):
        return {"logins": [{"platform": "qq", "user": {"id": "10000"}, "status": 1}], "proxy_urls": []}

    transport.http.call = fake_call  # type: ignore[method-assign]
    return transport


def test_webhook_is_registered_on_start_and_removed_on_stop():
    transport = WebHookEventTransport(
        WebHookConfig.model_validate(
            {
                "type": "WebHook",
                "api_url": "http://127.0.0.1:5140",
                "host": "127.0.0.1",
                "port": 15141,
                "token": "app",
            }
        ),
        30.0,
    )
    calls: list[tuple[str, dict]] = []

    async def fake_call(route, params, timeout, identity=None):
        calls.append((route, params))
        return {"logins": [{"platform": "qq", "user": {"id": "10000"}, "status": 1}], "proxy_urls": []}

    transport.http.call = fake_call  # type: ignore[method-assign]
    asyncio.run(transport.start())
    try:
        assert calls[0] == ("meta", {})
        assert calls[1] == ("meta/webhook.create", {"url": transport.event_url, "token": "app"})
    finally:
        asyncio.run(transport.stop())
    assert calls[-1] == ("meta/webhook.delete", {"url": transport.event_url})


def test_webhook_rejects_a_missing_token():
    transport = _webhook_transport()
    with TestClient(transport.app) as client:
        assert client.post("/satori", json={"type": "message-created"}).status_code == 401


def test_webhook_accepts_an_event_and_reads_the_opcode():
    transport = _webhook_transport()
    # Starting loads the logins from /v1/meta, the WebHook equivalent of READY.
    asyncio.run(transport.start())
    try:
        with TestClient(transport.app) as client:
            ok = client.post(
                "/satori",
                json={"type": "message-created"},
                headers={"Authorization": "Bearer secret", "Satori-Opcode": "0"},
            )
            assert ok.status_code == 204
            meta = client.post(
                "/satori",
                json={"proxy_urls": ["https://cdn/"]},
                headers={"Authorization": "Bearer secret", "Satori-Opcode": "5"},
            )
            assert meta.status_code == 204
            ignored = client.post(
                "/satori",
                json={},
                headers={"Authorization": "Bearer secret", "Satori-Opcode": "2"},
            )
            assert ignored.status_code == 202
            broken = client.post(
                "/satori",
                content="not json",
                headers={"Authorization": "Bearer secret"},
            )
            assert broken.status_code == 400

        event = asyncio.run(transport.receive())
        assert event == {"type": "message-created"}
        assert transport.proxy_urls() == ["https://cdn/"]
        assert transport.resolve_identity() == ("qq", "10000")
    finally:
        asyncio.run(transport.stop())
