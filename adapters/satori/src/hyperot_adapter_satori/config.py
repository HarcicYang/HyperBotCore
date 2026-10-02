from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectionConfig(BaseModel):
    """Fields every Satori connection shares.

    ``platform`` and ``user_id`` name the login used for API calls. Satori addresses
    every request with the ``Satori-Platform`` and ``Satori-User-ID`` headers, so a
    connection has to know which of the logins reported by the SDK it talks for.
    Leaving both empty picks the first online login.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    access_token: str = ""
    platform: str = ""
    user_id: str = ""


class WebSocketConfig(ConnectionConfig):
    type: Literal["WebSocket"] = "WebSocket"
    url: str
    event_path: str = "/v1/events"
    api_url: str | None = None
    ping_interval: float = 10.0
    ping_timeout: float = 20.0


class WebHookConfig(ConnectionConfig):
    type: Literal["WebHook"] = "WebHook"
    api_url: str
    host: str = "127.0.0.1"
    port: int = 5140
    endpoint: str = "/satori"
    # Reverse authentication: the token this application hands to the SDK.
    token: str = ""
    register_webhook: bool = True


SatoriConnectionConfig = Annotated[
    WebSocketConfig | WebHookConfig,
    Field(discriminator="type"),
]


class SatoriConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    connections: tuple[SatoriConnectionConfig, ...] = (WebSocketConfig(url="ws://127.0.0.1:5140"),)
    action_timeout: float = 30.0
