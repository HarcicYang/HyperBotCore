import json
import queue
import threading

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as wsc


async def httpx_get(url: str, headers: dict | None = None, timeout: float | None = None) -> httpx.Response:
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        return await client.get(url)


async def httpx_post(
    url: str,
    json: dict | None = None,
    data: str | None = None,
    headers: dict | None = None,
    timeout: float | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
        return await client.post(url, json=json, data=data)  # pyrefly: ignore[bad-argument-type]


class WebsocketConnection:
    def __init__(self, url: str, auth: str = ""):
        self.ws: ClientConnection | None = None
        self.url = url
        self.auth = auth

    async def connect(self) -> None:
        if self.auth:
            self.ws = await wsc(self.url, header={"Authorization": "Bearer " + self.auth})
        else:
            self.ws = await wsc(self.url)

    async def send(self, message: str) -> None:
        if self.ws is None:
            raise RuntimeError("没有建立连接")
        await self.ws.send(message)

    async def close(self) -> None:
        if self.ws is None:
            raise RuntimeError("没有建立连接")
        await self.ws.close()

    async def recv(self) -> dict | None:
        if self.ws is None:
            raise RuntimeError("没有建立连接")
        return json.loads(await self.ws.recv())


class HTTPConnection:
    def __init__(self, url: str, listener_url: str, listener_endpoint: str = "/", auth: str = ""):
        self.url = url
        listener_url = listener_url.replace("http://", "")
        listener_url = listener_url.replace("https://", "")
        self.listener_url = listener_url.split(":")[0]
        self.listener_endpoint = listener_endpoint
        try:
            self.port = int(listener_url.split(":")[1])
        except IndexError:
            self.port = 8080
        self.reports = queue.Queue()
        self.auth = auth

        self.listener_started = False
        self._server: uvicorn.Server | None = None
        self.app = FastAPI()

        @self.app.post(self.listener_endpoint)
        async def listener(request: Request) -> JSONResponse:
            self.reports.put(await request.json())
            return JSONResponse({})

    def __start_listener(self) -> None:
        config = uvicorn.Config(self.app, host=self.listener_url, port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        threading.Thread(target=self._server.run, daemon=True).start()
        self.listener_started = True

    async def connect(self) -> None:
        if not self.listener_started:
            self.__start_listener()
        await httpx_post(self.url, {})

    async def recv(self) -> dict:
        return self.reports.get()

    async def send(self, endpoint: str, data: dict, echo: str) -> None:
        if self.auth:
            response = await httpx_post(
                f"{self.url}/{endpoint}", json=data, headers={"Authorization": f"Bearer {self.auth}"}
            )
        else:
            response = await httpx_post(f"{self.url}/{endpoint}", json=data)
        res = response.json()
        res["echo"] = echo
        self.reports.put(res)

    async def close(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
