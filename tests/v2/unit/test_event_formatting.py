import logging
from datetime import UTC, datetime

from hyperot_adapter_onebot.events import OneBotHeartbeatEvent, OneBotHeartbeatStatus

from hyperot.v2.common import FileInfo, SceneType, UserSnapshot
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


def test_message_event_is_compact_and_escapes_control_characters():
    event = MessageReceivedEvent(
        timestamp=datetime(2026, 9, 30, 12, 34, 56, tzinfo=UTC),
        scene_type=SceneType.GROUP,
        scene_id="100",
        user_id="200",
        message_id="m1",
        message=Message(
            Mention(user_id="123"),
            Text(text="line1\nline2\x1b[31m"),
            Image(source="https://example.com/a.png"),
        ),
        sender=UserSnapshot(user_id="200", display_name="display"),
        is_mentioned=True,
    )

    assert print_event(event) == ["[group] 100 @display: @123line1\\nline2\\x1b[31m[图片]"]


def test_other_events_use_short_summaries():
    events = [
        MessageRecalledEvent(
            scene_type=SceneType.GROUP,
            scene_id="100",
            user_id="200",
            message_id="m1",
            operator_id="300",
        ),
        MemberJoinedEvent(
            scene_type=SceneType.GROUP,
            scene_id="100",
            user_id="200",
            member_id="200",
            inviter_id="300",
        ),
        FileUploadedEvent(
            scene_type=SceneType.GROUP,
            scene_id="100",
            user_id="200",
            file=FileInfo(file_id="f1", name="archive.zip", size=42),
        ),
        BotOnlineEvent(reason="ready"),
    ]

    assert [print_event(event) for event in events] == [
        ["[group] 100 @300 recalled message m1"],
        ["[group] 100 @200 joined via @300"],
        ["[group] 100 @200 uploaded file archive.zip (42 bytes)"],
        ["[bot] online: ready"],
    ]


def test_heartbeat_events_are_silent():
    event = OneBotHeartbeatEvent(interval=1000, status=OneBotHeartbeatStatus(online=True, good=True))

    assert event.log_enabled is False
    assert print_event(event) == []
