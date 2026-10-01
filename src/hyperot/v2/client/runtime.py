from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from ..common import AdapterConnectionError, AdapterDisconnectedError
from ..events import Event
from ..hyperogger import Logger

if TYPE_CHECKING:
    from ..adapter import Adapter
    from ..config import RuntimeConfig


class RuntimeSupervisor:
    def __init__(
        self,
        adapter: Adapter[Any],
        runtime_config: RuntimeConfig,
        adapter_config: Any,
        on_event: Callable[[Event], Awaitable[None]],
    ) -> None:
        self._adapter = adapter
        self._config = runtime_config
        self._adapter_config = adapter_config
        self._on_event = on_event
        self._task: asyncio.Task[None] | None = None
        self._connected_event: asyncio.Event | None = None
        self._closed_event = asyncio.Event()
        self._terminal_error: BaseException | None = None
        self._running = False
        self._logger = Logger.fetch("hyperot.v2.runtime")

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._terminal_error = None
        self._connected_event = asyncio.Event()
        self._closed_event = asyncio.Event()
        self._task = asyncio.create_task(self._run())
        await self._connected_event.wait()
        if self._terminal_error is not None:
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            raise self._terminal_error

    async def stop(self) -> None:
        self._running = False
        if self._connected_event is not None:
            self._connected_event.set()
        if self._task is None:
            return
        if not self._task.done():
            self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def wait_closed(self) -> BaseException | None:
        if self._task is None:
            return self._terminal_error
        await self._closed_event.wait()
        return self._terminal_error

    async def _run(self) -> None:
        delay = self._config.reconnect_initial_delay
        attempt = 0
        try:
            while self._running:
                try:
                    self._logger.info(f"connecting to {type(self._adapter).__name__}")
                    await self._adapter.start(self._adapter_config)
                    self._logger.info("adapter connected")
                    if self._connected_event is not None:
                        self._connected_event.set()
                    attempt = 0
                    delay = self._config.reconnect_initial_delay
                    while self._running:
                        event = await self._adapter.receive()
                        await self._on_event(event)
                    return
                except asyncio.CancelledError:
                    raise
                except (
                    AdapterConnectionError,
                    AdapterDisconnectedError,
                    ConnectionRefusedError,
                    TimeoutError,
                    OSError,
                ) as exc:
                    if not self._running:
                        return
                    attempt += 1
                    if self._retry_exhausted(attempt):
                        self._terminal_error = exc
                        self._logger.error(
                            f"adapter connection failed permanently after {attempt} attempts: {exc};{self._retry_hint()}"
                        )
                        self._running = False
                        return
                    self._logger.warning(
                        f"adapter connection failed: {exc}; retrying in {delay:.1f}s{self._attempt_suffix(attempt)}"
                    )
                except Exception as exc:
                    if not self._running:
                        return
                    attempt += 1
                    if self._retry_exhausted(attempt):
                        self._terminal_error = exc
                        self._logger.log(
                            f"runtime connection failed permanently after {attempt} attempts:{self._retry_hint()}",
                            "ERROR",
                            exc_info=True,
                        )
                        self._running = False
                        return
                    self._logger.log(
                        f"runtime connection failed; retrying in {delay:.1f}s{self._attempt_suffix(attempt)}",
                        "ERROR",
                        exc_info=True,
                    )
                finally:
                    with suppress(Exception):
                        await self._adapter.stop()
                if not self._running:
                    return
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._config.reconnect_max_delay)
        finally:
            self._running = False
            if self._connected_event is not None:
                self._connected_event.set()
            self._closed_event.set()

    def _retry_exhausted(self, attempt: int) -> bool:
        limit = self._config.reconnect_max_attempts
        return limit is not None and attempt >= limit

    def _attempt_suffix(self, attempt: int) -> str:
        limit = self._config.reconnect_max_attempts
        if limit is None:
            return f" (attempt {attempt})"
        return f" (attempt {attempt}/{limit})"

    def _retry_hint(self) -> str:
        limit = self._config.reconnect_max_attempts
        if limit is None:
            return ""
        return " set runtime.reconnect_max_attempts to null to keep retrying"
