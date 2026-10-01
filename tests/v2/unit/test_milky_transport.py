import asyncio
import errno

import pytest
from hyperot_adapter_milky import MilkyConfig, create_adapter
from hyperot_adapter_milky import transport as milky_transport
from hyperot_adapter_milky.transport import WebSocketEventTransport

from hyperot.v2.common import AdapterConnectionError, AdapterDisconnectedError


def _websocket_config() -> MilkyConfig:
    return MilkyConfig.model_validate({"connections": [{"type": "WebSocket", "url": "ws://127.0.0.1:5005"}]})


def _refuse(monkeypatch, exc: BaseException) -> None:
    async def fake_connect(*_args, **_kwargs):
        raise exc

    monkeypatch.setattr(milky_transport, "ws_connect", fake_connect)


def test_refused_websocket_reports_the_endpoint(monkeypatch):
    _refuse(monkeypatch, ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5005)"))
    config = _websocket_config()
    transport = WebSocketEventTransport(config.connections[0], config.action_timeout)  # type: ignore[arg-type]

    with pytest.raises(AdapterConnectionError) as caught:
        asyncio.run(transport.start())

    message = str(caught.value)
    assert "ws://127.0.0.1:5005/event" in message
    assert "running and listening on 127.0.0.1:5005" in message


def test_failed_adapter_start_leaves_it_stopped(monkeypatch):
    _refuse(monkeypatch, ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5005)"))
    adapter = create_adapter()

    async def scenario() -> None:
        with pytest.raises(AdapterConnectionError):
            await adapter.start(_websocket_config())

        assert adapter._transports == []
        await adapter.stop()
        with pytest.raises(AdapterDisconnectedError, match="not started"):
            await adapter.receive()

    asyncio.run(scenario())
