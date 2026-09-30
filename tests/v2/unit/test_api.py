import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

import pytest
from typing_extensions import override

from hyperot.v2.actions import (
    Action,
    BotProfile,
    CookieInfo,
    CsrfTokenInfo,
    FileUrl,
    GetBotProfileAction,
    SendMessageAction,
    SendResult,
)
from hyperot.v2.actions.result import format_result
from hyperot.v2.api import ClientAPI
from hyperot.v2.client import ActionExecutor
from hyperot.v2.common import ActionTimeoutError, ClientNotRunningError, GroupId, MessageId, SceneId, SceneType
from hyperot.v2.hyperogger import Logger
from hyperot.v2.messages import Message, Text

ResultT = TypeVar("ResultT")


class FakeContext:
    running = True

    async def execute(self, action: Action[ResultT]) -> ResultT:
        if isinstance(action, SendMessageAction):
            return SendResult(message_id=MessageId("m1"))  # type: ignore[return-value]
        if isinstance(action, GetBotProfileAction):
            return BotProfile(user_id="1", display_name="bot")  # type: ignore[return-value]
        raise AssertionError(action)


def test_hierarchical_api():
    async def run() -> None:
        api = ClientAPI(FakeContext())
        sent = await api.group(GroupId("100")).send("hello")
        assert sent.message_id == "m1"
        profile = await api.bot.profile()
        assert profile.display_name == "bot"

    asyncio.run(run())


class QueryAdapter:
    async def execute(self, _action: Action[ResultT]) -> ResultT:
        return BotProfile(user_id="1", display_name="bot")  # type: ignore[return-value]


class SendAdapter:
    async def execute(self, _action: Action[ResultT]) -> ResultT:
        return SendResult(message_id=MessageId("m1"))  # type: ignore[return-value]


class FailingAdapter:
    async def execute(self, _action: Action[ResultT]) -> ResultT:
        raise ActionTimeoutError("OneBot action timed out")


class CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=-100)
        self.messages: list[tuple[str, str]] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        level = getattr(record, "hyperot_level", record.levelname)
        self.messages.append((level, record.getMessage()))


@contextmanager
def capture_api_logs(level: str = "INFO") -> Iterator[list[tuple[str, str]]]:
    handler = CaptureHandler()
    stdlib_logger = logging.getLogger("hyperot.v2.api")
    api_logger = Logger.fetch("hyperot.v2.api")
    api_logger.set_level(level)
    stdlib_logger.addHandler(handler)
    try:
        yield handler.messages
    finally:
        stdlib_logger.removeHandler(handler)
        api_logger.set_level("INFO")


def test_query_action_logs_at_trace():
    async def run() -> None:
        with capture_api_logs("TRACE") as messages:
            executor = ActionExecutor(QueryAdapter(), lambda: True)  # type: ignore[arg-type]
            await executor.execute(GetBotProfileAction())

        assert len(messages) == 1
        assert messages[0][0] == "TRACE"
        assert messages[0][1].startswith("[api] bot profile -> @1 bot (")
        assert "BotProfile(" not in messages[0][1]

    asyncio.run(run())


def test_write_action_logs_at_info():
    async def run() -> None:
        action = SendMessageAction(
            scene_type=SceneType.GROUP,
            scene_id=SceneId("100"),
            message=Message(Text(text="hello")),
        )
        with capture_api_logs() as messages:
            executor = ActionExecutor(SendAdapter(), lambda: True)  # type: ignore[arg-type]
            await executor.execute(action)

        assert len(messages) == 1
        assert messages[0][0] == "INFO"
        assert messages[0][1].startswith("[api] [group] 100 send: hello -> sent m1 (")

    asyncio.run(run())


def test_failed_action_logs_at_warning():
    async def run() -> None:
        action = SendMessageAction(
            scene_type=SceneType.GROUP,
            scene_id=SceneId("100"),
            message=Message(Text(text="hello")),
        )
        with capture_api_logs() as messages:
            executor = ActionExecutor(FailingAdapter(), lambda: True)  # type: ignore[arg-type]
            with pytest.raises(ActionTimeoutError):
                await executor.execute(action)

        assert len(messages) == 1
        assert messages[0][0] == "WARNING"
        assert messages[0][1].startswith(
            "[api] [group] 100 send: hello -> failed: ActionTimeoutError: OneBot action timed out ("
        )

    asyncio.run(run())


def test_not_running_action_logs_at_warning():
    async def run() -> None:
        with capture_api_logs() as messages:
            executor = ActionExecutor(SendAdapter(), lambda: False)  # type: ignore[arg-type]
            with pytest.raises(ClientNotRunningError):
                await executor.execute(GetBotProfileAction())

        assert len(messages) == 1
        assert messages[0][0] == "WARNING"
        assert messages[0][1].startswith(
            "[api] bot profile -> failed: ClientNotRunningError: cannot execute GetBotProfileAction"
        )

    asyncio.run(run())


def test_result_summaries_redact_sensitive_values():
    assert format_result(None) == "ok"
    assert format_result([1, 2, 3]) == "3 items"
    assert format_result(CookieInfo(cookies="secret")) == "cookie (length=6)"
    assert format_result(CsrfTokenInfo(token=123)) == "csrf token"
    assert format_result(FileUrl(url="https://example.com/a?token=secret#fragment")) == "url https://example.com/a"
    assert format_result(Message(Text(text="x" * 250))) == f"message: {'x' * 200}..."
