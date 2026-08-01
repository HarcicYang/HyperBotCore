import asyncio

from hyperot.adapters.onebot import OneBotListener
from hyperot.protocol.listener import BaseListener


class _FakeConn:
    def __init__(
        self,
        connect_error: Exception | None = None,
        recv_exc: Exception | None = None,
        fail_connect_after: int | None = None,
    ):
        self.url = "ws://fake"
        self.connect_calls = 0
        self.recv_calls = 0
        self.closed = False
        self._connect_error = connect_error
        self._recv_exc = recv_exc
        self._fail_connect_after = fail_connect_after

    async def connect(self):
        await asyncio.sleep(0)  # 让出事件循环，避免假连接造成忙循环
        self.connect_calls += 1
        if self._connect_error is not None:
            raise self._connect_error
        if self._fail_connect_after is not None and self.connect_calls > self._fail_connect_after:
            raise ConnectionRefusedError()

    async def recv(self):
        await asyncio.sleep(0)
        self.recv_calls += 1
        if self._recv_exc is not None:
            raise self._recv_exc
        return {"post_type": "meta_event", "time": 1}

    async def close(self):
        self.closed = True


def _make_listener(monkeypatch, conn: _FakeConn, retries: int = 2) -> tuple[BaseListener, _FakeConn]:
    lis = OneBotListener()

    async def dummy(_event, _actions):
        return None

    lis.reg(dummy)
    lis.build_connection = lambda: conn  # type: ignore[method-assign]
    lis.new_actions = lambda c: object()  # type: ignore[method-assign]
    monkeypatch.setattr(lis.config.connection, "retries", retries)

    real_sleep = asyncio.sleep

    async def noop_sleep(_s):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", noop_sleep)
    return lis, conn


def test_run_retries_then_exits_after_max(monkeypatch):
    conn = _FakeConn(connect_error=ConnectionRefusedError())
    lis, conn = _make_listener(monkeypatch, conn, retries=2)

    asyncio.run(lis.run())

    assert conn.connect_calls == 3  # 初次连接 + 2 次重试后放弃
    assert conn.closed is False  # 未建立连接，不关闭


def test_run_reconnects_after_disconnect(monkeypatch):
    # 第 1 次 connect 成功 → recv 断开 → 重连（第 2 次 connect）→ 之后连接失败 → 重试耗尽退出
    conn = _FakeConn(recv_exc=ConnectionResetError(), fail_connect_after=1)
    lis, conn = _make_listener(monkeypatch, conn, retries=1)

    asyncio.run(lis.run())

    # 初次成功 + 断线后重连尝试 1 次 + 重试 1 次 = 3
    assert conn.connect_calls == 3
    assert conn.recv_calls >= 1


def test_stop_sends_notify_and_closes(monkeypatch):
    conn = _FakeConn()
    lis, conn = _make_listener(monkeypatch, conn)
    lis.connection = conn

    events = []

    async def capture(event, actions):
        events.append(type(event).__name__)

    lis.reg(capture)

    asyncio.run(lis.stop())

    assert "HyperListenerStopNotify" in events
    assert conn.closed is True
