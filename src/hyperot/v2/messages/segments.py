from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from typing_extensions import override


@dataclass(frozen=True)
class Segment:
    # Annotated subclasses become frozen dataclasses on their own, so a segment only
    # needs field annotations. Writing @dataclass(frozen=True) explicitly stays valid.
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "__annotations__" in cls.__dict__ and "__dataclass_fields__" not in cls.__dict__:
            dataclasses.dataclass(cls, frozen=True)
            # Immutability comes from the accessors installed below; dropping the
            # generated copies also keeps an explicit @dataclass(frozen=True) valid.
            for name in ("__setattr__", "__delattr__"):
                delattr(cls, name)

    def display_text(self) -> str:
        return f"[{type(self).__name__}]"


def _reject_assignment(self: Segment, name: str, value: object) -> None:
    raise dataclasses.FrozenInstanceError(f"cannot assign to field {name!r}")


def _reject_deletion(self: Segment, name: str) -> None:
    raise dataclasses.FrozenInstanceError(f"cannot delete field {name!r}")


# A frozen dataclass only guards exact instances, so subclasses would stay writable.
Segment.__setattr__ = _reject_assignment
Segment.__delattr__ = _reject_deletion


@dataclass(frozen=True)
class UnknownSegment(Segment):
    wire_type: str
    data: dict[str, Any] = field(default_factory=dict)

    @override
    def display_text(self) -> str:
        return f"[unknown:{self.wire_type}]"


@dataclass(frozen=True)
class Text(Segment):
    text: str

    @override
    def display_text(self) -> str:
        return self.text


@dataclass(frozen=True)
class Mention(Segment):
    user_id: str

    @override
    def display_text(self) -> str:
        return f"@{self.user_id}"


@dataclass(frozen=True)
class MentionAll(Segment):
    @override
    def display_text(self) -> str:
        return "@全体成员"


@dataclass(frozen=True)
class Image(Segment):
    source: str
    alt: str | None = None
    width: int | None = None
    height: int | None = None

    @override
    def display_text(self) -> str:
        return self.alt or "[图片]"


@dataclass(frozen=True)
class Audio(Segment):
    source: str
    title: str | None = None
    duration: float | None = None

    @override
    def display_text(self) -> str:
        return "[音频]"


@dataclass(frozen=True)
class Video(Segment):
    source: str
    duration: float | None = None
    thumbnail: str | None = None

    @override
    def display_text(self) -> str:
        return "[视频]"


@dataclass(frozen=True)
class File(Segment):
    source: str
    name: str | None = None
    size: int | None = None
    file_id: str | None = None

    @override
    def display_text(self) -> str:
        return f"[文件: {self.name or self.source}]"


@dataclass(frozen=True)
class Quote(Segment):
    message_id: str
    message: Message | None = None

    @override
    def display_text(self) -> str:
        return "[引用]"


@dataclass(frozen=True)
class Forward(Segment):
    forward_id: str

    @override
    def display_text(self) -> str:
        return "[转发]"


@dataclass(frozen=True)
class ForwardNode(Segment):
    user_id: str
    display_name: str
    message: Message

    @override
    def display_text(self) -> str:
        return "[节点]"


@dataclass(frozen=True)
class Markdown(Segment):
    text: str

    @override
    def display_text(self) -> str:
        return self.text


@dataclass(frozen=True)
class Face(Segment):
    face_id: str
    is_large: bool = False

    @override
    def display_text(self) -> str:
        return f"[表情: {self.face_id}]"


@dataclass(frozen=True, init=False)
class Message:
    segments: tuple[Segment, ...] = ()

    # Keeps the V1 construction surface: Message(), Message(*segments),
    # Message([segment, ...]) / Message((segment, ...)) and Message(segments=...).
    def __init__(
        self,
        *args: Segment | list[Segment] | tuple[Segment, ...],
        segments: Iterable[Segment] | None = None,
    ) -> None:
        if segments is not None:
            if args:
                raise TypeError("positional segments and the segments keyword cannot be mixed")
            collected = tuple(segments)
        elif len(args) == 1 and isinstance(args[0], list | tuple):
            collected = tuple(args[0])
        else:
            collected = tuple(args)
        object.__setattr__(self, "segments", collected)

    @classmethod
    def text(cls, value: str) -> Message:
        return cls(Text(text=value))

    def add(self, segment: Segment) -> Message:
        return Message(*self.segments, segment)

    def __iter__(self) -> Iterator[Segment]:
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
