import asyncio
import json
import socket

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response, WebSocket
from hyperot_adapter_milky import MilkyConfig, create_adapter
from starlette.responses import StreamingResponse

from hyperot.v2.actions import GetVersionAction, SendMessageAction
from hyperot.v2.common import SceneType
from hyperot.v2.messages import Message, Text

GROUP_MESSAGE = {
    "time": 1700000000,
    "self_id": 10000,
    "event_type": "message_receive",
    "data": {
        "message_scene": "group",
        "peer_id": 12345,
        "message_seq": 456,
        "sender_id": 10001,
        "time": 1700000001,
        "segments": [{"type": "text", "data": {"text": "hi"}}],
    },
}


class FakeMilkyEnd:
    """A protocol end that serves the Milky `/event` websocket and `/api` endpoints."""

    def __init__(self) -> None:
        self.app = FastAPI()
        self.events: asyncio.Queue[dict] = asyncio.Queue()
        self.calls: list[tuple[str, dict]] = []
        self.server: uvicorn.Server | None = None

        @self.app.websocket("/event")
        async def event(websocket: WebSocket) -> None:
            await websocket.accept()
            while True:
                payload = await self.events.get()
                await websocket.send_text(json.dumps(payload))

        @self.app.post("/api/{action}")
        async def api(action: str, request: Request) -> Response:
            params = await request.json()
            self.calls.append((action, params))
            data: dict = {"message_seq": 99, "time": 1700000002}
            if action == "get_impl_info":
                data = {"impl_name": "fake", "impl_version": "1.0", "milky_version": "1.3"}
            return Response(
                content=json.dumps({"status": "ok", "retcode": 0, "data": data}),
                media_type="application/json",
            )

        @self.app.get("/sse")
        async def sse() -> StreamingResponse:
            async def stream():
                while True:
                    payload = await self.events.get()
                    yield f"event: milky_event\ndata: {json.dumps(payload)}\n\n"

            return StreamingResponse(stream(), media_type="text/event-stream")

    async def start(self) -> int:
        config = uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.server.started:
                return int(self.server.servers[0].sockets[0].getsockname()[1])
            await asyncio.sleep(0.01)
        raise AssertionError("fake Milky protocol end failed to start")

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
        await asyncio.sleep(0)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_websocket_events_and_http_actions():
    async def run() -> None:
        end = FakeMilkyEnd()
        port = await end.start()
        adapter = create_adapter()
        config = MilkyConfig.model_validate({"connections": [{"type": "WebSocket", "url": f"ws://127.0.0.1:{port}"}]})
        await adapter.start(config)
        try:
            await end.events.put(GROUP_MESSAGE)
            event = await asyncio.wait_for(adapter.receive(), timeout=5)
            assert str(event.message) == "hi"  # type: ignore[attr-defined]
            assert event.scene_id == "12345"  # type: ignore[attr-defined]

            version = await adapter.execute(GetVersionAction())
            assert version.app_name == "fake"
            assert version.protocol_version == "1.3"

            sent = await adapter.execute(
                SendMessageAction(
                    scene_type=SceneType.GROUP,
                    scene_id="12345",
                    message=Message(Text(text="hello")),
                )
            )
            assert sent.message_id == "group:12345:99"
            expected = {"group_id": 12345, "message": [{"type": "text", "data": {"text": "hello"}}]}
            assert ("send_group_message", expected) in end.calls
        finally:
            await adapter.stop()
            await end.stop()

    asyncio.run(run())


def test_webhook_events_over_http():
    async def run() -> None:
        end = FakeMilkyEnd()
        api_port = await end.start()
        adapter = create_adapter()
        webhook_port = _free_port()
        config = MilkyConfig.model_validate(
            {
                "connections": [
                    {
                        "type": "WebHook",
                        "api_url": f"http://127.0.0.1:{api_port}",
                        "host": "127.0.0.1",
                        "port": webhook_port,
                        "endpoint": "/milky",
                    }
                ]
            }
        )
        await adapter.start(config)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"http://127.0.0.1:{webhook_port}/milky", json=GROUP_MESSAGE)
            assert response.status_code == 204
            event = await asyncio.wait_for(adapter.receive(), timeout=5)
            assert str(event.message) == "hi"  # type: ignore[attr-defined]
        finally:
            await adapter.stop()
            await end.stop()

    asyncio.run(run())


def test_webhook_rejects_a_missing_token():
    async def run() -> None:
        adapter = create_adapter()
        webhook_port = _free_port()
        config = MilkyConfig.model_validate(
            {
                "connections": [
                    {
                        "type": "WebHook",
                        "api_url": "http://127.0.0.1:1",
                        "access_token": "secret",
                        "host": "127.0.0.1",
                        "port": webhook_port,
                    }
                ]
            }
        )
        await adapter.start(config)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"http://127.0.0.1:{webhook_port}/", json=GROUP_MESSAGE)
                assert response.status_code == 401
                response = await client.post(
                    f"http://127.0.0.1:{webhook_port}/",
                    json=GROUP_MESSAGE,
                    headers={"Authorization": "Bearer secret"},
                )
            assert response.status_code == 204
            event = await asyncio.wait_for(adapter.receive(), timeout=5)
            assert str(event.message) == "hi"  # type: ignore[attr-defined]
        finally:
            await adapter.stop()

    asyncio.run(run())


def test_sse_events():
    async def run() -> None:
        end = FakeMilkyEnd()
        port = await end.start()
        adapter = create_adapter()
        config = MilkyConfig.model_validate(
            {
                "connections": [
                    {
                        "type": "SSE",
                        "url": f"http://127.0.0.1:{port}",
                        "event_path": "/sse",
                        "reconnect_delay": 0.1,
                    }
                ]
            }
        )
        await adapter.start(config)
        try:
            await end.events.put(GROUP_MESSAGE)
            event = await asyncio.wait_for(adapter.receive(), timeout=5)
            assert str(event.message) == "hi"  # type: ignore[attr-defined]
            assert event.scene_id == "12345"  # type: ignore[attr-defined]
        finally:
            await adapter.stop()
            await end.stop()

    asyncio.run(run())
