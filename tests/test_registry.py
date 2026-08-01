import pytest

from hyperot.adapters import Adapter, AdapterRegistry, registry
from hyperot.adapters.onebot import OneBotActions, OneBotListener
from hyperot.utils import KeyQueue


def _adapter(name: str = "Test") -> Adapter:
    return Adapter(name, OneBotActions, OneBotListener(), KeyQueue())


def test_registry_register_and_load():
    r = AdapterRegistry()
    adapter = _adapter()
    r.register_loader("Test", lambda: adapter)
    r.load("Test")
    assert r.current is adapter


def test_registry_load_unknown_raises():
    r = AdapterRegistry()
    with pytest.raises(NotImplementedError):
        r.load("Nope")


def test_registry_loader_lazy_and_cached():
    r = AdapterRegistry()
    calls = []

    def loader():
        calls.append(1)
        return _adapter()

    r.register_loader("Lazy", loader)
    assert calls == []

    r.load("Lazy")
    assert calls == [1]
    r.load("Lazy")
    r.load("Lazy")
    assert calls == [1]  # 缓存命中，不再调用 loader


def test_registry_loader_overrides_builtin():
    r = AdapterRegistry()
    custom = _adapter("Custom")
    r.register_loader("OneBot", lambda: custom)
    r.load("OneBot")
    assert r.current is custom


def test_registry_switch_current():
    r = AdapterRegistry()
    a = _adapter("A")
    b = _adapter("B")
    r.register_loader("A", lambda: a)
    r.register_loader("B", lambda: b)
    r.load("A")
    assert r.current is a
    r.load("B")
    assert r.current is b
    r.load("A")
    assert r.current is a  # 幂等切换


def test_registry_discovers_entry_points(monkeypatch):
    r = AdapterRegistry()
    found = _adapter("EP")

    class FakeEP:
        name = "EPProto"

        def load(self):
            return lambda: found

    class FakeEntryPoints:
        def __iter__(self):
            return iter([FakeEP()])

    monkeypatch.setattr("importlib.metadata.entry_points", lambda group=None: FakeEntryPoints())
    r.load("EPProto")
    assert r.current is found


def test_global_registry_loaded_onebot_by_conftest():
    assert registry.current is not None
    assert registry.current.name == "OneBot"
    assert registry.current.actions_cls is OneBotActions
