from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    access_token: str = ""


class WebSocketConfig(ConnectionConfig):
    type: Literal["WebSocket"] = "WebSocket"
    url: str
    event_path: str = "/event"
    api_url: str | None = None
    ping_interval: float | None = 20.0
    ping_timeout: float | None = 20.0


class SSEConfig(ConnectionConfig):
    type: Literal["SSE"] = "SSE"
    url: str
    event_path: str = "/event"
    api_url: str | None = None
    reconnect_delay: float = 3.0


class WebHookConfig(ConnectionConfig):
    type: Literal["WebHook"] = "WebHook"
    api_url: str
    host: str = "127.0.0.1"
    port: int = 6700
    endpoint: str = "/"


MilkyConnectionConfig = Annotated[
    WebSocketConfig | SSEConfig | WebHookConfig,
    Field(discriminator="type"),
]


class MilkyConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    connections: tuple[MilkyConnectionConfig, ...] = (WebSocketConfig(url="ws://127.0.0.1:5005"),)
    action_timeout: float = 30.0
