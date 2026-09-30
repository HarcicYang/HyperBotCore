from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from ..common import FileInfo, ReactionValue, UserSnapshot
from ..messages import Message, Segment
from .base import Event, SceneEvent

_BASE_FIELDS = {"event_id", "timestamp", "scene_type", "scene_id", "user_id"}


def format_fallback(event: Event) -> str:
    prefix = format_scene(event) if isinstance(event, SceneEvent) else f"[event] {type(event).__name__}"
    fields = [
        f"{name}={format_value(value)}"
        for name in type(event).model_fields
        if name not in _BASE_FIELDS and (value := getattr(event, name)) is not None
    ]
    details = " ".join(fields)
    actor = format_actor(event.user_id) if isinstance(event, SceneEvent) and event.user_id is not None else ""
    return " ".join(part for part in (prefix, actor, details) if part)


def format_scene(event: SceneEvent) -> str:
    return f"[{format_value(event.scene_type)}] {format_id(event.scene_id)}"


def format_actor(value: object | None, sender: UserSnapshot | None = None) -> str:
    if sender is not None:
        label = sender.display_name or sender.nick_name or str(sender.user_id)
    elif value is None:
        label = "unknown"
    else:
        label = str(value)
    return f"@{format_text(label)}"


def format_message(message: Message) -> str:
    rendered = format_text(str(message))
    return rendered if message.segments else "<empty>"


def format_with_reason(message: str, reason: str | None) -> str:
    return f"{message}: {format_text(reason)}" if reason else message


def format_id(value: object) -> str:
    return format_text(str(value))


def format_value(value: Any) -> str:
    if isinstance(value, Message):
        return format_message(value)
    if isinstance(value, Segment):
        return format_text(value.display_text())
    if isinstance(value, UserSnapshot):
        return format_text(value.display_name or value.nick_name or str(value.user_id))
    if isinstance(value, FileInfo):
        return format_text(value.name)
    if isinstance(value, ReactionValue):
        return f"{format_value(value.kind)}:{format_text(value.value)}"
    if isinstance(value, datetime):
        return value.astimezone().isoformat(sep=" ", timespec="seconds")
    if isinstance(value, Enum):
        return format_value(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return format_text(value)
    if isinstance(value, BaseModel):
        fields = [
            f"{name}={format_value(field_value)}"
            for name in type(value).model_fields
            if (field_value := getattr(value, name)) is not None
        ]
        return f"{type(value).__name__}({', '.join(fields)})"
    if isinstance(value, Mapping):
        return ", ".join(f"{format_value(key)}={format_value(item)}" for key, item in value.items())
    if isinstance(value, Sequence):
        return ", ".join(format_value(item) for item in value)
    return str(value)


def format_text(value: str | None) -> str:
    if not value:
        return "<empty>"

    output: list[str] = []
    for char in value:
        if char == "\n":
            output.append("\\n")
        elif char == "\r":
            output.append("\\r")
        elif char == "\t":
            output.append("\\t")
        elif char == "\\":
            output.append("\\\\")
        elif ord(char) < 32 or ord(char) == 127:
            output.append(f"\\x{ord(char):02x}")
        else:
            output.append(char)
    return "".join(output)
