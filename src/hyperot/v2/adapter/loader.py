from __future__ import annotations

import importlib
import importlib.metadata
from importlib.resources import files
from typing import Any, cast

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ..common import AdapterNotLoadedError, ConfigurationError
from .manifest import AdapterManifest
from .protocol import Adapter

HYPEROT_API_VERSION = 2
ADAPTER_ENTRY_POINT_GROUP = "hyperot.adapters"


def load_manifest(package: str) -> AdapterManifest:
    try:
        resource = files(package).joinpath("manifest.json")
        raw = resource.read_text(encoding="utf-8")
    except (ImportError, FileNotFoundError) as exc:
        raise AdapterNotLoadedError(f"adapter package is not importable: {package}") from exc
    return AdapterManifest.model_validate_json(raw)


def find_adapter_entrypoint(adapter_id: str) -> importlib.metadata.EntryPoint:
    entrypoints = importlib.metadata.entry_points(group=ADAPTER_ENTRY_POINT_GROUP)
    for entrypoint in entrypoints:
        if entrypoint.name == adapter_id:
            return entrypoint
    raise AdapterNotLoadedError(f"adapter {adapter_id!r} is not installed; install its package and retry")


def validate_manifest(manifest: AdapterManifest) -> None:
    if manifest.api_version != HYPEROT_API_VERSION:
        raise ConfigurationError(
            f"adapter API version {manifest.api_version} is incompatible with hyperot API {HYPEROT_API_VERSION}"
        )
    if manifest.entrypoint_module.split(".", 1)[0] != manifest.package:
        raise ConfigurationError("adapter entrypoint module does not match package")


def check_hyperot_requirement(manifest: AdapterManifest) -> None:
    try:
        installed = importlib.metadata.version("hyper-bot")
    except importlib.metadata.PackageNotFoundError:
        return
    if Version(installed) not in SpecifierSet(manifest.requires_hyperot):
        raise ConfigurationError(
            f"adapter {manifest.id!r} requires hyper-bot {manifest.requires_hyperot}, found {installed}"
        )


def create_adapter(manifest: AdapterManifest) -> Adapter[Any]:
    validate_manifest(manifest)
    module = importlib.import_module(manifest.entrypoint_module)
    factory = getattr(module, manifest.entrypoint_attr)
    adapter = factory()
    if adapter.manifest.id != manifest.id:
        raise ConfigurationError("adapter factory returned a mismatched manifest")
    return cast(Adapter[Any], adapter)


def create_adapter_by_id(adapter_id: str) -> Adapter[Any]:
    entrypoint = find_adapter_entrypoint(adapter_id)
    factory = entrypoint.load()
    adapter = factory()
    if adapter.manifest.id != adapter_id:
        raise ConfigurationError(f"adapter entrypoint {adapter_id!r} returned manifest id {adapter.manifest.id!r}")
    validate_manifest(adapter.manifest)
    check_hyperot_requirement(adapter.manifest)
    return cast(Adapter[Any], adapter)
