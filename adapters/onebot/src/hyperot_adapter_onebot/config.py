from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    access_token: str = ""


class ForwardWebSocketConfig(ConnectionConfig):
    type: Literal["ForwardWebSocket"] = "ForwardWebSocket"
    url: str
    ping_interval: float | None = 20.0
    ping_timeout: float | None = 20.0


class ReverseWebSocketConfig(ConnectionConfig):
    type: Literal["ReverseWebSocket"] = "ReverseWebSocket"
    host: str = "127.0.0.1"
    port: int = 6700
    api_path: str = "/api"
    event_path: str = "/event"


class HTTPConfig(ConnectionConfig):
    type: Literal["HTTP"] = "HTTP"
    url: str
    timeout: float = 30.0


class HTTPPostConfig(ConnectionConfig):
    type: Literal["HTTPPost"] = "HTTPPost"
    host: str = "127.0.0.1"
    port: int = 6701
    endpoint: str = "/"
    secret: str = ""


OneBotConnectionConfig = Annotated[
    ForwardWebSocketConfig | ReverseWebSocketConfig | HTTPConfig | HTTPPostConfig,
    Field(discriminator="type"),
]


class OneBotConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    connections: tuple[OneBotConnectionConfig, ...] = (ForwardWebSocketConfig(url="ws://127.0.0.1:5004"),)
    action_timeout: float = 30.0
