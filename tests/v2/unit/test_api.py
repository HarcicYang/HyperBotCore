import asyncio
from typing import TypeVar

import pytest

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
from hyperot.v2.common import ActionTimeoutError, SceneType
from hyperot.v2.messages import Message, Text

ResultT = TypeVar("ResultT")


class FakeContext:
    running = True

    async def execute(self, action: Action[ResultT]) -> ResultT:
        if isinstance(action, SendMessageAction):
            return SendResult(message_id="m1")  # type: ignore[return-value]
        if isinstance(action, GetBotProfileAction):
            return BotProfile(user_id="1", display_name="bot")  # type: ignore[return-value]
        raise AssertionError(action)


def test_hierarchical_api_executes_actions():
    async def run() -> None:
        api = ClientAPI(FakeContext())

        sent = await api.group("100").send("hello")
        profile = await api.bot.profile()

        assert sent.message_id == "m1"
        assert profile.display_name == "bot"

    asyncio.run(run())


class FailingAdapter:
    async def execute(self, _action: Action[ResultT]) -> ResultT:
        raise ActionTimeoutError("OneBot action timed out")


def test_action_executor_preserves_action_failures():
    action = SendMessageAction(scene_type=SceneType.GROUP, scene_id="100", message=Message(Text(text="hello")))

    with pytest.raises(ActionTimeoutError, match="OneBot action timed out"):
        asyncio.run(ActionExecutor(FailingAdapter(), lambda: True).execute(action))  # type: ignore[arg-type]


def test_result_summaries_redact_sensitive_values():
    assert format_result(None) == "ok"
    assert format_result([1, 2, 3]) == "3 items"
    assert format_result(CookieInfo(cookies="secret")) == "cookie (length=6)"
    assert format_result(CsrfTokenInfo(token=123)) == "csrf token"
    assert format_result(FileUrl(url="https://example.com/a?token=secret#fragment")) == "url https://example.com/a"
    assert format_result(Message(Text(text="x" * 250))) == f"message: {'x' * 200}..."
