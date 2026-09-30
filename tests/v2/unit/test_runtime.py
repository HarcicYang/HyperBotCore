import asyncio

import pytest
from pydantic import BaseModel

from hyperot.v2.client import Client
from hyperot.v2.client.runtime import RuntimeSupervisor
from hyperot.v2.common import AdapterConnectionError, AdapterDisconnectedError
from hyperot.v2.config import LoggingConfig, RuntimeConfig


class EmptyConfig(BaseModel):
    pass


class RetryAdapter:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self.receive_event = asyncio.Event()

    async def start(self, _config: object) -> None:
        self.start_calls += 1
        if self.start_calls < 3:
            raise AdapterConnectionError("not ready")

    async def stop(self) -> None:
        self.stop_calls += 1

    async def receive(self):
        await self.receive_event.wait()
        raise RuntimeError("stopped")


def test_runtime_retries_initial_connection():
    async def run() -> None:
        adapter = RetryAdapter()
        supervisor = RuntimeSupervisor(
            adapter,  # type: ignore[arg-type]
            RuntimeConfig(reconnect_initial_delay=0, reconnect_max_delay=0),
            object(),
            lambda _event: asyncio.sleep(0),
        )
        await supervisor.start()
        for _ in range(20):
            if adapter.start_calls >= 3:
                break
            await asyncio.sleep(0)
        assert adapter.start_calls == 3
        assert supervisor.running is True
        await supervisor.stop()

    asyncio.run(run())


class FailingAdapter:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self, _config: object) -> None:
        self.start_calls += 1
        raise AdapterConnectionError("connection down")

    async def stop(self) -> None:
        self.stop_calls += 1

    async def receive(self):
        raise AssertionError("receive should not be called")


class DisconnectAdapter:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self, _config: object) -> None:
        self.start_calls += 1
        if self.start_calls > 1:
            raise AdapterConnectionError("connection down")

    async def stop(self) -> None:
        self.stop_calls += 1

    async def receive(self):
        raise AdapterDisconnectedError("connection closed")


def test_runtime_stops_after_initial_connection_attempts():
    async def run() -> None:
        adapter = FailingAdapter()
        supervisor = RuntimeSupervisor(
            adapter,  # type: ignore[arg-type]
            RuntimeConfig(reconnect_initial_delay=0, reconnect_max_delay=0, reconnect_max_attempts=3),
            object(),
            lambda _event: asyncio.sleep(0),
        )

        with pytest.raises(AdapterConnectionError, match="connection down"):
            await supervisor.start()

        assert adapter.start_calls == 3
        assert supervisor.running is False
        assert isinstance(await supervisor.wait_closed(), AdapterConnectionError)

    asyncio.run(run())


def test_runtime_stops_after_disconnect_reconnect_limit():
    async def run() -> None:
        adapter = DisconnectAdapter()
        supervisor = RuntimeSupervisor(
            adapter,  # type: ignore[arg-type]
            RuntimeConfig(reconnect_initial_delay=0, reconnect_max_delay=0, reconnect_max_attempts=2),
            object(),
            lambda _event: asyncio.sleep(0),
        )

        await supervisor.start()
        error = await asyncio.wait_for(supervisor.wait_closed(), timeout=1)

        assert adapter.start_calls == 2
        assert supervisor.running is False
        assert isinstance(error, AdapterConnectionError)

    asyncio.run(run())


def test_client_run_exits_after_reconnect_limit():
    async def run() -> None:
        adapter = DisconnectAdapter()
        client = Client(
            adapter,  # type: ignore[arg-type]
            EmptyConfig(),
            RuntimeConfig(reconnect_initial_delay=0, reconnect_max_delay=0, reconnect_max_attempts=2),
            LoggingConfig(level="CRITICAL", use_nerd_font=False, global_handlers=False, stream="stdout"),
        )

        with pytest.raises(AdapterConnectionError, match="connection down"):
            await asyncio.wait_for(client.run(), timeout=1)

        assert client.running is False

    asyncio.run(run())
