from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..common import EventId, SceneId, SceneType, UserId
from ..hyperogger import Logger

logger = Logger.fetch("hyperot.v2.events")


def utc_now() -> datetime:
    return datetime.now(UTC)


class Event(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    log_enabled: ClassVar[bool] = True
    event_id: EventId = Field(default_factory=lambda: EventId(uuid4().hex))
    timestamp: datetime = Field(default_factory=utc_now)

    def print_log(self) -> None:
        if not self.log_enabled:
            return
        from .formatting import format_fallback

        self._emit_log(format_fallback(self))

    def _emit_log(self, message: str | None) -> None:
        if self.log_enabled and message:
            logger.info(message)


class SceneEvent(Event):
    scene_type: SceneType
    scene_id: SceneId
    user_id: UserId | None = None
