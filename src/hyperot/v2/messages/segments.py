from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict, Field, JsonValue, SerializeAsAny, field_validator
from typing_extensions import override

from ..common import FileId, MessageId, UserId


class Segment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    def __init__(self, *args: object, **kwargs: object) -> None:
        if args:
            if kwargs:
                raise TypeError("positional and keyword arguments cannot be mixed")
            kwargs = dict(zip(self.model_fields, args, strict=False))
        super().__init__(**kwargs)

    def display_text(self) -> str:
        return f"[{type(self).__name__}]"


class UnknownSegment(Segment):
    wire_type: str
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @override
    def display_text(self) -> str:
        return f"[unknown:{self.wire_type}]"


class Text(Segment):
    text: str

    @override
    def display_text(self) -> str:
        return self.text


class Mention(Segment):
    user_id: UserId

    @override
    def display_text(self) -> str:
        return f"@{self.user_id}"


class MentionAll(Segment):
    @override
    def display_text(self) -> str:
        return "@全体成员"


class Image(Segment):
    source: str
    alt: str | None = None
    width: int | None = None
    height: int | None = None

    @override
    def display_text(self) -> str:
        return self.alt or "[图片]"


class Audio(Segment):
    source: str
    title: str | None = None
    duration: float | None = None

    @override
    def display_text(self) -> str:
        return "[音频]"


class Video(Segment):
    source: str
    duration: float | None = None
    thumbnail: str | None = None

    @override
    def display_text(self) -> str:
        return "[视频]"


class File(Segment):
    source: str
    name: str | None = None
    size: int | None = None
    file_id: FileId | None = None

    @override
    def display_text(self) -> str:
        return f"[文件: {self.name or self.source}]"


class Quote(Segment):
    message_id: MessageId
    message: Message | None = None

    @override
    def display_text(self) -> str:
        return "[引用]"


class Forward(Segment):
    forward_id: str

    @override
    def display_text(self) -> str:
        return "[转发]"


class ForwardNode(Segment):
    user_id: UserId
    display_name: str
    message: Message

    @override
    def display_text(self) -> str:
        return "[节点]"


class Markdown(Segment):
    text: str

    @override
    def display_text(self) -> str:
        return self.text


class Face(Segment):
    face_id: str
    is_large: bool = False

    @override
    def display_text(self) -> str:
        return f"[表情: {self.face_id}]"


class Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    segments: tuple[SerializeAsAny[Segment], ...] = ()

    def __init__(self, *args: Segment, **kwargs: object) -> None:
        if args and kwargs:
            raise TypeError("positional and keyword arguments cannot be mixed")
        if args:
            kwargs = {"segments": args}
        super().__init__(**kwargs)

    @field_validator("segments", mode="before")
    @classmethod
    def _coerce_segments(cls, value: object) -> object:
        if value is None:
            return ()
        return value

    @classmethod
    def text(cls, value: str) -> Message:
        return cls(Text(text=value))

    def add(self, segment: Segment) -> Message:
        return Message(*self.segments, segment)

    # Pydantic's BaseModel.__iter__ exposes fields. Message intentionally iterates segments.
    @override
    def __iter__(self) -> Iterator[Segment]:  # pyrefly: ignore[bad-override]
        return iter(self.segments)

    def __len__(self) -> int:
        return len(self.segments)

    def __getitem__(self, index: int) -> Segment:
        return self.segments[index]

    @override
    def __str__(self) -> str:
        return "".join(segment.display_text() for segment in self.segments)

    def __add__(self, other: Message) -> Message:
        return Message(*self.segments, *other.segments)


Quote.model_rebuild()
ForwardNode.model_rebuild()
