from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import AppConfig, RawAppConfig

ConfigT = TypeVar("ConfigT", bound=BaseModel)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON configuration: {path}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"configuration must be a JSON object: {path}")
    value.pop("$schema", None)
    return value


def load_raw_app_config(path: str | os.PathLike[str]) -> RawAppConfig:
    return RawAppConfig.model_validate(_read_json(Path(path)))


def load_app_config(
    path: str | os.PathLike[str],
    adapter_config_type: type[ConfigT],
) -> AppConfig[ConfigT]:
    config_path = Path(path)
    raw = load_raw_app_config(config_path)
    adapter_config = adapter_config_type.model_validate(raw.adapter_config)
    return AppConfig[adapter_config_type](  # type: ignore[index]
        schema_version=raw.schema_version,
        active_adapter=raw.active_adapter,
        adapter_config=adapter_config,
        runtime=raw.runtime,
        logging=raw.logging,
    )


def write_app_config(path: str | os.PathLike[str], config: RawAppConfig) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(mode="json", by_alias=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{config_path.name}.", dir=config_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
        os.replace(temp_name, config_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
