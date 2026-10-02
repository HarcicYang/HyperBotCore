"""Connections to a Satori SDK.

Satori splits its transport in two: an HTTP RPC service at ``/{version}/{resource}.{method}``
and an event service that is either a WebSocket at ``/{version}/events`` or a WebHook the
SDK posts events to. Both event transports share one HTTP client for API calls, and both
resolve the login a call belongs to from the logins the SDK reports.
"""

from __future__ import annotations

import asyncio
import json
import socket
from contextlib import suppress
from typing import Any, Protocol, cast

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from pydantic import JsonValue
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as ws_connect

from hyperot.v2.common import (
    ActionRejectedError,
    AdapterConnectionError,
    AdapterDisconnectedError,
    CapabilityNotSupportedError,
    bind_error,
    connection_error,
)
from hyperot.v2.hyperogger import Logger

from .config import WebHookConfig, WebSocketConfig

logger = Logger.fetch("hyperot.v2.adapter.satori")

API_VERSION = "v1"

OP_EVENT = 0
OP_PING = 1
OP_PONG = 2
OP_IDENTIFY = 3
OP_READY = 4
OP_META = 5

ONLINE = 1


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


class SatoriTransport(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def receive(self) -> dict[str, Any]: ...

    async def call(self, route: str, params: dict[str, Any], timeout: float) -> JsonValue: ...

    def resolve_identity(self) -> tuple[str, str]: ...

    def remember_login(self, login: dict[str, Any]) -> None: ...

    def forget_login(self, login: dict[str, Any]) -> None: ...

    def logins(self) -> list[dict[str, Any]]: ...

    def proxy_urls(self) -> list[str]: ...

    def login_status(self, platform: str, user_id: str) -> int | None: ...

    def proxy_url(self, url: str) -> str: ...

    async def upload(self, files: list[tuple[str, bytes, str, str]], timeout: float) -> dict[str, str]: ...


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dict_list(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _status(login: dict[str, Any]) -> int:
    try:
        return int(login.get("status", 0))
    except (TypeError, ValueError):
        return 0


class _LoginState:
    """The logins an SDK reported, plus the identity used for outbound calls."""

    def __init__(self, platform: str = "", user_id: str = "") -> None:
        self._logins: dict[str, dict[str, Any]] = {}
        self._proxy_urls: list[str] = []
        self._preferred_platform = platform
        self._preferred_user_id = user_id

    def remember_login(self, login: dict[str, Any]) -> None:
        key = self._login_key(login)
        if key is None:
            return
        known = self._logins.setdefault(key, {})
        known.update({name: value for name, value in login.items() if value is not None})

    def forget_login(self, login: dict[str, Any]) -> None:
        key = self._login_key(login)
        if key is not None:
            self._logins.pop(key, None)

    def remember_proxy_urls(self, proxy_urls: list[str]) -> None:
        self._proxy_urls = list(proxy_urls)

    def logins(self) -> list[dict[str, Any]]:
        return list(self._logins.values())

    def proxy_urls(self) -> list[str]:
        return list(self._proxy_urls)

    def login_status(self, platform: str, user_id: str) -> int | None:
        login = self._logins.get(f"{platform}:{user_id}")
        return None if login is None else _status(login)

    def resolve_identity(self) -> tuple[str, str]:
        """Return the ``(platform, user_id)`` pair API calls are addressed to."""
        for login in self._sorted_logins():
            platform = str(login.get("platform") or "")
            user = login.get("user") or {}
            user_id = str(user.get("id") or "")
            if not platform or not user_id:
                continue
            if self._preferred_platform and platform != self._preferred_platform:
                continue
            if self._preferred_user_id and user_id != self._preferred_user_id:
                continue
            return platform, user_id
        raise AdapterDisconnectedError(
            "Satori adapter has no login to address API calls with;"
            " wait for the SDK to report one, or set platform and user_id"
        )

    def _sorted_logins(self) -> list[dict[str, Any]]:
        return sorted(self._logins.values(), key=lambda login: 0 if _status(login) == ONLINE else 1)

    @staticmethod
    def _login_key(login: dict[str, Any]) -> str | None:
        user = login.get("user") or {}
        user_id = user.get("id")
        if user_id is not None:
            return f"{login.get('platform')}:{user_id}"
        # A login without a user is only identified by its sequence number.
        sn = login.get("sn")
        return None if sn is None else f"sn:{sn}"


class SatoriHttpClient:
    """HTTP caller for the ``/v1`` API service."""

    def __init__(self, base_url: str, access_token: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
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

    def route_url(self, route: str) -> str:
        return f"/{API_VERSION}/{route.lstrip('/')}"

    def proxy_url(self, url: str) -> str:
        return f"{self.base_url}/proxy/{url}"

    async def call(
        self,
        route: str,
        params: dict[str, Any],
        timeout: float,
        identity: tuple[str, str] | None,
    ) -> JsonValue:
        client = self._client
        if client is None:
            raise AdapterDisconnectedError("Satori HTTP client is not started")
        try:
            response = await client.post(
                self.route_url(route),
                json=params or {},
                headers=_headers(self.access_token, identity),
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise connection_error(exc, label="Satori", target=self.route_url(route), kind="HTTP call") from exc
        return _response_value(response, route)

    async def upload(
        self,
        files: list[tuple[str, bytes, str, str]],
        timeout: float,
        identity: tuple[str, str] | None,
    ) -> dict[str, str]:
        client = self._client
        if client is None:
            raise AdapterDisconnectedError("Satori HTTP client is not started")
        payload = [(name, (filename, data, content_type)) for name, data, content_type, filename in files]
        try:
            response = await client.post(
                self.route_url("upload.create"),
                files=payload,
                headers=_headers(self.access_token, identity),
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise connection_error(
                exc, label="Satori", target=self.route_url("upload.create"), kind="HTTP call"
            ) from exc
        data = _response_value(response, "upload.create")
        return {str(key): str(value) for key, value in data.items()} if isinstance(data, dict) else {}


def _headers(access_token: str, identity: tuple[str, str] | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if identity is not None:
        headers["Satori-Platform"], headers["Satori-User-ID"] = identity
    return headers


def _response_value(response: httpx.Response, route: str) -> JsonValue:
    if response.status_code == 400:
        raise ActionRejectedError(f"Satori rejected the request body for {route} (HTTP 400)")
    if response.status_code == 401:
        raise AdapterConnectionError("Satori rejected the access token (HTTP 401)")
    if response.status_code == 403:
        raise ActionRejectedError(f"Satori denied permission for {route} (HTTP 403)")
    if response.status_code == 404:
        # The specification reserves 404 for an API the platform does not provide.
        raise CapabilityNotSupportedError(route)
    if response.status_code == 405:
        raise ActionRejectedError(f"Satori rejected the request method for {route}")
    if response.status_code >= 400:
        raise AdapterConnectionError(f"Satori API call {route} failed with HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise AdapterConnectionError(f"Satori returned a non-JSON response for {route}") from exc


class _ActionCallMixin:
    """Adds the API-call surface both event transports expose."""

    http: SatoriHttpClient

    async def call(self, route: str, params: dict[str, Any], timeout: float) -> JsonValue:
        # The mixin is always combined with _LoginState, which resolves the identity.
        identity = cast(_LoginState, self).resolve_identity()
        return await self.http.call(route, params, timeout, identity)

    async def upload(self, files: list[tuple[str, bytes, str, str]], timeout: float) -> dict[str, str]:
        identity = cast(_LoginState, self).resolve_identity()
        return await self.http.upload(files, timeout, identity)

    def proxy_url(self, url: str) -> str:
        return self.http.proxy_url(url)


class WebSocketEventTransport(_ActionCallMixin, _LoginState):
    """Opens the event WebSocket and speaks the Satori signal protocol."""

    def __init__(self, config: WebSocketConfig, action_timeout: float) -> None:
        _LoginState.__init__(self, config.platform, config.user_id)
        self.config = config
        api_url = config.api_url or _derive_api_url(config.url)
        self.http = SatoriHttpClient(api_url, config.access_token, action_timeout)
        self._ws: ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self._heartbeat: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()
        self._sequence = -1

    @property
    def event_url(self) -> str:
        return f"{self.config.url.rstrip('/')}{self.config.event_path}"

    @property
    def sequence(self) -> int:
        return self._sequence

    async def start(self) -> None:
        if self._ws is not None:
            return
        await self.http.start()
        try:
            self._ws = await ws_connect(
                self.event_url,
                additional_headers=_auth_headers(self.config.access_token),
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
            )
        # Anything raised here means the SDK never answered.
        except Exception as exc:
            await self.http.stop()
            raise connection_error(exc, label="Satori", target=self.event_url, kind="websocket connection") from exc
        # The specification asks the application to identify within 10 seconds.
        try:
            await self._send(OP_IDENTIFY, _identify_body(self.config.access_token, self._sequence))
        except Exception as exc:
            await self.stop()
            raise connection_error(exc, label="Satori", target=self.event_url, kind="websocket connection") from exc
        self._reader = asyncio.create_task(self._read())
        self._heartbeat = asyncio.create_task(self._beat())

    async def stop(self) -> None:
        for task in (self._reader, self._heartbeat):
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        self._reader = None
        self._heartbeat = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        await self.http.stop()
        while not self._events.empty():
            self._events.get_nowait()

    async def receive(self) -> dict[str, Any]:
        value = await self._events.get()
        if isinstance(value, BaseException):
            raise value
        return value

    async def _send(self, op: int, body: dict[str, Any] | None = None) -> None:
        ws = self._ws
        if ws is None:
            raise AdapterDisconnectedError("Satori websocket is not connected")
        payload: dict[str, Any] = {"op": op}
        if body is not None:
            payload["body"] = body
        await ws.send(json.dumps(payload))

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
                    await self._dispatch(data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await self._events.put(AdapterDisconnectedError(f"Satori websocket {self.event_url} closed: {exc}"))

    async def _dispatch(self, data: dict[str, Any]) -> None:
        op = data.get("op")
        if op == OP_EVENT:
            body = data.get("body")
            if isinstance(body, dict):
                self._sequence = _sequence_of(body)
                await self._events.put(body)
        elif op == OP_READY:
            self._ready(data.get("body") or {})
        elif op == OP_META:
            body = data.get("body") or {}
            self.remember_proxy_urls([str(url) for url in (body.get("proxy_urls") or [])])
        # PONG and unknown signals need no handling; the heartbeat keeps the socket warm.

    def _ready(self, body: dict[str, Any]) -> None:
        self.remember_proxy_urls(_string_list(body.get("proxy_urls")))
        for login in _dict_list(body.get("logins")):
            self.remember_login(login)

    async def _beat(self) -> None:
        # The specification asks the application to signal every 10 seconds.
        while True:
            try:
                await self._send(OP_PING)
            except Exception as exc:  # noqa: BLE001
                await self._events.put(AdapterDisconnectedError(f"Satori websocket heartbeat failed: {exc}"))
                return
            await asyncio.sleep(self.config.ping_interval)


def _sequence_of(body: dict[str, Any]) -> int:
    try:
        return int(body.get("sn", -1))
    except (TypeError, ValueError):
        return -1


def _identify_body(access_token: str, sequence: int) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if access_token:
        body["token"] = access_token
    if sequence >= 0:
        body["sn"] = sequence
    return body


class WebHookEventTransport(_ActionCallMixin, _LoginState):
    """Serves the endpoint the SDK posts events to."""

    def __init__(self, config: WebHookConfig, action_timeout: float) -> None:
        _LoginState.__init__(self, config.platform, config.user_id)
        self.config = config
        self.http = SatoriHttpClient(config.api_url, config.access_token, action_timeout)
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()
        self._registered = False
        self.app = FastAPI()

        @self.app.post(config.endpoint, status_code=204)
        async def receive(request: Request) -> Response:
            if self.config.token and request.headers.get("authorization") != f"Bearer {self.config.token}":
                return Response(status_code=401)
            body = await _json_body(request)
            if body is None:
                return Response(status_code=400)
            try:
                op = int(request.headers.get("Satori-Opcode", str(OP_EVENT)))
            except ValueError:
                return Response(status_code=400)
            if op == OP_META:
                self.remember_proxy_urls(_string_list(body.get("proxy_urls")))
                return Response(status_code=204)
            if op != OP_EVENT:
                return Response(status_code=202)
            await self._events.put(body)
            return Response(status_code=204)

    @property
    def event_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}{self.config.endpoint}"

    async def start(self) -> None:
        await self.http.start()
        await self._load_meta()
        if self.config.register_webhook:
            await self._register_webhook()
        await self._start_server()

    async def stop(self) -> None:
        await self._unregister_webhook()
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._server = None
        await self.http.stop()
        while not self._events.empty():
            self._events.get_nowait()

    async def receive(self) -> dict[str, Any]:
        value = await self._events.get()
        if isinstance(value, BaseException):
            raise value
        return value

    async def _load_meta(self) -> None:
        # The WebHook service has no READY signal, so meta is fetched over the API.
        data = await self.http.call("meta", {}, self.http.timeout, identity=None)
        if not isinstance(data, dict):
            return
        self.remember_proxy_urls(_string_list(data.get("proxy_urls")))
        for login in _dict_list(data.get("logins")):
            self.remember_login(login)

    async def _register_webhook(self) -> None:
        params: dict[str, Any] = {"url": self.event_url}
        if self.config.token:
            params["token"] = self.config.token
        data = await self.http.call("meta/webhook.create", params, self.http.timeout, identity=None)
        self._registered = bool(data)
        if data:
            logger.info(f"Satori webhook registered: {self.event_url}")

    async def _unregister_webhook(self) -> None:
        if not self._registered:
            return
        self._registered = False
        # Leaving the registration behind would keep pointing the SDK at a dead port.
        with suppress(Exception):
            await self.http.call("meta/webhook.delete", {"url": self.event_url}, self.http.timeout, identity=None)

    async def _start_server(self) -> None:
        target = f"{self.config.host}:{self.config.port}"
        if (conflict := _bind_conflict(self.config.host, self.config.port)) is not None:
            raise bind_error(conflict, label="Satori", target=target) from conflict
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="warning",
            log_config=None,
        )
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(200):
            if self._task.done():
                error = self._task.exception()
                self._task = None
                self._server = None
                if error is None:
                    raise AdapterConnectionError(f"Satori webhook listener on {target} stopped early")
                raise bind_error(error, label="Satori", target=target) from error
            if self._server.started:
                return
            await asyncio.sleep(0.01)
        raise AdapterConnectionError(f"Satori webhook listener on {target} failed to start in time")


async def _json_body(request: Request) -> dict[str, Any] | None:
    try:
        data = json.loads(await request.body())
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _auth_headers(access_token: str) -> dict[str, str] | None:
    return {"Authorization": f"Bearer {access_token}"} if access_token else None


def _derive_api_url(url: str) -> str:
    if url.startswith("wss://"):
        return "https://" + url[len("wss://") :]
    if url.startswith("ws://"):
        return "http://" + url[len("ws://") :]
    return url


def build_transport(config: Any, action_timeout: float = 30.0) -> SatoriTransport:
    match config:
        case WebSocketConfig():
            return cast(SatoriTransport, WebSocketEventTransport(config, action_timeout))
        case WebHookConfig():
            return cast(SatoriTransport, WebHookEventTransport(config, action_timeout))
    raise TypeError(f"unsupported Satori connection: {type(config).__name__}")


__all__ = [
    "API_VERSION",
    "ONLINE",
    "OP_EVENT",
    "OP_IDENTIFY",
    "OP_META",
    "OP_PING",
    "OP_PONG",
    "OP_READY",
    "SatoriHttpClient",
    "SatoriTransport",
    "WebHookEventTransport",
    "WebSocketEventTransport",
    "build_transport",
]
