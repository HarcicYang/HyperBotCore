from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from ..actions import Action
from ..events import Event
from ..messages import Message
from .manifest import AdapterManifest
from .registry import ActionRegistry, ExtensionRegistry

ConfigT = TypeVar("ConfigT", bound=BaseModel)
ResultT = TypeVar("ResultT")
WireT = TypeVar("WireT")
ExtensionT = TypeVar("ExtensionT")


@runtime_checkable
class SegmentCodec(Protocol[WireT]):
    def decode_message(self, payload: WireT) -> Message: ...

    def encode_message(self, message: Message) -> WireT: ...


@runtime_checkable
class Adapter(Protocol[ConfigT]):
    manifest: AdapterManifest
    config_type: type[ConfigT]
    actions: ActionRegistry
    extensions: ExtensionRegistry
    segment_codec: SegmentCodec[Any]
    api_type: type[Any]

    async def start(self, config: ConfigT) -> None: ...

    async def stop(self) -> None: ...

    async def receive(self) -> Event: ...

    async def execute(self, action: Action[ResultT]) -> ResultT: ...


AdapterFactory = Callable[[], Adapter[Any]]
