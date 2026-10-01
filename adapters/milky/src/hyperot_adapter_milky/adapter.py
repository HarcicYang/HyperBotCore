from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextlib import suppress
from typing import Any, TypeVar

from pydantic import JsonValue

from hyperot.v2.adapter import (
    ActionRegistry,
    AdapterManifest,
    ExtensionRegistry,
    load_manifest,
)
from hyperot.v2.common import SceneType
from hyperot.v2.events import Event, FileUploadedEvent

from .actions import MilkyActions
from .api import MilkyAPI
from .config import MilkyConfig
from .events import (
    MilkyFriendFileUploadedEvent,
    MilkyFriendRequestedEvent,
    MilkyGroupInvitationReceivedEvent,
    MilkyGroupJoinRequestedEvent,
    MilkyMemberInviteRequestedEvent,
    MilkyMessageReceivedEvent,
    translate_event,
)
from .segments import MilkyFile, MilkySegmentCodec
from .transport import MilkyTransport, build_transport

ResultT = TypeVar("ResultT")


class _ExtensionContext:
    def __init__(self, adapter: MilkyAdapter) -> None:
        self.adapter = adapter

    async def execute(self, action: Any) -> Any:
        return await self.adapter.execute(action)


class MilkyAdapter:
    def __init__(self) -> None:
        self.manifest: AdapterManifest = load_manifest("hyperot_adapter_milky")
        self.config_type = MilkyConfig
        self.segment_codec = MilkySegmentCodec()
        self.actions = ActionRegistry()
        self.extensions = ExtensionRegistry(_ExtensionContext(self))
        self.api_type = MilkyAPI
        self._config: MilkyConfig | None = None
        self._transports: list[MilkyTransport] = []
        self._action_transport: MilkyTransport | None = None
        self._running = False
        self._file_context: OrderedDict[str, dict[str, JsonValue]] = OrderedDict()
        self._request_context: OrderedDict[str, dict[str, JsonValue]] = OrderedDict()

    async def start(self, config: MilkyConfig) -> None:
        if self._running:
            return
        self._config = config
        self._transports = [build_transport(connection, config.action_timeout) for connection in config.connections]
        if not self._transports:
            raise ValueError("Milky adapter requires at least one connection")
        started: list[MilkyTransport] = []
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
        builder = MilkyActions(
            self._action_transport,
            self.segment_codec,
            config.action_timeout,
            file_context_lookup=self._file_context_lookup,
            request_context_lookup=self._request_context_lookup,
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

            raise AdapterDisconnectedError("Milky adapter is not started")
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

    async def execute(self, action: Any) -> Any:
        handler = self.actions.get(type(action))
        return await handler(action)

    def _remember(self, store: OrderedDict[str, dict[str, JsonValue]], key: str, values: dict[str, JsonValue]) -> None:
        context = store.setdefault(key, {})
        context.update({name: value for name, value in values.items() if value is not None})
        store.move_to_end(key)
        while len(store) > 4096:
            store.popitem(last=False)

    def _lookup(self, store: OrderedDict[str, dict[str, JsonValue]], key: str) -> dict[str, JsonValue] | None:
        context = store.get(key)
        if context is not None:
            store.move_to_end(key)
            return dict(context)
        return None

    def _file_context_lookup(self, file_id: str) -> dict[str, JsonValue] | None:
        return self._lookup(self._file_context, str(file_id))

    def _request_context_lookup(self, request_id: str) -> dict[str, JsonValue] | None:
        return self._lookup(self._request_context, str(request_id))

    def _remember_event_context(self, event: Event) -> None:
        # Milky addresses files and requests by scene, which the core events drop,
        # so the adapter remembers what each id was seen in.
        if isinstance(event, MilkyMessageReceivedEvent):
            in_group = event.scene_type == SceneType.GROUP
            for segment in event.message:
                if isinstance(segment, MilkyFile) and segment.file_id:
                    values = _file_context(segment.file_hash, event.scene_id, in_group)
                    self._remember(self._file_context, segment.file_id, values)
            return

        if isinstance(event, FileUploadedEvent):
            values = _file_context(None, event.scene_id, event.scene_type == SceneType.GROUP)
            if isinstance(event, MilkyFriendFileUploadedEvent):
                values["file_hash"] = event.file_hash
                values["is_self"] = event.is_self
            self._remember(self._file_context, event.file.file_id, values)
            return

        if isinstance(event, MilkyGroupJoinRequestedEvent | MilkyMemberInviteRequestedEvent):
            self._remember(
                self._request_context,
                str(event.request_id),
                {"notification_type": event.notification_type, "is_filtered": event.is_filtered},
            )
            return

        if isinstance(event, MilkyGroupInvitationReceivedEvent):
            self._remember(self._request_context, str(event.request_id), {"invitation_seq": event.invitation_seq})
            return

        if isinstance(event, MilkyFriendRequestedEvent):
            self._remember(self._request_context, str(event.request_id), {"is_filtered": event.is_filtered})


def _file_context(file_hash: str | None, scene_id: str, in_group: bool) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {"file_hash": file_hash}
    if in_group:
        values["group_id"] = scene_id
    else:
        values["user_id"] = scene_id
    return values


def create_adapter() -> MilkyAdapter:
    return MilkyAdapter()


__all__ = ["MilkyAdapter", "create_adapter"]
