from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ConfigT = TypeVar("ConfigT", bound=BaseModel)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    reconnect_initial_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    reconnect_max_attempts: int | None = Field(default=5, ge=1)
    shutdown_timeout: float = 10.0
    action_timeout: float = 30.0


class LoggingConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    level: str = "INFO"
    use_nerd_font: bool = False
    global_handlers: bool = False
    stream: Literal["stdout", "stderr"] = "stdout"


class RawAppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    schema_version: int = Field(default=1, alias="schema_version")
    active_adapter: str | None = None
    adapter_config: dict[str, JsonValue]
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class AppConfig(BaseModel, Generic[ConfigT]):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: int = 1
    active_adapter: str | None
    adapter_config: ConfigT
    runtime: RuntimeConfig
    logging: LoggingConfig


def app_config_json_schema(config_type: type[BaseModel]) -> dict[str, Any]:
    schema = RawAppConfig.model_json_schema()
    schema["properties"]["adapter_config"] = config_type.model_json_schema()
    return schema
