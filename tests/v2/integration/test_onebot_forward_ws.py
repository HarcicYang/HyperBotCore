import asyncio
import json

from hyperot_adapter_onebot import OneBotConfig, create_adapter
from websockets.asyncio.server import serve

from hyperot.v2.actions import GetVersionAction, SendMessageAction, SendResult
from hyperot.v2.common import GroupId, MessageId, SceneType
from hyperot.v2.messages import Message, Text


def test_forward_websocket_event_and_action_echo():
    async def run() -> None:
        async def handler(websocket) -> None:
            await websocket.send(
                json.dumps(
                    {
                        "post_type": "message",
                        "message_type": "group",
                        "sub_type": "normal",
                        "time": 1,
                        "self_id": 1,
                        "user_id": 2,
                        "group_id": 3,
                        "message_id": "m",
                        "message": [{"type": "text", "data": {"text": "hi"}}],
                    }
                )
            )
            async for raw in websocket:
                call = json.loads(raw)
                action = call["action"]
                if action == "get_version_info":
                    data = {"app_name": "fake", "app_version": "1.0", "protocol_version": "v11"}
                elif action == "send_msg":
                    data = {"message_id": "sent"}
                else:
                    data = {}
                await websocket.send(
                    json.dumps(
                        {
                            "status": "ok",
                            "retcode": 0,
                            "data": data,
                            "echo": call["echo"],
                        }
                    )
                )

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            adapter = create_adapter()
            await adapter.start(
                OneBotConfig.model_validate(
                    {"connections": [{"type": "ForwardWebSocket", "url": f"ws://127.0.0.1:{port}/"}]}
                )
            )
            try:
                event = await asyncio.wait_for(adapter.receive(), timeout=5)
                assert str(event.message) == "hi"  # type: ignore[attr-defined]
                version = await adapter.execute(GetVersionAction())
                assert version.app_name == "fake"
                sent = await adapter.execute(
                    SendMessageAction(
                        scene_type=SceneType.GROUP,
                        scene_id=GroupId("3"),
                        message=Message(Text(text="hello")),
                    )
                )
                assert isinstance(sent, SendResult)
                assert sent.message_id == MessageId("sent")
            finally:
                await adapter.stop()

    asyncio.run(run())
