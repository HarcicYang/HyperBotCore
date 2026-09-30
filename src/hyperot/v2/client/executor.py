from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any, TypeVar

from ..actions import Action
from ..actions.formatting import format_duration
from ..actions.result import format_result
from ..adapter import Adapter
from ..common import ClientNotRunningError
from ..hyperogger import Logger

ResultT = TypeVar("ResultT")


class ActionExecutor:
    def __init__(self, adapter: Adapter[Any], running: Callable[[], bool]) -> None:
        self._adapter = adapter
        self._running = running
        self._logger = Logger.fetch("hyperot.v2.api")

    @property
    def running(self) -> bool:
        return self._running()

    async def execute(self, action: Action[ResultT]) -> ResultT:
        started = perf_counter()
        summary = action.log_summary()
        if not self.running:
            error = ClientNotRunningError(f"cannot execute {type(action).__name__}: client is not running")
            self._logger.warning(self._failure_log(summary, error, perf_counter() - started))
            raise error
        try:
            result = await self._adapter.execute(action)
        except Exception as exc:
            self._logger.warning(self._failure_log(summary, exc, perf_counter() - started))
            raise
        duration = format_duration(perf_counter() - started)
        self._logger.log(f"[api] {summary} -> {format_result(result)} ({duration})", action.log_level)
        return result

    @staticmethod
    def _failure_log(summary: str, error: BaseException, elapsed: float) -> str:
        duration = format_duration(elapsed)
        return f"[api] {summary} -> failed: {type(error).__name__}: {error} ({duration})"
