import asyncio
import errno
from types import SimpleNamespace

import pytest
from hyperot_adapter_onebot import OneBotConfig, create_adapter
from hyperot_adapter_onebot import transport as onebot_transport
from hyperot_adapter_onebot.config import ForwardWebSocketConfig, HTTPPostConfig, ReverseWebSocketConfig
from hyperot_adapter_onebot.transport import ForwardWebSocketTransport, HTTPPostTransport, ReverseWebSocketTransport
from websockets.exceptions import InvalidStatus

from hyperot.v2.common import AdapterConnectionError, AdapterDisconnectedError


def _forward_config() -> OneBotConfig:
    return OneBotConfig.model_validate({"connections": [{"type": "ForwardWebSocket", "url": "ws://127.0.0.1:5004"}]})


def _refuse(monkeypatch, exc: BaseException) -> None:
    async def fake_connect(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr(onebot_transport, "ws_connect", fake_connect)


def test_refused_forward_websocket_reports_the_endpoint(monkeypatch):
    _refuse(monkeypatch, ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5004)"))
    transport = ForwardWebSocketTransport(ForwardWebSocketConfig(url="ws://127.0.0.1:5004"))

    with pytest.raises(AdapterConnectionError) as caught:
        asyncio.run(transport.start())

    message = str(caught.value)
    assert "ws://127.0.0.1:5004" in message
    assert "connection refused" in message
    assert "running and listening on 127.0.0.1:5004" in message
    assert transport._reader_task is None


def test_rejected_handshake_reports_the_access_token(monkeypatch):
    _refuse(monkeypatch, InvalidStatus(SimpleNamespace(status_code=401)))
    transport = ForwardWebSocketTransport(ForwardWebSocketConfig(url="ws://127.0.0.1:5004"))

    with pytest.raises(AdapterConnectionError) as caught:
        asyncio.run(transport.start())

    assert "access_token" in str(caught.value)


def test_unexpected_forward_failure_is_still_wrapped(monkeypatch):
    _refuse(monkeypatch, RuntimeError("boom"))
    transport = ForwardWebSocketTransport(ForwardWebSocketConfig(url="ws://127.0.0.1:5004"))

    with pytest.raises(AdapterConnectionError, match="RuntimeError: boom"):
        asyncio.run(transport.start())


def test_busy_listener_port_is_reported(monkeypatch):
    class _BusyServer:
        started = False

        async def serve(self):
            raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(
        onebot_transport,
        "uvicorn",
        SimpleNamespace(Config=lambda *_args, **_kwargs: None, Server=lambda _config: _BusyServer()),
    )
    # The real bind conflict is covered by tests/v2/integration/test_onebot_listener.py.
    monkeypatch.setattr(onebot_transport, "_bind_conflict", lambda _host, _port: None)
    transport = HTTPPostTransport(HTTPPostConfig(host="127.0.0.1", port=6701))

    with pytest.raises(AdapterConnectionError) as caught:
        asyncio.run(transport.start())

    message = str(caught.value)
    assert "127.0.0.1:6701" in message
    assert "address already in use" in message
    assert "already listening" in message


def test_rejected_reverse_websocket_is_logged(monkeypatch):
    logged: list[str] = []

    class _FakeLogger:
        def warning(self, message: str) -> None:
            logged.append(message)

    monkeypatch.setattr(onebot_transport.Logger, "fetch", lambda _key: _FakeLogger())

    class _FakeWebSocket:
        def __init__(self) -> None:
            self.closed: int | None = None

        async def close(self, code: int) -> None:
            self.closed = code

    fake = _FakeWebSocket()
    transport = ReverseWebSocketTransport(ReverseWebSocketConfig(access_token="secret"))

    async def scenario() -> None:
        await transport._reject(fake, "access_token mismatch")  # type: ignore[arg-type]

    asyncio.run(scenario())

    assert logged == ["rejected OneBot reverse websocket: access_token mismatch"]
    assert fake.closed == 1008


def test_failed_adapter_start_leaves_it_stopped(monkeypatch):
    _refuse(monkeypatch, ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5004)"))
    adapter = create_adapter()

    async def scenario() -> None:
        with pytest.raises(AdapterConnectionError):
            await adapter.start(_forward_config())

        assert adapter._transports == []
        await adapter.stop()
        with pytest.raises(AdapterDisconnectedError, match="not started"):
            await adapter.receive()

    asyncio.run(scenario())
