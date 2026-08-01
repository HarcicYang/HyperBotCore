from collections.abc import Callable
from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protocol import ActionsBase, BaseListener
    from ..utils import KeyQueue

__all__ = ["ENTRY_POINT_GROUP", "Adapter", "AdapterRegistry", "registry"]

ENTRY_POINT_GROUP = "hyperot.adapters"


@dataclass
class Adapter:
    name: str
    actions_cls: type["ActionsBase"]
    listener: "BaseListener"
    reports: "KeyQueue"


class AdapterRegistry:
    def __init__(self):
        self._registry: dict[str, Adapter] = {}
        self._loaders: dict[str, Callable[[], Adapter]] = {}
        self._entry_points_loaded = False
        self._current: Adapter | None = None

    def register_loader(self, name: str, loader: Callable[[], Adapter]) -> None:
        """注册协议加载器（内置表之外，第三方协议可调用）。"""
        self._loaders[name] = loader

    def _load_entry_points(self) -> None:
        if self._entry_points_loaded:
            return
        self._entry_points_loaded = True
        try:
            eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:
            eps = metadata.entry_points().select(group=ENTRY_POINT_GROUP)
        for ep in eps:
            if ep.name not in self._loaders:
                self._loaders[ep.name] = ep.load()

    def load(self, name: str) -> None:
        if name in self._registry:
            self._current = self._registry[name]
            return
        self._load_entry_points()
        loader = self._loaders.get(name)
        if loader is None:
            raise NotImplementedError(f"未知的适配器：{name}")
        adapter = loader()
        self._registry[name] = adapter
        self._current = adapter

    @property
    def current(self) -> Adapter | None:
        return self._current

    def __contains__(self, name: str) -> bool:
        return name in self._registry or name in self._loaders


def _builtin_onebot() -> Adapter:
    from . import onebot

    return onebot.build_adapter()


def _builtin_milky() -> Adapter:
    from . import milky

    return milky.build_adapter()


registry = AdapterRegistry()
registry.register_loader("OneBot", _builtin_onebot)
registry.register_loader("Milky", _builtin_milky)
