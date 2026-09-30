from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from ..hyperogger import Logger
from .base import Event

if TYPE_CHECKING:
    from ..client.client import Client

EventT = TypeVar("EventT", bound=Event)
Handler = Callable[[EventT, "Client"], Awaitable[None]]
logger = Logger.fetch("hyperot.v2.events")


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: list[tuple[type[Event], Handler[Any]]] = []

    def subscribe(self, event_type: type[EventT], handler: Handler[EventT]) -> None:
        if not inspect.iscoroutinefunction(handler):
            raise TypeError("event handler must be async")
        if (event_type, handler) in self._handlers:
            return
        self._handlers.append((event_type, handler))

    def unsubscribe(self, event_type: type[EventT], handler: Handler[EventT]) -> None:
        self._handlers.remove((event_type, handler))

    def matching(self, event: Event) -> list[Handler[Any]]:
        matches: list[tuple[int, int, Handler[Any]]] = []
        for index, (event_type, handler) in enumerate(self._handlers):
            if isinstance(event, event_type):
                depth = len(event_type.__mro__)
                matches.append((depth, index, handler))
        matches.sort(key=lambda item: (item[0], item[1]))
        return [handler for _, _, handler in matches]

    async def dispatch(self, event: Event, client: Client) -> None:
        event.print_log()
        handlers = self.matching(event)
        if not handlers:
            return
        async with asyncio.TaskGroup() as group:
            for handler in handlers:
                group.create_task(_safe_call(handler, event, client))


async def _safe_call(handler: Handler[Any], event: Event, client: Client) -> None:
    try:
        await handler(event, client)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.error(  # noqa: G201
            f"event handler failed: event_id={event.event_id} handler={handler!r}",
            exc_info=True,
        )
