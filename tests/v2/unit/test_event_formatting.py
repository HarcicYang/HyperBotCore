import logging
from datetime import UTC, datetime

from hyperot_adapter_onebot.events import OneBotHeartbeatEvent, OneBotHeartbeatStatus
from typing_extensions import override

from hyperot.v2.common import (
    FileId,
    FileInfo,
    MessageId,
    SceneId,
    SceneType,
    UserId,
    UserSnapshot,
)
from hyperot.v2.events import (
    BotOnlineEvent,
    Event,
    FileUploadedEvent,
    MemberJoinedEvent,
    MessageRecalledEvent,
    MessageReceivedEvent,
)
from hyperot.v2.messages import Image, Mention, Message, Text


class CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=-100)
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def print_event(event: Event) -> list[str]:
    handler = CaptureHandler()
    stdlib_logger = logging.getLogger("hyperot.v2.events")
    stdlib_logger.addHandler(handler)
    try:
        event.print_log()
    finally:
        stdlib_logger.removeHandler(handler)
    return handler.messages


def test_message_event_is_compact_and_readable():
    event = MessageReceivedEvent(
        timestamp=datetime(2026, 9, 30, 12, 34, 56, tzinfo=UTC),
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        message_id=MessageId("m1"),
        message=Message(
            Mention(user_id=UserId("123")),
            Text(text=" hello "),
            Image(source="https://example.com/a.png"),
        ),
        sender=UserSnapshot(
            user_id=UserId("200"),
            nick_name="nick",
            display_name="display",
        ),
        is_mentioned=True,
    )

    assert print_event(event) == ["[group] 100 @display: @123 hello [图片]"]


def test_extended_message_event_inherits_parent_formatting():
    class ExtendedMessageReceivedEvent(MessageReceivedEvent):
        self_id: UserId

    event = ExtendedMessageReceivedEvent(
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        message_id=MessageId("m1"),
        message=Message(Text(text="hello")),
        sender=UserSnapshot(user_id=UserId("200"), display_name="display"),
        self_id=UserId("999"),
    )

    assert print_event(event) == ["[group] 100 @display: hello"]


def test_other_events_use_short_summaries():
    recall = MessageRecalledEvent(
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        message_id=MessageId("m1"),
        operator_id=UserId("300"),
    )
    joined = MemberJoinedEvent(
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        member_id=UserId("200"),
        inviter_id=UserId("300"),
    )
    upload = FileUploadedEvent(
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        file=FileInfo(file_id=FileId("f1"), name="archive.zip", size=42),
    )

    assert print_event(recall) == ["[group] 100 @300 recalled message m1"]
    assert print_event(joined) == ["[group] 100 @200 joined via @300"]
    assert print_event(upload) == ["[group] 100 @200 uploaded file archive.zip (42 bytes)"]
    assert print_event(BotOnlineEvent(reason="ready")) == ["[bot] online: ready"]


def test_unknown_event_uses_compact_fallback():
    class CustomEvent(Event):
        source: str
        retry_count: int

    event = CustomEvent(source="onebot", retry_count=2)

    assert print_event(event) == ["[event] CustomEvent source=onebot retry_count=2"]


def test_message_text_escapes_control_characters():
    event = MessageReceivedEvent(
        scene_type=SceneType.GROUP,
        scene_id=SceneId("100"),
        user_id=UserId("200"),
        message_id=MessageId("m1"),
        message=Message(Text(text="line1\nline2\x1b[31m")),
    )

    assert print_event(event) == ["[group] 100 @200: line1\\nline2\\x1b[31m"]


def test_heartbeat_events_are_silent():
    event = OneBotHeartbeatEvent(
        interval=1000,
        status=OneBotHeartbeatStatus(online=True, good=True),
    )

    assert event.log_enabled is False
    assert print_event(event) == []
