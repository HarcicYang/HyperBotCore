from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

from ..messages import Message, Segment


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


def format_value(value: Any) -> str:
    if isinstance(value, Message):
        return format_message(value)
    if isinstance(value, Segment):
        return format_text(value.display_text())
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


def format_message(message: Message) -> str:
    rendered = format_preview(str(message))
    return rendered if message.segments else "<empty>"


def format_preview(value: str, limit: int = 200) -> str:
    rendered = format_text(value)
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[:limit]}..."


def format_scene(scene_type: object, scene_id: object) -> str:
    return f"[{format_value(scene_type)}] {format_text(str(scene_id))}"


def format_actor(user_id: object) -> str:
    return f"@{format_text(str(user_id))}"


def format_source(source: str) -> str:
    if source.startswith(("http://", "https://")):
        return format_url(source)
    return format_text(source)


def format_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.scheme and not parts.netloc:
        return format_text(url.split("?", 1)[0].split("#", 1)[0])
    return format_text(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.1f}s"
