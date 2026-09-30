from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TypeVar

from hyperot.v2.actions import Action
from hyperot.v2.adapter import (
    ActionRegistry,
    AdapterManifest,
    ExtensionRegistry,
    load_manifest,
)
from hyperot.v2.events import Event

from .actions import OneBotActions
from .api import OneBotAPI
from .config import OneBotConfig
from .events import translate_event
from .segments import OneBotSegmentCodec
from .transport import ActionTransport, HTTPPostTransport, build_transport

ResultT = TypeVar("ResultT")


class _ExtensionContext:
    def __init__(self, adapter: OneBotAdapter) -> None:
        self.adapter = adapter

    async def execute(self, action: Action[ResultT]) -> ResultT:
        return await self.adapter.execute(action)


class OneBotAdapter:
    def __init__(self) -> None:
        self.manifest: AdapterManifest = load_manifest("hyperot_adapter_onebot")
        self.config_type = OneBotConfig
        self.segment_codec = OneBotSegmentCodec()
        self.actions = ActionRegistry()
        self.extensions = ExtensionRegistry(_ExtensionContext(self))
        self.api_type = OneBotAPI
        self._config: OneBotConfig | None = None
        self._transports: list[ActionTransport] = []
        self._action_transport: ActionTransport | None = None
        self._running = False

    async def start(self, config: OneBotConfig) -> None:
        if self._running:
            return
        self._config = config
        self._transports = [build_transport(connection) for connection in config.connections]
        if not self._transports:
            raise ValueError("OneBot adapter requires at least one connection")
        started: list[ActionTransport] = []
        try:
            for transport in self._transports:
                await transport.start()
                started.append(transport)
        except Exception:
            for transport in reversed(started):
                with suppress(Exception):
                    await transport.stop()
            raise
        self._action_transport = next(
            (transport for transport in self._transports if not isinstance(transport, HTTPPostTransport)),
            None,
        )
        self.actions = ActionRegistry()
        if self._action_transport is not None:
            builder = OneBotActions(
                self._action_transport,
                self.segment_codec,
                config.action_timeout,
            )
            builder.register_all(self.actions)
        self._running = True

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for transport in reversed(self._transports):
            await transport.stop()
        self._transports.clear()
        self._action_transport = None
        self.extensions.clear()

    async def receive(self) -> Event:
        if not self._transports:
            from hyperot.v2.common import AdapterDisconnectedError

            raise AdapterDisconnectedError("OneBot adapter is not started")
        while True:
            if len(self._transports) == 1:
                payload = await self._transports[0].receive()
            else:
                tasks = [asyncio.create_task(transport.receive()) for transport in self._transports]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                payload = done.pop().result()
            event = translate_event(payload, self.segment_codec)
            if event is not None:
                return event

    async def execute(self, action: Action[ResultT]) -> ResultT:
        handler = self.actions.get(type(action))
        return await handler(action)

    def _require_action_transport(self) -> ActionTransport:
        if self._action_transport is None:
            raise RuntimeError("OneBot adapter has no action transport")
        return self._action_transport


def create_adapter() -> OneBotAdapter:
    return OneBotAdapter()
