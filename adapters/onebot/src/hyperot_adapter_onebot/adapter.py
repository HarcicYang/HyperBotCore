from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextlib import suppress
from typing import TypeVar

from pydantic import JsonValue

from hyperot.v2.actions import Action
from hyperot.v2.adapter import (
    ActionRegistry,
    AdapterManifest,
    ExtensionRegistry,
    load_manifest,
)
from hyperot.v2.common import SceneType
from hyperot.v2.events import Event, GroupInvitationReceivedEvent, GroupJoinRequestedEvent

from .actions import OneBotActions
from .api import OneBotAPI
from .config import OneBotConfig
from .events import (
    OneBotFileUploadedEvent,
    OneBotMessageReceivedEvent,
    translate_event,
)
from .segments import OneBotFile, OneBotSegmentCodec
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
        self._message_groups: OrderedDict[str, str] = OrderedDict()
        self._request_subtypes: OrderedDict[str, str] = OrderedDict()
        self._file_context: OrderedDict[str, dict[str, JsonValue]] = OrderedDict()

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
            self._transports.clear()
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
                message_group_lookup=self._message_group_lookup,
                message_group_remember=self._remember_message_group,
                request_subtype_lookup=self._request_subtype_lookup,
                file_context_lookup=self._file_context_lookup,
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
            event = translate_event(payload, self.segment_codec, self._message_group_lookup)
            if event is not None:
                self._remember_event_context(event)
                return event

    async def execute(self, action: Action[ResultT]) -> ResultT:
        handler = self.actions.get(type(action))
        return await handler(action)

    def _require_action_transport(self) -> ActionTransport:
        if self._action_transport is None:
            raise RuntimeError("OneBot adapter has no action transport")
        return self._action_transport

    def _remember_message_group(self, message_id: str, group_id: str) -> None:
        self._message_groups[str(message_id)] = group_id
        self._message_groups.move_to_end(str(message_id))
        while len(self._message_groups) > 8192:
            self._message_groups.popitem(last=False)

    def _message_group_lookup(self, message_id: str) -> str | None:
        group_id = self._message_groups.get(str(message_id))
        if group_id is not None:
            self._message_groups.move_to_end(str(message_id))
        return group_id

    def _remember_request_subtype(self, request_id: str, sub_type: str) -> None:
        self._request_subtypes[request_id] = sub_type
        self._request_subtypes.move_to_end(request_id)
        while len(self._request_subtypes) > 1024:
            self._request_subtypes.popitem(last=False)

    def _request_subtype_lookup(self, request_id: str) -> str | None:
        sub_type = self._request_subtypes.get(request_id)
        if sub_type is not None:
            self._request_subtypes.move_to_end(request_id)
        return sub_type

    def _remember_file_context(self, file_id: str, **values: JsonValue) -> None:
        key = str(file_id)
        context = self._file_context.setdefault(key, {})
        context.update({name: value for name, value in values.items() if value is not None})
        self._file_context.move_to_end(key)
        while len(self._file_context) > 4096:
            self._file_context.popitem(last=False)

    def _file_context_lookup(self, file_id: str) -> dict[str, JsonValue] | None:
        context = self._file_context.get(str(file_id))
        if context is not None:
            self._file_context.move_to_end(str(file_id))
            return dict(context)
        return None

    def _remember_event_context(self, event: Event) -> None:
        if isinstance(event, OneBotMessageReceivedEvent):
            if event.scene_type == SceneType.GROUP:
                self._remember_message_group(event.message_id, str(event.scene_id))
            for segment in event.message:
                if isinstance(segment, OneBotFile) and segment.file_id is not None:
                    self._remember_file_context(segment.file_id, file_hash=segment.file_hash)
        elif isinstance(event, OneBotFileUploadedEvent):
            if str(event.file.file_id):
                self._remember_file_context(
                    event.file.file_id,
                    busid=event.busid,
                    file_hash=event.file_hash,
                )
        elif isinstance(event, GroupJoinRequestedEvent):
            self._remember_request_subtype(str(event.request_id), "add")
        elif isinstance(event, GroupInvitationReceivedEvent):
            self._remember_request_subtype(str(event.request_id), "invite")


def create_adapter() -> OneBotAdapter:
    return OneBotAdapter()
