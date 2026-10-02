import asyncio
import importlib.util
import json
import socket
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response, WebSocket
from hyperot_adapter_satori import SatoriConfig, create_adapter

from hyperot.v2 import Client
from hyperot.v2.actions import GetBotProfileAction, SendMessageAction
from hyperot.v2.common import SceneType
from hyperot.v2.events import MessageReceivedEvent
from hyperot.v2.messages import Message, Text

_ROOT = Path(__file__).resolve().parents[3]

LOGIN = {"sn": 1, "platform": "qq", "user": {"id": "10000", "nick": "bot"}, "status": 1}

MESSAGE_EVENT = {
    "sn": 2,
    "type": "message-created",
    "timestamp": 1700000000000,
    "login": {"platform": "qq", "user": {"id": "10000"}, "status": 1},
    "channel": {"id": "chan1", "type": 0, "name": "general"},
    "guild": {"id": "guild1", "name": "group"},
    "user": {"id": "20001", "nick": "someone"},
    "message": {"id": "msg1", "content": 'hi <at id="10000"/>'},
}

# The smoke scripts answer `.ping`, so the script-driven test pushes that content.
PING_EVENT = {**MESSAGE_EVENT, "message": {"id": "ping1", "content": ".ping"}}


class FakeSatoriEnd:
    """A protocol end that serves the Satori event websocket and ``/v1`` API routes."""

    def __init__(self) -> None:
        self.app = FastAPI()
        self.events: asyncio.Queue[dict] = asyncio.Queue()
        self.calls: list[tuple[str, dict, dict]] = []
        self.identified: list[dict] = []
        self.server: uvicorn.Server | None = None

        @self.app.post("/v1/meta")
        async def meta(_request: Request) -> Response:
            return Response(content=json.dumps({"logins": [LOGIN], "proxy_urls": []}), media_type="application/json")

        @self.app.websocket("/v1/events")
        async def events(websocket: WebSocket) -> None:
            await websocket.accept()
            identify = json.loads(await websocket.receive_text())
            self.identified.append(identify)
            await websocket.send_text(json.dumps({"op": 4, "body": {"logins": [LOGIN], "proxy_urls": []}}))

            # Drain the heartbeat signals in the background so the close handshake
            # the adapter starts on shutdown completes instead of timing out.
            async def drain() -> None:
                try:
                    while True:
                        await websocket.receive_text()
                except Exception:  # noqa: BLE001
                    return

            asyncio.create_task(drain())
            while True:
                payload = await self.events.get()
                await websocket.send_text(json.dumps({"op": 0, "body": payload}))

        @self.app.post("/v1/{action}")
        async def api(action: str, request: Request) -> Response:
            if action == "upload.create":
                # multipart; the body itself is not what this fake end checks.
                await request.body()
                params: dict = {"multipart": True}
            else:
                params = await request.json()
            self.calls.append((action, params, dict(request.headers)))
            return _route_result(action, params)

    async def start(self) -> int:
        config = uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.server.started:
                return int(self.server.servers[0].sockets[0].getsockname()[1])
            await asyncio.sleep(0.01)
        raise AssertionError("fake Satori protocol end failed to start")

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        await asyncio.sleep(0)


