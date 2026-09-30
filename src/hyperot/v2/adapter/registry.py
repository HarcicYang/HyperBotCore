from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar, cast

from ..actions import Action
from ..common import CapabilityNotSupportedError, ExtensionNotAvailableError

ResultT = TypeVar("ResultT")
ExtensionT = TypeVar("ExtensionT")


ActionHandler = Callable[[Any], Awaitable[Any]]


class ActionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[type[Action[Any]], ActionHandler] = {}

    def register(
        self,
        action_type: type[Action[ResultT]],
        handler: ActionHandler,
        *,
        replace: bool = False,
    ) -> None:
        if action_type in self._handlers and not replace:
            raise ValueError(f"action already registered: {action_type.__name__}")
        self._handlers[cast(type[Action[Any]], action_type)] = handler

    def get(self, action_type: type[Action[ResultT]]) -> ActionHandler:
        handler = self._handlers.get(cast(type[Action[Any]], action_type))
        if handler is None:
            raise CapabilityNotSupportedError(action_type)
        return handler

    def supports(self, action_type: type[Action[Any]]) -> bool:
        return action_type in self._handlers

    def action_types(self) -> frozenset[type[Action[Any]]]:
        return frozenset(self._handlers)


class ExtensionContext(Protocol):
    async def execute(self, action: Action[ResultT]) -> ResultT: ...


ExtensionFactory = Callable[[ExtensionContext], ExtensionT]


class ExtensionRegistry:
    def __init__(self, context: ExtensionContext) -> None:
        self._context = context
        self._factories: dict[type[Any], ExtensionFactory[Any]] = {}
        self._instances: dict[type[Any], Any] = {}

    def register(
        self,
        interface: type[ExtensionT],
        factory: ExtensionFactory[ExtensionT],
    ) -> None:
        if interface in self._factories:
            raise ValueError(f"extension already registered: {interface.__name__}")
        self._factories[interface] = cast(ExtensionFactory[Any], factory)

    def get(self, interface: type[ExtensionT]) -> ExtensionT:
        instance = self._instances.get(interface)
        if instance is not None:
            return cast(ExtensionT, instance)
        factory = self._factories.get(interface)
        if factory is None:
            raise ExtensionNotAvailableError(interface.__name__)
        instance = factory(self._context)
        self._instances[interface] = instance
        return cast(ExtensionT, instance)

    def clear(self) -> None:
        self._instances.clear()
