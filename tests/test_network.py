import asyncio
import socket

import httpx
import pytest

from hyperot import network


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_httpc_listener_receive_and_close():
    listener_port = _free_port()
    conn = network.HTTPConnection("http://127.0.0.1:5999", f"http://127.0.0.1:{listener_port}")
    conn._HTTPConnection__start_listener()

    async def run():
        await asyncio.sleep(0.5)
        await httpx.AsyncClient().post(f"http://127.0.0.1:{listener_port}/", json={"post_type": "message", "time": 1})
        data = await asyncio.wait_for(conn.recv(), timeout=5)
        assert data == {"post_type": "message", "time": 1}
        await conn.close()
        await asyncio.sleep(0.5)
        with pytest.raises(httpx.ConnectError):
            await httpx.AsyncClient().post(f"http://127.0.0.1:{listener_port}/", json={})

    asyncio.run(run())


def test_httpc_recv_timeout_returns_none(monkeypatch):
    monkeypatch.setattr(network, "DEFAULT_TIMEOUT", 0.3)
    listener_port = _free_port()
    conn = network.HTTPConnection("http://127.0.0.1:5999", f"http://127.0.0.1:{listener_port}")
    conn._HTTPConnection__start_listener()

    async def run():
        await asyncio.sleep(0.2)
        data = await asyncio.wait_for(conn.recv(), timeout=5)
        assert data is None

    asyncio.run(run())
