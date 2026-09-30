from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import suppress
from typing import Any, Protocol, cast

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from typing_extensions import override
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as ws_connect

from hyperot.v2.common import ActionTimeoutError, AdapterConnectionError, AdapterDisconnectedError

from .config import (
    ForwardWebSocketConfig,
    HTTPConfig,
    HTTPPostConfig,
    OneBotConnectionConfig,
    ReverseWebSocketConfig,
)


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
        except OSError as exc:
            raise AdapterConnectionError(str(exc)) from exc
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
            self._fail_pending(AdapterDisconnectedError(str(exc)))
            await self._events.put(AdapterDisconnectedError(str(exc)))


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
        try:
            response = await self._client.post(f"{self.config.url.rstrip('/')}/{action}", json=params, timeout=timeout)
        except httpx.HTTPError as exc:
            raise AdapterConnectionError(str(exc)) from exc
        return response.json()


class _ServerTransport:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.server: uvicorn.Server | None = None
        self.task: asyncio.Task[None] | None = None
        self.events: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()

    async def _start_server(self, app: FastAPI) -> None:
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.server.started:
                return
            await asyncio.sleep(0.01)
        raise AdapterConnectionError("OneBot callback server failed to start")

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

        @self.app.post(config.endpoint)
        async def receive(request: Request) -> dict[str, bool]:
            data = await request.json()
            if isinstance(data, dict):
                await self.events.put(data)
            return {"ok": True}

    async def start(self) -> None:
        await self._start_server(self.app)

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

        @self.app.websocket(config.api_path)
        async def api_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            self._api_ws = websocket
            self._api_task = asyncio.create_task(self._api_reader(websocket))
            try:
                await self._api_task
            except WebSocketDisconnect:
                pass
            finally:
                self._api_ws = None

        @self.app.websocket(config.event_path)
        async def event_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            try:
                while True:
                    data = json.loads(await websocket.receive_text())
                    if isinstance(data, dict):
                        await self.events.put(data)
            except WebSocketDisconnect:
                return

    async def start(self) -> None:
        await self._start_server(self.app)

    @override
    async def stop(self) -> None:
        if self._api_task is not None:
            self._api_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._api_task
        if self._api_ws is not None:
            await self._api_ws.close()
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

    async def _api_reader(self, websocket: WebSocket) -> None:
        try:
            while True:
                data = json.loads(await websocket.receive_text())
                if isinstance(data, dict):
                    self._resolve(data)
        except WebSocketDisconnect:
            return


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
