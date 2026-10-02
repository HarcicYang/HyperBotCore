"""The Satori adapter itself.

The adapter owns the connections, translates events, and keeps the small amount of
state the protocol needs: which channel carries a guild, which logins the SDK reported,
and how to address them. Everything else lives in the action, codec and transport
modules.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any, TypeVar

from hyperot.v2.actions import Action
from hyperot.v2.adapter import (
    ActionRegistry,
    AdapterManifest,
    ExtensionRegistry,
    load_manifest,
)
from hyperot.v2.common import SceneType
from hyperot.v2.events import Event

from .actions import ChannelIndex, SatoriActions
from .api import SatoriAPI
from .config import SatoriConfig
from .events import (
    SatoriBotOfflineEvent,
    SatoriBotOnlineEvent,
    SatoriChannelChangedEvent,
    SatoriLoginChangedEvent,
    SatoriMessageReceivedEvent,
    translate_event,
)
from .segments import SatoriSegmentCodec
from .transport import ONLINE, SatoriTransport, build_transport

ResultT = TypeVar("ResultT")


class _ExtensionContext:
    def __init__(self, adapter: SatoriAdapter) -> None:
        self.adapter = adapter

    async def execute(self, action: Action[ResultT]) -> ResultT:
        return await self.adapter.execute(action)


class SatoriAdapter:
    def __init__(self) -> None:
        self.manifest: AdapterManifest = load_manifest("hyperot_adapter_satori")
        self.config_type = SatoriConfig
        self.segment_codec = SatoriSegmentCodec()
        self.actions = ActionRegistry()
        self.extensions = ExtensionRegistry(_ExtensionContext(self))
        self.api_type = SatoriAPI
        self._config: SatoriConfig | None = None
        self._transports: list[SatoriTransport] = []
        self._action_transport: SatoriTransport | None = None
        self._running = False
        # Channels and logins are learned at runtime and survive a reconnect.
        self._channel_index = ChannelIndex()

    async def start(self, config: SatoriConfig) -> None:
        if self._running:
            return
        self._config = config
        self._transports = [build_transport(connection, config.action_timeout) for connection in config.connections]
        if not self._transports:
            raise ValueError("Satori adapter requires at least one connection")
        started: list[SatoriTransport] = []
        try:
            for transport in self._transports:
                await transport.start()
                started.append(transport)
        except Exception:
            for transport in reversed(started):
                with suppress(Exception):
                    await transport.stop()
            self._transports.clear()
            raise
        self._action_transport = self._transports[0]
        self.actions = ActionRegistry()
        builder = SatoriActions(
            self._action_transport,
            self.segment_codec,
            config.action_timeout,
            channel_index=self._channel_index,
            online_provider=self._is_online,
            proxy_urls_provider=self._proxy_urls,
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

            raise AdapterDisconnectedError("Satori adapter is not started")
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
            if event is None:
                continue
            self._remember_event_context(event)
            return event

    async def execute(self, action: Action[ResultT]) -> ResultT:
        handler = self.actions.get(type(action))
        return await handler(action)

    # -- state the actions need -------------------------------------------------

    def _is_online(self) -> bool:
        transport = self._action_transport
        if transport is None:
            return False
        try:
            platform, user_id = transport.resolve_identity()
        except Exception:  # noqa: BLE001
            return False
        status = transport.login_status(platform, user_id)
        return status is None or status == ONLINE

    def _proxy_urls(self) -> list[str]:
        transport = self._action_transport
        return [] if transport is None else transport.proxy_urls()

    def _remember_event_context(self, event: Event) -> None:
        # Satori addresses API calls by channel and by login, neither of which the core
        # events carry, so the adapter remembers what each id was seen with.
        if isinstance(event, SatoriMessageReceivedEvent):
            self._channel_index.remember(event.channel_id, event.guild_id)
            if event.scene_type == SceneType.USER:
                self._channel_index.remember_user_channel(str(event.scene_id), event.channel_id)
            return
        if isinstance(event, SatoriChannelChangedEvent):
            if event.scene_type == SceneType.GUILD:
                # A private channel event is addressed by the peer, not by the channel.
                self._channel_index.remember(str(event.scene_id), event.guild_id)
            return
        login = _login_of(event)
        if login is not None:
            for transport in self._transports:
                if isinstance(event, SatoriBotOfflineEvent):
                    transport.forget_login(login)
                else:
                    transport.remember_login(login)


def _login_of(event: Event) -> dict[str, Any] | None:
    if isinstance(event, SatoriBotOnlineEvent | SatoriBotOfflineEvent | SatoriLoginChangedEvent):
        return {
            "platform": event.platform,
            "user": {"id": event.self_id},
            "status": event.status,
        }
    return None


def create_adapter() -> SatoriAdapter:
    return SatoriAdapter()


__all__ = ["SatoriAdapter", "create_adapter"]
