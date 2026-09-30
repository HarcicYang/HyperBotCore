from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from .formatting import format_value

ResultT = TypeVar("ResultT")


class Action(BaseModel, Generic[ResultT]):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    log_level: ClassVar[str] = "INFO"

    def log_summary(self) -> str:
        fields = [
            f"{name}={format_value(value)}"
            for name in type(self).model_fields
            if (value := getattr(self, name)) is not None
        ]
        if not fields:
            return type(self).__name__
        return f"{type(self).__name__} {' '.join(fields)}"
