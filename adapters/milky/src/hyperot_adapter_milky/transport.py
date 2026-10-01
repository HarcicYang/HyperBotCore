from __future__ import annotations

import asyncio
import json
import socket
from contextlib import suppress
from typing import Any, Protocol, cast

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from typing_extensions import override
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as ws_connect

from hyperot.v2.common import (
    ActionRejectedError,
    AdapterConnectionError,
    AdapterDisconnectedError,
    bind_error,
    connection_error,
)

from .config import SSEConfig, WebHookConfig, WebSocketConfig


def _bind_conflict(host: str, port: int) -> OSError | None:
    """Return the error uvicorn would hit while binding, before it can exit the process.

    uvicorn calls ``sys.exit`` when it cannot bind, which tears the event loop down before
    the waiting coroutine can report anything, so the address is checked here first.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return exc
    conflict: OSError | None = None
    for family, kind, proto, _canonname, address in infos:
        try:
            with socket.socket(family, kind, proto) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(address)
                probe.listen(1)
            return None
        except OSError as exc:
            conflict = exc
    return conflict


class ActionTransport(Protocol):
    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]: ...


class MilkyTransport(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def receive(self) -> dict[str, Any]: ...

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]: ...


def _auth_headers(access_token: str) -> dict[str, str] | None:
    return {"Authorization": f"Bearer {access_token}"} if access_token else None


def _derive_api_url(url: str, event_path: str) -> str:
    if url.startswith("wss://"):
        base = "https://" + url[len("wss://") :]
    elif url.startswith("ws://"):
        base = "http://" + url[len("ws://") :]
    else:
        base = url
    if event_path and base.endswith(event_path):
        base = base[: -len(event_path)]
    return base.rstrip("/")


class MilkyHttpClient:
    """HTTP action caller for the `/api` endpoint the protocol end exposes."""

    def __init__(self, base_url: str, access_token: str, timeout: float) -> None:
        self.base_url = base_url
        self.access_token = access_token
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def stop(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        client = self._client
        if client is None:
            raise AdapterDisconnectedError("Milky HTTP client is not started")
        try:
            response = await client.post(
                f"/api/{action}",
                json=params or {},
                headers=_auth_headers(self.access_token),
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise connection_error(exc, label="Milky", target=f"{self.base_url}/api/{action}", kind="HTTP call") from exc
        if response.status_code == 401:
            raise AdapterConnectionError("Milky rejected the access token (HTTP 401)")
        if response.status_code == 404:
            raise ActionRejectedError(f"Milky has no API named {action}")
        if response.status_code == 415:
            raise ActionRejectedError("Milky rejected the request content type")
        if response.status_code >= 400:
            raise AdapterConnectionError(f"Milky API call failed with HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise AdapterConnectionError(f"Milky returned a non-JSON response (HTTP {response.status_code})") from exc
        if not isinstance(data, dict):
            raise AdapterConnectionError("Milky returned an invalid response body")
        return data


class _HttpActionMixin:
    def __init__(self, http: MilkyHttpClient) -> None:
        self._http = http

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        return await self._http.call(action, params, timeout)


class WebSocketEventTransport(_HttpActionMixin):
    def __init__(self, config: WebSocketConfig, action_timeout: float) -> None:
        api_url = config.api_url or _derive_api_url(config.url, config.event_path)
        super().__init__(MilkyHttpClient(api_url, config.access_token, action_timeout))
        self.config = config
        self._ws: ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()

    @property
    def event_url(self) -> str:
        return f"{self.config.url.rstrip('/')}{self.config.event_path}"

    async def start(self) -> None:
        if self._ws is not None:
            return
        await self._http.start()
        try:
            self._ws = await ws_connect(
                self.event_url,
                additional_headers=_auth_headers(self.config.access_token),
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
            )
        # Anything raised here means the Milky end never answered.
        except Exception as exc:
            await self._http.stop()
            raise connection_error(exc, label="Milky", target=self.event_url, kind="websocket connection") from exc
        self._reader = asyncio.create_task(self._read())

    async def stop(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader
            self._reader = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        await self._http.stop()
        while not self._events.empty():
            self._events.get_nowait()

    async def receive(self) -> dict[str, Any]:
        value = await self._events.get()
        if isinstance(value, BaseException):
            raise value
        return value

    async def _read(self) -> None:
        ws = self._ws
        assert ws is not None
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(data, dict):
                    await self._events.put(data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await self._events.put(AdapterDisconnectedError(f"Milky websocket {self.event_url} closed: {exc}"))


class SSEEventTransport(_HttpActionMixin):
    def __init__(self, config: SSEConfig, action_timeout: float) -> None:
        api_url = config.api_url or config.url.rstrip("/")
        super().__init__(MilkyHttpClient(api_url, config.access_token, action_timeout))
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._reader: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()

    @property
    def event_url(self) -> str:
        return f"{self.config.url.rstrip('/')}{self.config.event_path}"

    async def start(self) -> None:
        if self._reader is not None:
            return
        await self._http.start()
        self._client = httpx.AsyncClient(timeout=None)
        self._reader = asyncio.create_task(self._read())

    async def stop(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader
            self._reader = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        await self._http.stop()
        while not self._events.empty():
            self._events.get_nowait()

    async def receive(self) -> dict[str, Any]:
        value = await self._events.get()
        if isinstance(value, BaseException):
            raise value
        return value

    async def _read(self) -> None:
        client = self._client
        assert client is not None
        while True:
            data: list[str] = []
            try:
                async with client.stream(
                    "GET",
                    self.event_url,
                    headers=_auth_headers(self.config.access_token),
                ) as response:
                    if response.status_code >= 400:
                        await self._events.put(
                            AdapterConnectionError(f"Milky event stream failed with HTTP {response.status_code}")
                        )
                        return
                    async for line in response.aiter_lines():
                        if line.startswith(":"):
                            continue
                        if line.strip():
                            field, _, value = line.partition(":")
                            if field == "data":
                                data.append(value.strip())
                            continue
                        if data:
                            event = _sse_payload(data)
                            data.clear()
                            if event is not None:
                                await self._events.put(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await self._events.put(AdapterDisconnectedError(str(exc)))
            await asyncio.sleep(self.config.reconnect_delay)


def _sse_payload(chunks: list[str]) -> dict[str, Any] | None:
    body = "".join(chunks).strip()
    if not body:
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class _ServerTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None
        self.task: asyncio.Task[None] | None = None
        self.events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()

    async def _start_server(self, app: FastAPI) -> None:
        target = f"{self.host}:{self.port}"
        if (conflict := _bind_conflict(self.host, self.port)) is not None:
            raise bind_error(conflict, label="Milky", target=target) from conflict
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.task.done():
                error = self.task.exception()
                self.task = None
                self.server = None
                if error is None:
                    raise AdapterConnectionError(f"Milky webhook listener on {target} stopped early")
                raise bind_error(error, label="Milky", target=target) from error
            if self.server.started:
                return
            await asyncio.sleep(0.01)
        raise AdapterConnectionError(f"Milky webhook listener on {target} failed to start in time")

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        if self.task is not None:
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        self.server = None

    async def receive(self) -> dict[str, Any]:
        value = await self.events.get()
        if isinstance(value, BaseException):
            raise value
        return value


class WebHookEventTransport(_HttpActionMixin, _ServerTransport):
    def __init__(self, config: WebHookConfig, action_timeout: float) -> None:
        _ServerTransport.__init__(self, config.host, config.port)
        _HttpActionMixin.__init__(
            self, MilkyHttpClient(config.api_url.rstrip("/"), config.access_token, action_timeout)
        )
        self.config = config
        self.app = FastAPI()

        @self.app.post(config.endpoint, status_code=204)
        async def receive(request: Request) -> Response:
            token = self.config.access_token
            if token and request.headers.get("authorization") != f"Bearer {token}":
                return Response(status_code=401)
            try:
                data = json.loads(await request.body())
            except ValueError:
                return Response(status_code=400)
            if isinstance(data, dict):
                await self.events.put(data)
            return Response(status_code=204)

    async def start(self) -> None:
        await self._http.start()
        await self._start_server(self.app)

    @override
    async def stop(self) -> None:
        await _ServerTransport.stop(self)
        await self._http.stop()
        while not self.events.empty():
            self.events.get_nowait()


def build_transport(config: Any, action_timeout: float = 30.0) -> MilkyTransport:
    match config:
        case WebSocketConfig():
            return cast(MilkyTransport, WebSocketEventTransport(config, action_timeout))
        case SSEConfig():
            return cast(MilkyTransport, SSEEventTransport(config, action_timeout))
        case WebHookConfig():
            return cast(MilkyTransport, WebHookEventTransport(config, action_timeout))
    raise TypeError(f"unsupported Milky connection: {type(config).__name__}")


__all__ = [
    "ActionTransport",
    "MilkyHttpClient",
    "MilkyTransport",
    "SSEEventTransport",
    "WebHookEventTransport",
    "WebSocketEventTransport",
    "build_transport",
]
