import asyncio
import logging
from datetime import UTC, datetime

from hyperot.v2 import Image, Mention, MessageReceivedEvent, SceneType, Text, UserId
from hyperot.v2.common import MessageId, SceneId
from hyperot.v2.events import Event, EventDispatcher
from hyperot.v2.messages import Message


class FakeClient:
    pass


def test_message_get_accepts_event_instances():
    event = MessageReceivedEvent(
        timestamp=datetime.now(UTC),
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        message_id=MessageId("m1"),
        message=Message(Text(text="hello")),
    )
    assert str(event.message) == "hello"


def test_dispatcher_runs_all_matching_handlers_parent_first():
    seen: list[str] = []

    async def base_handler(_event: Event, _client: FakeClient) -> None:
        seen.append("base")

    async def concrete_handler(_event: MessageReceivedEvent, _client: FakeClient) -> None:
        seen.append("concrete")

    async def run() -> None:
        dispatcher = EventDispatcher()
        dispatcher.subscribe(Event, base_handler)
        dispatcher.subscribe(MessageReceivedEvent, concrete_handler)
        event = MessageReceivedEvent(
            timestamp=datetime.now(UTC),
            scene_type=SceneType.USER,
            scene_id=SceneId("1"),
            user_id=UserId("1"),
            message_id=MessageId("m"),
            message=Message(),
        )
        await dispatcher.dispatch(event, FakeClient())  # type: ignore[arg-type]

    asyncio.run(run())
    assert seen == ["base", "concrete"]


class CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=-100)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_dispatcher_logs_every_event():
    async def run() -> None:
        handler = CaptureHandler()
        stdlib_logger = logging.getLogger("hyperot.v2.events")
        stdlib_logger.addHandler(handler)
        try:
            dispatcher = EventDispatcher()
            event = MessageReceivedEvent(
                timestamp=datetime.now(UTC),
                scene_type=SceneType.GROUP,
                scene_id=SceneId("1"),
                user_id=UserId("2"),
                message_id=MessageId("m"),
                message=Message(
                    Mention(user_id=UserId("1")),
                    Text(text=" hi "),
                    Image(source="https://example.com/a.png"),
                ),
            )
            await dispatcher.dispatch(event, FakeClient())  # type: ignore[arg-type]
        finally:
            stdlib_logger.removeHandler(handler)
        assert handler.messages == ["[group] 1 @2: @1 hi [图片]"]

    asyncio.run(run())
