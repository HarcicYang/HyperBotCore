from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import socket
import uuid
from contextlib import suppress
from typing import Any, Protocol, cast

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from typing_extensions import override
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as ws_connect

from hyperot.v2.common import (
    ActionRejectedError,
    ActionTimeoutError,
    AdapterConnectionError,
    AdapterDisconnectedError,
    bind_error,
    connection_error,
)
from hyperot.v2.hyperogger import Logger

from .config import (
    ForwardWebSocketConfig,
    HTTPConfig,
    HTTPPostConfig,
    OneBotConnectionConfig,
    ReverseWebSocketConfig,
)


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
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def receive(self) -> dict[str, Any]: ...

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]: ...


class _PendingMixin:
    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def _new_echo(self) -> str:
        return f"hyperot_{uuid.uuid4().hex[:12]}"

    def _resolve(self, data: dict[str, Any]) -> bool:
        echo = data.get("echo")
        if not isinstance(echo, str):
            return False
        future = self._pending.pop(echo, None)
        if future is not None and not future.done():
            future.set_result(data)
        return True

    def _fail_pending(self, exc: BaseException) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()


class ForwardWebSocketTransport(_PendingMixin):
    def __init__(self, config: ForwardWebSocketConfig) -> None:
        super().__init__()
        self.config = config
        self._ws: ClientConnection | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()

    async def start(self) -> None:
        if self._ws is not None:
            return
        headers = {"Authorization": f"Bearer {self.config.access_token}"} if self.config.access_token else None
        try:
            self._ws = await ws_connect(
                self.config.url,
                additional_headers=headers,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_timeout,
            )
        # Anything raised here means the OneBot end never answered.
        except Exception as exc:
            raise connection_error(
                exc,
                label="OneBot",
                target=self.config.url,
                kind="websocket connection",
            ) from exc
        self._reader_task = asyncio.create_task(self._reader())

    async def stop(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        while not self._events.empty():
            self._events.get_nowait()
        self._fail_pending(AdapterDisconnectedError("OneBot websocket closed"))

    async def receive(self) -> dict[str, Any]:
        value = await self._events.get()
        if isinstance(value, BaseException):
            raise value
        return value

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        if self._ws is None:
            raise AdapterDisconnectedError("OneBot websocket is not connected")
        echo = self._new_echo()
        future = asyncio.get_running_loop().create_future()
        self._pending[echo] = future
        payload = {"action": action, "params": params, "echo": echo}
        await self._ws.send(json.dumps(payload))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            self._pending.pop(echo, None)
            raise ActionTimeoutError(f"OneBot action timed out: {action}") from exc

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                if not isinstance(data, dict):
                    continue
                if not self._resolve(data):
                    await self._events.put(data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            dropped = AdapterDisconnectedError(f"OneBot websocket {self.config.url} closed: {exc}")
            self._fail_pending(dropped)
            await self._events.put(dropped)


class HTTPTransport:
    def __init__(self, config: HTTPConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        await self._client.aclose()

    async def receive(self) -> dict[str, Any]:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.config.access_token}"} if self.config.access_token else None
        try:
            response = await self._client.post(
                f"{self.config.url.rstrip('/')}/{action}",
                json=params,
                headers=headers,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            target = f"{self.config.url.rstrip('/')}/{action}"
            raise connection_error(exc, label="OneBot", target=target, kind="HTTP action call") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise AdapterConnectionError(f"OneBot HTTP returned non-JSON response: {response.status_code}") from exc
        if response.status_code >= 400:
            retcode = data.get("retcode", response.status_code) if isinstance(data, dict) else response.status_code
            raise ActionRejectedError(f"{action} failed with HTTP {response.status_code} retcode={retcode}")
        if not isinstance(data, dict):
            raise AdapterConnectionError(f"OneBot HTTP returned invalid response: {type(data).__name__}")
        return data


class _ServerTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None
        self.task: asyncio.Task[None] | None = None
        self.events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()

    async def _start_server(self, app: FastAPI, *, label: str, kind: str) -> None:
        target = f"{self.host}:{self.port}"
        if (conflict := _bind_conflict(self.host, self.port)) is not None:
            raise bind_error(conflict, label=label, target=target) from conflict
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.task.done():
                error = self.task.exception()
                self.task = None
                self.server = None
                if error is None:
                    raise AdapterConnectionError(f"OneBot {kind} listener on {target} stopped early")
                raise bind_error(error, label=label, target=target) from error
            if self.server.started:
                return
            await asyncio.sleep(0.01)
        raise AdapterConnectionError(f"OneBot {kind} listener on {target} failed to start in time")

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


class HTTPPostTransport(_ServerTransport):
    def __init__(self, config: HTTPPostConfig) -> None:
        super().__init__(config.host, config.port)
        self.config = config
        self.app = FastAPI()

        @self.app.post(config.endpoint, status_code=204)
        async def receive(request: Request) -> Response:
            body = await request.body()
            if self.config.secret:
                signature = request.headers.get("X-Signature")
                if not signature:
                    return Response(status_code=401)
                expected = hmac.new(self.config.secret.encode(), body, hashlib.sha1).hexdigest()
                if not hmac.compare_digest(signature, f"sha1={expected}"):
                    return Response(status_code=403)
            try:
                data = json.loads(body)
            except ValueError:
                return Response(status_code=400)
            if isinstance(data, dict):
                await self.events.put(data)
            return Response(status_code=204)

    async def start(self) -> None:
        await self._start_server(self.app, label="OneBot", kind="HTTPPost callback")

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise AdapterConnectionError(f"HTTPPost transport cannot execute action: {action}")


class ReverseWebSocketTransport(_PendingMixin, _ServerTransport):
    def __init__(self, config: ReverseWebSocketConfig) -> None:
        _ServerTransport.__init__(self, config.host, config.port)
        _PendingMixin.__init__(self)
        self.config = config
        self.app = FastAPI()
        self._api_ws: WebSocket | None = None
        self._api_task: asyncio.Task[None] | None = None

        @self.app.websocket("/")
        async def root_endpoint(websocket: WebSocket) -> None:
            role = websocket.headers.get("X-Client-Role")
            if role == "API":
                await self._run_api(websocket)
            elif role == "Event":
                await self._run_event(websocket)
            elif role == "Universal":
                await self._run_universal(websocket)
            else:
                await self._reject(websocket, "unknown connection role")

        @self.app.websocket(config.api_path)
        async def api_endpoint(websocket: WebSocket) -> None:
            role = websocket.headers.get("X-Client-Role")
            if role == "Universal":
                await self._run_universal(websocket)
            elif role == "Event":
                await self._run_event(websocket)
            else:
                await self._run_api(websocket)

        @self.app.websocket(config.event_path)
        async def event_endpoint(websocket: WebSocket) -> None:
            role = websocket.headers.get("X-Client-Role")
            if role == "Universal":
                await self._run_universal(websocket)
            elif role == "API":
                await self._run_api(websocket)
            else:
                await self._run_event(websocket)

    async def start(self) -> None:
        await self._start_server(self.app, label="OneBot", kind="reverse websocket")

    @override
    async def stop(self) -> None:
        if self._api_task is not None:
            self._api_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._api_task
        if self._api_ws is not None:
            await self._api_ws.close()
            self._api_ws = None
        self._fail_pending(AdapterDisconnectedError("OneBot reverse websocket closed"))
        await super().stop()

    async def call(self, action: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
        if self._api_ws is None:
            raise AdapterDisconnectedError("OneBot reverse API websocket is not connected")
        echo = self._new_echo()
        future = asyncio.get_running_loop().create_future()
        self._pending[echo] = future
        await self._api_ws.send_text(json.dumps({"action": action, "params": params, "echo": echo}))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            self._pending.pop(echo, None)
            raise ActionTimeoutError(f"OneBot action timed out: {action}") from exc

    def _authorized(self, websocket: WebSocket) -> bool:
        if not self.config.access_token:
            return True
        return (
            websocket.headers.get("authorization") == f"Bearer {self.config.access_token}"
            or websocket.query_params.get("access_token") == self.config.access_token
        )

    async def _reject(self, websocket: WebSocket, reason: str) -> None:
        # Closing 1008 is invisible to the protocol end, so say why in the log instead.
        Logger.fetch("hyperot.v2.adapter.onebot").warning(f"rejected OneBot reverse websocket: {reason}")
        await websocket.close(code=1008)

    async def _run_api(self, websocket: WebSocket) -> None:
        if not self._authorized(websocket):
            await self._reject(websocket, "access_token mismatch")
            return
        await websocket.accept()
        old = self._api_ws
        if old is not None and old is not websocket:
            with suppress(Exception):
                await old.close()
        self._api_ws = websocket
        task = asyncio.create_task(self._api_reader(websocket))
        self._api_task = task
        try:
            await task
        except Exception as exc:  # noqa: BLE001
            self._fail_pending(AdapterDisconnectedError(str(exc)))
        finally:
            if self._api_ws is websocket:
                self._api_ws = None
            if self._api_task is task:
                self._api_task = None
            self._fail_pending(AdapterDisconnectedError("OneBot reverse API websocket closed"))

    async def _run_event(self, websocket: WebSocket) -> None:
        if not self._authorized(websocket):
            await self._reject(websocket, "access_token mismatch")
            return
        await websocket.accept()
        try:
            while True:
                data = json.loads(await websocket.receive_text())
                if isinstance(data, dict):
                    await self.events.put(data)
        except (WebSocketDisconnect, ValueError):
            return

    async def _run_universal(self, websocket: WebSocket) -> None:
        if not self._authorized(websocket):
            await self._reject(websocket, "access_token mismatch")
            return
        await websocket.accept()
        old = self._api_ws
        if old is not None and old is not websocket:
            with suppress(Exception):
                await old.close()
        self._api_ws = websocket
        try:
            while True:
                data = json.loads(await websocket.receive_text())
                if not isinstance(data, dict):
                    continue
                if not self._resolve(data):
                    await self.events.put(data)
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            if self._api_ws is websocket:
                self._api_ws = None
            self._fail_pending(AdapterDisconnectedError("OneBot reverse websocket closed"))

    async def _api_reader(self, websocket: WebSocket) -> None:
        try:
            while True:
                data = json.loads(await websocket.receive_text())
                if isinstance(data, dict):
                    self._resolve(data)
        except WebSocketDisconnect:
            return
        except Exception as exc:
            self._fail_pending(AdapterDisconnectedError(str(exc)))
            raise


def build_transport(config: OneBotConnectionConfig) -> ActionTransport:
    match config:
        case ForwardWebSocketConfig():
            return cast(ActionTransport, ForwardWebSocketTransport(config))
        case ReverseWebSocketConfig():
            return cast(ActionTransport, ReverseWebSocketTransport(config))
        case HTTPConfig():
            return cast(ActionTransport, HTTPTransport(config))
        case HTTPPostConfig():
            return cast(ActionTransport, HTTPPostTransport(config))
    raise TypeError(f"unsupported OneBot connection: {type(config).__name__}")
