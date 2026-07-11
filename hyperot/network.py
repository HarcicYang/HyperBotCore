import httpx
import queue
import flask
import traceback
import json
import logging
import threading
from websockets.asyncio.client import connect as wsc
from websockets.asyncio.client import ClientConnection


async def httpx_get(url: str, headers: dict = None) -> httpx.Response:
    async with httpx.AsyncClient(headers=headers) as client:
        return await client.get(url)

async def httpx_post(url: str, json: dict, headers: dict = None) -> httpx.Response:
    async with httpx.AsyncClient(headers=headers) as client:
        return await client.post(url, json=json)


class WebsocketConnection:
    def __init__(self, url: str, auth: str = ""):
        self.ws: ClientConnection = None
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

    async def recv(self) -> dict:
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
        self.app = flask.Flask(__name__)
        self.app.config["LOGGER_HANDLER_POLICY"] = "never"
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        self.reports = queue.Queue()
        self.auth = auth

        self.listener_started = False

    def __start_listener(self) -> None:
        @self.app.route(self.listener_endpoint, methods=["POST"])
        def listener():
            self.reports.put(flask.request.json)
            return {}

            # self.app.run(host=self.listener_url, port=self.port)

        threading.Thread(target=lambda: self.app.run(host=self.listener_url, port=self.port)).start()
        self.listener_started = True

    async def connect(self) -> None:
        if not self.listener_started:
            self.__start_listener()
        await httpx_post(self.url, {})
        traceback.print_exc()

    async def recv(self) -> dict:
        return self.reports.get()

    async def send(self, endpoint: str, data: dict, echo: str) -> None:
        if self.auth:
            response = await httpx_post(f"{self.url}/{endpoint}", json=data, headers={"Authorization": f"Bearer {self.auth}"})
        else:
            response = await httpx_post(f"{self.url}/{endpoint}", json=data)
        res = response.json()
        res["echo"] = echo
        self.reports.put(res)

    @staticmethod
    def close() -> None:
        shutdown_func = flask.request.environ.get('werkzeug.server.shutdown')
        if shutdown_func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        shutdown_func()

