from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel

from ..adapter import (
    Adapter,
    ExtensionRegistry,
    create_adapter_by_id,
)
from ..api import ClientAPI
from ..common import ConfigurationError
from ..config import LoggingConfig, RuntimeConfig, load_raw_app_config
from ..events import ClientStartedEvent, ClientStoppedEvent, Event, EventDispatcher
from ..hyperogger import Logger, configure_hyperot_logging
from .executor import ActionExecutor
from .runtime import RuntimeSupervisor

ApiT = TypeVar("ApiT", bound=ClientAPI)
ConfigT = TypeVar("ConfigT", bound=BaseModel)


class Client(Generic[ApiT]):
    def __init__(
        self,
        adapter: Adapter[Any],
        adapter_config: BaseModel,
        runtime_config: RuntimeConfig | None = None,
        logging_config: LoggingConfig | None = None,
        api_type: type[ApiT] | None = None,
    ) -> None:
        self.adapter = adapter
        self.adapter_config = adapter_config
        self.runtime_config = runtime_config or RuntimeConfig()
        self.logging_config = logging_config or LoggingConfig()
        configure_hyperot_logging(
            use_nf=self.logging_config.use_nerd_font,
            stream=(sys.stderr if self.logging_config.stream == "stderr" else sys.stdout),
            replace=True,
            global_handlers=self.logging_config.global_handlers,
        )
        self.logger = Logger.create("hyperot.v2.client", self.logging_config.level, self.logging_config.use_nerd_font)
        self.dispatcher = EventDispatcher()
        self._executor = ActionExecutor(adapter, lambda: self.running)
        self._api_type = api_type or getattr(adapter, "api_type", ClientAPI)
        if not issubclass(self._api_type, ClientAPI):
            raise ConfigurationError("api_type must inherit ClientAPI")
        self.api: ApiT = cast(ApiT, self._api_type(self._executor))
        self._supervisor = RuntimeSupervisor(adapter, self.runtime_config, adapter_config, self._dispatch_event)
        self._running = False
        self._stop_event = asyncio.Event()
        self._receive_task: asyncio.Task[None] | None = None
        self._dispatch_tasks: set[asyncio.Task[None]] = set()

    @property
    def running(self) -> bool:
        return self._running

    @classmethod
    def from_appconfig(
        cls,
        path: str | Path = "appconfig.json",
        *,
        api_type: type[ApiT] | None = None,
    ) -> Client[ApiT]:
        raw = load_raw_app_config(path)
        if raw.active_adapter is None:
            raise ConfigurationError("no active adapter configured")
        adapter = create_adapter_by_id(raw.active_adapter)
        adapter_config = adapter.config_type.model_validate(raw.adapter_config)
        return cls(
            adapter=adapter,
            adapter_config=adapter_config,
            runtime_config=raw.runtime,
            logging_config=raw.logging,
            api_type=api_type,
        )

    def subscribe(self, event_type: type[Event], handler: Callable[..., Awaitable[None]]) -> None:
        self.dispatcher.subscribe(event_type, handler)

    def unsubscribe(self, event_type: type[Event], handler: Callable[..., Awaitable[None]]) -> None:
        self.dispatcher.unsubscribe(event_type, handler)

    def extension(self, interface: type[Any]) -> Any:
        registry = getattr(self.adapter, "extensions", None)
        if registry is None:
            registry = ExtensionRegistry(self._executor)
            self.adapter.extensions = registry
        return registry.get(interface)

    async def emit(self, event: Event) -> None:
        if not isinstance(event, Event):
            raise TypeError("event bus accepts Event instances only")
        task = asyncio.create_task(self.dispatcher.dispatch(event, self))
        self._dispatch_tasks.add(task)
        task.add_done_callback(self._dispatch_tasks.discard)

    async def _dispatch_event(self, event: Event) -> None:
        await self.emit(event)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        try:
            await self._supervisor.start()
        except BaseException:
            self._running = False
            self._stop_event.set()
            raise
        await self.emit(ClientStartedEvent())

    async def stop(self) -> None:
        if not self._running and self._receive_task is None:
            return
        self._running = False
        await self._supervisor.stop()
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        if self._dispatch_tasks:
            _done, pending = await asyncio.wait(
                self._dispatch_tasks,
                timeout=self.runtime_config.shutdown_timeout,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        try:
            await self.adapter.stop()
        finally:
            await self.emit(ClientStoppedEvent())
            self._stop_event.set()

    async def run(self) -> None:
        await self.start()
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self._stop_event.set)
                except (NotImplementedError, RuntimeError):
                    pass
        stop_task = asyncio.create_task(self._stop_event.wait())
        closed_task = asyncio.create_task(self._supervisor.wait_closed())
        error: BaseException | None = None
        try:
            done, _ = await asyncio.wait(
                {stop_task, closed_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if closed_task in done:
                error = closed_task.result()
        finally:
            for task in (stop_task, closed_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(stop_task, closed_task, return_exceptions=True)
            await self.stop()
        if error is not None:
            raise error

    async def __aenter__(self) -> Client[ApiT]:
        await self.start()
        return self

    async def __aexit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        await self.stop()
