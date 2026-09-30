import pytest
from hyperot_adapter_onebot import create_adapter

from hyperot.v2.adapter import create_adapter_by_id
from hyperot.v2.common import AdapterNotLoadedError


class FakeEntryPoint:
    name = "onebot"

    def load(self):
        return create_adapter


def test_create_adapter_by_id_uses_entrypoint(monkeypatch):
    monkeypatch.setattr(
        "hyperot.v2.adapter.loader.importlib.metadata.entry_points",
        lambda *, group: [FakeEntryPoint()],
    )

    adapter = create_adapter_by_id("onebot")

    assert adapter.manifest.id == "onebot"


def test_create_adapter_by_id_rejects_missing_entrypoint(monkeypatch):
    monkeypatch.setattr(
        "hyperot.v2.adapter.loader.importlib.metadata.entry_points",
        lambda *, group: [],
    )

    with pytest.raises(AdapterNotLoadedError, match="not installed"):
        create_adapter_by_id("onebot")
