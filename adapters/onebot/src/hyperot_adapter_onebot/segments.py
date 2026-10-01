from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, fields
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from typing_extensions import override

from hyperot.v2.messages import (
    Audio,
    Face,
    File,
    Forward,
    ForwardNode,
    Image,
    Markdown,
    Mention,
    MentionAll,
    Message,
    Quote,
    Segment,
    SegmentDecoder,
    SegmentEncoder,
    SegmentRegistry,
    Text,
    UnknownSegment,
    Video,
)


class PlainData(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TextData(PlainData):
    text: str


class MentionData(PlainData):
    qq: str | int


class ReplyData(PlainData):
    id: str | int


class FaceData(PlainData):
    id: str | int


class PokeData(PlainData):
    id: str
    type: str


class ImageData(PlainData):
    file: str
    url: str = ""
    summary: str = "[图片]"
    is_emoji: bool = False


class RecordData(PlainData):
    file: str
    url: str = ""


class VideoData(PlainData):
    file: str
    url: str = ""


class FileData(PlainData):
    file_name: str = ""
    file_hash: str = ""
    file_id: str = ""
    url: str = ""


class NodeData(PlainData):
    user_id: str | int
    nickname: str
    content: list[dict[str, Any]] = Field(default_factory=list)


class ForwardData(PlainData):
    id: str = ""
    content: list[NodeData] = Field(default_factory=list)


class JsonData(PlainData):
    data: str


class MarketFaceData(PlainData):
    face_id: str = ""
    tab_id: str = ""
    name: str = ""


class EmptyData(PlainData):
    pass


class WireSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TextWire(WireSegment):
    type: Literal["text"] = "text"
    data: TextData


class MentionWire(WireSegment):
    type: Literal["at"] = "at"
    data: MentionData


class QuoteWire(WireSegment):
    type: Literal["reply"] = "reply"
    data: ReplyData


class FaceWire(WireSegment):
    type: Literal["face"] = "face"
    data: FaceData


class PokeWire(WireSegment):
    type: Literal["poke"] = "poke"
    data: PokeData


class ImageWire(WireSegment):
    type: Literal["image"] = "image"
    data: ImageData


class AudioWire(WireSegment):
    type: Literal["record"] = "record"
    data: RecordData


class VideoWire(WireSegment):
    type: Literal["video"] = "video"
    data: VideoData


class FileWire(WireSegment):
    type: Literal["file"] = "file"
    data: FileData


class NodeWire(WireSegment):
    type: Literal["node"] = "node"
    data: NodeData


class ForwardWire(WireSegment):
    type: Literal["forward"] = "forward"
    data: ForwardData


class JsonWire(WireSegment):
    type: Literal["json"] = "json"
    data: JsonData


class MarketFaceWire(WireSegment):
    type: Literal["mface"] = "mface"
    data: MarketFaceData


class RpsWire(WireSegment):
    type: Literal["rps"] = "rps"
    data: EmptyData


class DiceWire(WireSegment):
    type: Literal["dice"] = "dice"
    data: EmptyData


class GreyTipsWire(WireSegment):
    type: Literal["grey_tips"] = "grey_tips"
    data: TextData


class OneBotText(Text):
    @classmethod
    def from_wire(cls, payload: TextWire) -> OneBotText:
        return cls(text=payload.data.text)

    def to_wire(self) -> TextWire:
        return TextWire(data=TextData(text=self.text))


class OneBotMention(Mention):
    @classmethod
    def from_wire(cls, payload: MentionWire) -> Mention | MentionAll:
        if str(payload.data.qq) == "all":
            return MentionAll()
        return cls(user_id=str(payload.data.qq))

    def to_wire(self) -> MentionWire:
        return MentionWire(data=MentionData(qq=str(self.user_id)))


@dataclass(frozen=True)
class OneBotImage(Image):
    is_emoji: bool = False

    @classmethod
    def from_wire(cls, payload: ImageWire) -> OneBotImage:
        source = payload.data.url or payload.data.file
        return cls(source=source, alt=payload.data.summary, is_emoji=payload.data.is_emoji)

    def to_wire(self) -> ImageWire:
        return ImageWire(
            data=ImageData(
                file=self.source,
                url=self.source,
                summary=self.alt or "[图片]",
                is_emoji=self.is_emoji,
            )
        )


class OneBotAudio(Audio):
    @classmethod
    def from_wire(cls, payload: AudioWire) -> OneBotAudio:
        return cls(source=payload.data.url or payload.data.file)

    def to_wire(self) -> AudioWire:
        return AudioWire(data=RecordData(file=self.source, url=self.source))


class OneBotVideo(Video):
    @classmethod
    def from_wire(cls, payload: VideoWire) -> OneBotVideo:
        return cls(source=payload.data.url or payload.data.file)

    def to_wire(self) -> VideoWire:
        return VideoWire(data=VideoData(file=self.source, url=self.source))


@dataclass(frozen=True)
class OneBotFile(File):
    file_hash: str = ""

    @classmethod
    def from_wire(cls, payload: FileWire) -> OneBotFile:
        return cls(
            source=payload.data.url or payload.data.file_id,
            name=payload.data.file_name or None,
            file_id=str(payload.data.file_id) if payload.data.file_id else None,
            file_hash=payload.data.file_hash,
        )

    def to_wire(self) -> FileWire:
        return FileWire(
            data=FileData(
                file_name=self.name or "",
                file_id=str(self.file_id or self.source),
                url=self.source,
                file_hash=self.file_hash,
            )
        )


class OneBotQuote(Quote):
    @classmethod
    def from_wire(cls, payload: QuoteWire) -> OneBotQuote:
        return cls(message_id=str(payload.data.id))

    def to_wire(self) -> QuoteWire:
        return QuoteWire(data=ReplyData(id=str(self.message_id)))


class OneBotForward(Forward):
    @classmethod
    def from_wire(cls, payload: ForwardWire) -> OneBotForward:
        return cls(forward_id=payload.data.id)

    def to_wire(self) -> ForwardWire:
        return ForwardWire(data=ForwardData(id=self.forward_id))


class OneBotForwardNode(ForwardNode):
    @classmethod
    def from_wire(cls, payload: NodeWire) -> OneBotForwardNode:
        return cls(
            user_id=str(payload.data.user_id),
            display_name=payload.data.nickname,
            message=OneBotSegmentCodec().decode_segments(payload.data.content),
        )

    def to_wire(self) -> NodeWire:
        return NodeWire(
            data=NodeData(
                user_id=str(self.user_id),
                nickname=self.display_name,
                content=OneBotSegmentCodec().encode_segments(self.message),
            )
        )


class OneBotFace(Face):
    @classmethod
    def from_wire(cls, payload: FaceWire) -> OneBotFace:
        return cls(face_id=str(payload.data.id))

    def to_wire(self) -> FaceWire:
        return FaceWire(data=FaceData(id=self.face_id))


@dataclass(frozen=True)
class OneBotPokeSegment(Segment):
    poke_id: str
    poke_type: str

    @classmethod
    def from_wire(cls, payload: PokeWire) -> OneBotPokeSegment:
        return cls(poke_id=payload.data.id, poke_type=payload.data.type)

    def to_wire(self) -> PokeWire:
        return PokeWire(data=PokeData(id=self.poke_id, type=self.poke_type))

    @override
    def display_text(self) -> str:
        return "[戳一戳]"


@dataclass(frozen=True)
class OneBotMarketFace(Segment):
    face_id: str
    tab_id: str
    name: str = ""

    @classmethod
    def from_wire(cls, payload: MarketFaceWire) -> OneBotMarketFace:
        return cls(face_id=payload.data.face_id, tab_id=payload.data.tab_id, name=payload.data.name)

    def to_wire(self) -> MarketFaceWire:
        return MarketFaceWire(data=MarketFaceData(face_id=self.face_id, tab_id=self.tab_id, name=self.name))

    @override
    def display_text(self) -> str:
        return f"[商城表情: {self.name or self.face_id}]"


@dataclass(frozen=True)
class OneBotJson(Segment):
    payload: str

    @classmethod
    def from_wire(cls, payload: JsonWire) -> OneBotJson:
        return cls(payload=payload.data.data)

    def to_wire(self) -> JsonWire:
        return JsonWire(data=JsonData(data=self.payload))

    @override
    def display_text(self) -> str:
        return "[JSON]"


class OneBotRps(Segment):
    @classmethod
    def from_wire(cls, payload: RpsWire) -> OneBotRps:
        return cls()

    def to_wire(self) -> RpsWire:
        return RpsWire(data=EmptyData())

    @override
    def display_text(self) -> str:
        return "[猜拳]"


class OneBotDice(Segment):
    @classmethod
    def from_wire(cls, payload: DiceWire) -> OneBotDice:
        return cls()

    def to_wire(self) -> DiceWire:
        return DiceWire(data=EmptyData())

    @override
    def display_text(self) -> str:
        return "[骰子]"


@dataclass(frozen=True)
class OneBotGreyTips(Segment):
    text: str

    @classmethod
    def from_wire(cls, payload: GreyTipsWire) -> OneBotGreyTips:
        return cls(text=payload.data.text)

    def to_wire(self) -> GreyTipsWire:
        return GreyTipsWire(data=TextData(text=self.text))

    @override
    def display_text(self) -> str:
        return self.text


class OneBotWireSegment(Protocol):
    """A segment class that knows how to cross the OneBot wire boundary."""

    @classmethod
    def from_wire(cls, payload: Any) -> Segment: ...

    def to_wire(self) -> Any: ...


# The hook on Segment builds the dataclass at runtime, so only the class hierarchy is
# visible to a type checker; this cast is where the wire methods are pulled out.
def _wire_methods(segment_type: type[Segment]) -> OneBotWireSegment:
    return cast(OneBotWireSegment, segment_type)


def _wire_decoder(adapter: TypeAdapter[Any], from_wire: Callable[[Any], Segment]) -> SegmentDecoder:
    def decode(item: Any) -> Segment:
        return from_wire(adapter.validate_python(item))

    return decode


def _wire_encoder(to_wire: Callable[..., Any]) -> SegmentEncoder:
    def encode(segment: Segment) -> dict[str, Any]:
        return to_wire(segment).model_dump(mode="json")

    return encode


def _adapting_encoder(target: type[Any]) -> SegmentEncoder:
    # Core segments carry the fields their OneBot counterpart needs, so the shared
    # names are copied over and the counterpart does the actual wire encoding.
    names = tuple(field.name for field in fields(target))
    encode_target = _wire_encoder(target.to_wire)

    def encode(segment: Segment) -> dict[str, Any]:
        values = {name: getattr(segment, name) for name in names if hasattr(segment, name)}
        return encode_target(target(**values))

    return encode


def _encode_mention_all(segment: Segment) -> dict[str, Any]:
    return _wire_encoder(OneBotMention.to_wire)(OneBotMention(user_id="all"))


def _encode_markdown(segment: Segment) -> dict[str, Any]:
    if not isinstance(segment, Markdown):
        raise TypeError(f"expected Markdown, got {type(segment).__name__}")
    payload = json.dumps({"content": segment.text}, ensure_ascii=False)
    return _wire_encoder(OneBotJson.to_wire)(OneBotJson(payload=payload))


# wire type, wire model, adapter-side segment class
_WIRE_SEGMENTS: tuple[tuple[str, type[Any], type[Segment]], ...] = (
    ("text", TextWire, OneBotText),
    ("at", MentionWire, OneBotMention),
    ("reply", QuoteWire, OneBotQuote),
    ("face", FaceWire, OneBotFace),
    ("poke", PokeWire, OneBotPokeSegment),
    ("image", ImageWire, OneBotImage),
    ("record", AudioWire, OneBotAudio),
    ("video", VideoWire, OneBotVideo),
    ("file", FileWire, OneBotFile),
    ("node", NodeWire, OneBotForwardNode),
    ("forward", ForwardWire, OneBotForward),
    ("json", JsonWire, OneBotJson),
    ("mface", MarketFaceWire, OneBotMarketFace),
    ("rps", RpsWire, OneBotRps),
    ("dice", DiceWire, OneBotDice),
    ("grey_tips", GreyTipsWire, OneBotGreyTips),
)

# core segment, wire type, adapter-side counterpart used to encode it
_CORE_SEGMENTS: tuple[tuple[type[Segment], str, type[Segment]], ...] = (
    (Text, "text", OneBotText),
    (Mention, "at", OneBotMention),
    (Image, "image", OneBotImage),
    (Audio, "record", OneBotAudio),
    (Video, "video", OneBotVideo),
    (File, "file", OneBotFile),
    (Quote, "reply", OneBotQuote),
    (Forward, "forward", OneBotForward),
    (ForwardNode, "node", OneBotForwardNode),
    (Face, "face", OneBotFace),
)


def _register_decoder(registry: SegmentRegistry, wire_type: str) -> SegmentDecoder:
    decode = registry.decoder(wire_type)
    if decode is None:
        raise ValueError(f"no decoder registered for wire type {wire_type!r}")
    return decode


def _register_segments(registry: SegmentRegistry) -> None:
    for wire_type, wire_model, segment_type in _WIRE_SEGMENTS:
        adapter = TypeAdapter(wire_model)
        wire_segment = _wire_methods(segment_type)
        registry.register(
            segment_type,
            wire_type=wire_type,
            decode=_wire_decoder(adapter, wire_segment.from_wire),
            encode=_wire_encoder(wire_segment.to_wire),
        )
    for core_type, wire_type, adapter_type in _CORE_SEGMENTS:
        registry.register(
            core_type,
            wire_type=wire_type,
            decode=_register_decoder(registry, wire_type),
            encode=_adapting_encoder(adapter_type),
        )
    registry.register(
        MentionAll,
        wire_type="at",
        decode=_register_decoder(registry, "at"),
        encode=_encode_mention_all,
    )
    registry.register(
        Markdown,
        wire_type="json",
        decode=_register_decoder(registry, "json"),
        encode=_encode_markdown,
    )


class OneBotSegmentCodec:
    def __init__(self) -> None:
        self.registry = SegmentRegistry()
        _register_segments(self.registry)

    def register_segment(
        self,
        segment_type: type[Segment],
        *,
        wire_type: str,
        decode: SegmentDecoder,
        encode: SegmentEncoder,
        replace: bool = False,
    ) -> None:
        """Register a segment type with this codec so it survives a wire round trip."""
        self.registry.register(
            segment_type,
            wire_type=wire_type,
            decode=decode,
            encode=encode,
            replace=replace,
        )

    def decode_segments(self, payload: list[dict[str, Any]]) -> Message:
        return Message(*(self._decode_segment(item) for item in payload))

    def _decode_segment(self, item: Any) -> Segment:
        wire_type = str(item.get("type", "unknown")) if isinstance(item, dict) else "unknown"
        decode = self.registry.decoder(wire_type)
        if decode is None:
            return self._unknown_segment(item, wire_type)
        try:
            return decode(item)
        except Exception:  # noqa: BLE001
            # Registered decoders may raise anything. A segment that cannot be decoded
            # keeps its raw payload instead of failing the whole message.
            return self._unknown_segment(item, wire_type)

    @staticmethod
    def _unknown_segment(item: Any, wire_type: str) -> UnknownSegment:
        data = item.get("data", {}) if isinstance(item, dict) else {}
        return UnknownSegment(wire_type=wire_type, data=data if isinstance(data, dict) else {})

    def encode_segments(self, message: Message) -> list[dict[str, Any]]:
        return [self._encode_segment(segment) for segment in message]

    def _encode_segment(self, segment: Segment) -> dict[str, Any]:
        if isinstance(segment, UnknownSegment):
            return {"type": segment.wire_type, "data": segment.data}
        encode = self.registry.encoder_for(type(segment))
        if encode is None:
            raise TypeError(f"unsupported OneBot segment: {type(segment).__name__}")
        return encode(segment)

    def supports(self, segment_type: type[Segment]) -> bool:
        return self.registry.supports(segment_type)

    def decode_message(self, payload: list[dict[str, Any]]) -> Message:
        if not isinstance(payload, list):
            raise TypeError("OneBot message must be an array")
        return self.decode_segments(payload)

    def encode_message(self, message: Message) -> list[dict[str, Any]]:
        return self.encode_segments(message)
