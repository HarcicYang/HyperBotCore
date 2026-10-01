import asyncio
import socket

import pytest
from hyperot_adapter_onebot.config import HTTPPostConfig, ReverseWebSocketConfig
from hyperot_adapter_onebot.transport import HTTPPostTransport, ReverseWebSocketTransport

from hyperot.v2.common import AdapterConnectionError


def _occupy() -> tuple[socket.socket, int]:
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    return holder, holder.getsockname()[1]


def test_httppost_listener_reports_an_occupied_port():
    holder, port = _occupy()
    try:
        transport = HTTPPostTransport(HTTPPostConfig(host="127.0.0.1", port=port))
        with pytest.raises(AdapterConnectionError) as caught:
            asyncio.run(transport.start())
    finally:
        holder.close()

    message = str(caught.value)
    assert f"127.0.0.1:{port}" in message
    assert "address already in use" in message
    assert "already listening" in message


def test_reverse_websocket_listener_reports_an_occupied_port():
    holder, port = _occupy()
    try:
        transport = ReverseWebSocketTransport(ReverseWebSocketConfig(host="127.0.0.1", port=port))
        with pytest.raises(AdapterConnectionError) as caught:
            asyncio.run(transport.start())
    finally:
        holder.close()

    assert f"127.0.0.1:{port}" in str(caught.value)
    assert "address already in use" in str(caught.value)


def test_ephemeral_port_still_starts():
    transport = HTTPPostTransport(HTTPPostConfig(host="127.0.0.1", port=0))

    async def scenario() -> None:
        await transport.start()
        try:
            assert transport.server is not None
            assert transport.server.started
            sockets = [sock for server in (transport.server.servers or []) for sock in server.sockets]
            assert sockets[0].getsockname()[1] > 0
        finally:
            await transport.stop()

    asyncio.run(scenario())