def _route_result(route: str, params: dict) -> Response:
    payload: object
    match route:
        case "login.get":
            payload = LOGIN
        case "message.create":
            payload = [{"id": "sent1", "channel": {"id": params.get("channel_id")}}]
        case "user.channel.create":
            payload = {"id": "direct1", "type": 1}
        case "upload.create":
            payload = {"banner": "internal:qq/10000/_tmp/banner.png"}
        case _:
            payload = {}
    return Response(content=json.dumps(payload), media_type="application/json")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_websocket_events_and_http_actions():
    async def run() -> None:
        end = FakeSatoriEnd()
        port = await end.start()
        adapter = create_adapter()
        config = SatoriConfig.model_validate(
            {"connections": [{"type": "WebSocket", "url": f"ws://127.0.0.1:{port}", "access_token": "tok"}]}
        )
        await adapter.start(config)
        try:
            await end.events.put(MESSAGE_EVENT)
            event = await asyncio.wait_for(adapter.receive(), timeout=5)
            assert str(event.message) == "hi @10000"  # type: ignore[attr-defined]
            assert event.scene_id == "chan1"  # type: ignore[attr-defined]
            assert event.is_mentioned  # type: ignore[attr-defined]

            profile = await adapter.execute(GetBotProfileAction())
            assert (profile.user_id, profile.display_name) == ("10000", "bot")

            sent = await adapter.execute(
                SendMessageAction(
                    scene_type=SceneType.GUILD,
                    scene_id="chan1",
                    message=Message(Text(text="hello")),
                )
            )
            assert sent.message_id == "chan1:sent1"
            route, params, headers = end.calls[-1]
            assert route == "message.create"
            assert params == {"channel_id": "chan1", "content": "hello"}
            assert headers["satori-platform"] == "qq"
            assert headers["satori-user-id"] == "10000"
            assert headers["authorization"] == "Bearer tok"
            assert end.identified == [{"op": 3, "body": {"token": "tok"}}]
        finally:
            await adapter.stop()
            await end.stop()

    asyncio.run(run())


def test_webhook_events_and_http_actions():
    async def run() -> None:
        end = FakeSatoriEnd()
        port = await end.start()
        adapter = create_adapter()
        webhook_port = _free_port()
        config = SatoriConfig.model_validate(
            {
                "connections": [
                    {
                        "type": "WebHook",
                        "api_url": f"http://127.0.0.1:{port}",
                        "host": "127.0.0.1",
                        "port": webhook_port,
                        "endpoint": "/satori",
                        "token": "app",
                        "register_webhook": False,
                    }
                ]
            }
        )
        await adapter.start(config)
        try:
            async with httpx.AsyncClient() as client:
                pushed = await client.post(
                    f"http://127.0.0.1:{webhook_port}/satori",
                    json=MESSAGE_EVENT,
                    headers={"Authorization": "Bearer app", "Satori-Opcode": "0"},
                )
                assert pushed.status_code == 204
            event = await asyncio.wait_for(adapter.receive(), timeout=5)
            assert str(event.message) == "hi @10000"  # type: ignore[attr-defined]

            await adapter.execute(GetBotProfileAction())
            assert end.calls[-1][0] == "login.get"
        finally:
            await adapter.stop()
            await end.stop()

    asyncio.run(run())


def _load_smoke_script(name: str):
    """Import a root-level smoke script by path, the way ``python <script>.py`` would."""
    spec = importlib.util.spec_from_file_location(name, _ROOT / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_script_replies_uploads_and_recalls(monkeypatch):
    """Drive test_v2_satori's handler end to end against the fake protocol end."""
    monkeypatch.setenv("HYPEROT_RECALL_DELAY", "0.05")
    script = _load_smoke_script("test_v2_satori")

    async def run() -> None:
        end = FakeSatoriEnd()
        port = await end.start()
        client = Client(
            create_adapter(),
            SatoriConfig.model_validate({"connections": [{"type": "WebSocket", "url": f"ws://127.0.0.1:{port}"}]}),
        )
        client.subscribe(MessageReceivedEvent, script.handler_msg)
        await client.start()
        try:
            await end.events.put(PING_EVENT)
            for _ in range(200):
                if any(route == "message.delete" for route, _params, _headers in end.calls):
                    break
                await asyncio.sleep(0.05)

            routes = [route for route, _params, _headers in end.calls]
            assert routes == [
                # Satori has no version API, so the script falls back to the login.
                "login.get",
                "message.create",
                "upload.create",
                "message.create",
                "message.delete",
            ]
            sent = [params for route, params, _headers in end.calls if route == "message.create"]
            assert sent[0] == {"channel_id": "chan1", "content": "pong"}
            assert sent[1] == {
                "channel_id": "chan1",
                "content": (
                    '<quote id="sent1"/>'
                    '<at id="20001"/>'
                    " Hello from HyperBotCore V2 bot"
                    '<img src="internal:qq/10000/_tmp/banner.png" title="HyperBotCore Banner"/>'
                ),
            }
            assert end.calls[-1][1] == {"channel_id": "chan1", "message_id": "sent1"}
        finally:
            await client.stop()
            await end.stop()

    asyncio.run(run())
