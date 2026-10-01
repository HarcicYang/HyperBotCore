from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from typing import Any, Literal, Protocol, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from typing_extensions import override

from hyperot.v2.hyperogger import Logger
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
    Video,
)

from .ids import decode_message_id, encode_message_id

logger = Logger.fetch("hyperot.v2.events")


class PlainData(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EmptyData(PlainData):
    pass


class TextData(PlainData):
    text: str


class MentionData(PlainData):
    user_id: int
    name: str | None = None


class FaceData(PlainData):
    face_id: str
    is_large: bool = False


class ReplyData(PlainData):
    message_seq: int
    sender_id: int | None = None
    sender_name: str | None = None
    time: int | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)


class ImageData(PlainData):
    resource_id: str = ""
    temp_url: str = ""
    width: int | None = None
    height: int | None = None
    summary: str | None = None
    sub_type: str = "normal"


class RecordData(PlainData):
    resource_id: str = ""
    temp_url: str = ""
    duration: int | None = None


class VideoData(PlainData):
    resource_id: str = ""
    temp_url: str = ""
    width: int | None = None
    height: int | None = None
    duration: int | None = None


class FileData(PlainData):
    file_id: str = ""
    file_name: str = ""
    file_size: int = 0
    file_hash: str | None = None


class ForwardData(PlainData):
    forward_id: str = ""
    title: str | None = None
    preview: list[str] | None = None
    summary: str | None = None


class MarketFaceData(PlainData):
    emoji_package_id: int | None = None
    emoji_id: str = ""
    key: str = ""
    summary: str | None = None
    url: str = ""


class LightAppData(PlainData):
    app_name: str = ""
    json_payload: str = ""


class XmlData(PlainData):
    service_id: int = 0
    xml_payload: str = ""


class MarkdownData(PlainData):
    content: str = ""


class OutImageData(PlainData):
    uri: str
    sub_type: str = "normal"
    summary: str | None = None


class OutMentionData(PlainData):
    user_id: int


class OutReplyData(PlainData):
    message_seq: int


class OutRecordData(PlainData):
    uri: str


class OutVideoData(PlainData):
    uri: str
    thumb_uri: str | None = None


class ForwardedMessageData(PlainData):
    user_id: int
    sender_name: str
    time: int | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)


class OutForwardData(PlainData):
    messages: list[ForwardedMessageData] = Field(default_factory=list)
    title: str | None = None
    preview: list[str] | None = None
    summary: str | None = None
    prompt: str | None = None


class OutLightAppData(PlainData):
    json_payload: str


class WireSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TextWire(WireSegment):
    type: Literal["text"] = "text"
    data: TextData


class MentionWire(WireSegment):
    type: Literal["mention"] = "mention"
    data: MentionData


class MentionAllWire(WireSegment):
    type: Literal["mention_all"] = "mention_all"
    data: EmptyData = Field(default_factory=EmptyData)


class FaceWire(WireSegment):
    type: Literal["face"] = "face"
    data: FaceData


class ReplyWire(WireSegment):
    type: Literal["reply"] = "reply"
    data: ReplyData


class ImageWire(WireSegment):
    type: Literal["image"] = "image"
    data: ImageData


class RecordWire(WireSegment):
    type: Literal["record"] = "record"
    data: RecordData


class VideoWire(WireSegment):
    type: Literal["video"] = "video"
    data: VideoData


class FileWire(WireSegment):
    type: Literal["file"] = "file"
    data: FileData


class ForwardWire(WireSegment):
    type: Literal["forward"] = "forward"
    data: ForwardData


class MarketFaceWire(WireSegment):
    type: Literal["market_face"] = "market_face"
    data: MarketFaceData


class LightAppWire(WireSegment):
    type: Literal["light_app"] = "light_app"
    data: LightAppData


class XmlWire(WireSegment):
    type: Literal["xml"] = "xml"
    data: XmlData


class MarkdownWire(WireSegment):
    type: Literal["markdown"] = "markdown"
    data: MarkdownData


class IncomingForwardedMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_seq: int | None = None
    sender_name: str = ""
    avatar_url: str = ""
    time: int = 0
    segments: list[dict[str, Any]] = Field(default_factory=list)


class OutImageWire(WireSegment):
    type: Literal["image"] = "image"
    data: OutImageData


class OutMentionWire(WireSegment):
    type: Literal["mention"] = "mention"
    data: OutMentionData


class OutReplyWire(WireSegment):
    type: Literal["reply"] = "reply"
    data: OutReplyData


class OutRecordWire(WireSegment):
    type: Literal["record"] = "record"
    data: OutRecordData


class OutVideoWire(WireSegment):
    type: Literal["video"] = "video"
    data: OutVideoData


class OutForwardWire(WireSegment):
    type: Literal["forward"] = "forward"
    data: OutForwardData


class OutLightAppWire(WireSegment):
    type: Literal["light_app"] = "light_app"
    data: OutLightAppData


class MilkyText(Text):
    @classmethod
    def from_wire(cls, payload: TextWire) -> MilkyText:
        return cls(text=payload.data.text)

    def to_wire(self) -> TextWire:
        return TextWire(data=TextData(text=self.text))


class MilkyMention(Mention):
    @classmethod
    def from_wire(cls, payload: MentionWire) -> MilkyMention:
        return cls(user_id=str(payload.data.user_id))

    def to_wire(self) -> OutMentionWire:
        return OutMentionWire(data=OutMentionData(user_id=int(self.user_id)))


def _decode_mention_all(payload: MentionAllWire) -> MentionAll:
    return MentionAll()


def _encode_mention_all(segment: Segment) -> MentionAllWire:
    return MentionAllWire(data=EmptyData())


class MilkyFace(Face):
    @classmethod
    def from_wire(cls, payload: FaceWire) -> MilkyFace:
        return cls(face_id=payload.data.face_id, is_large=payload.data.is_large)

    def to_wire(self) -> FaceWire:
        return FaceWire(data=FaceData(face_id=self.face_id, is_large=self.is_large))


class MilkyQuote(Quote):
    @classmethod
    def from_wire(cls, payload: ReplyWire, scene: str | None = None, peer_id: int | str | None = None) -> MilkyQuote:
        message = None
        if payload.data.segments:
            message = MilkySegmentCodec().decode_segments(payload.data.segments, scene=scene, peer_id=peer_id)
        return cls(message_id=_quote_id(scene, peer_id, payload.data.message_seq), message=message)

    def to_wire(self) -> OutReplyWire:
        return OutReplyWire(data=OutReplyData(message_seq=_message_seq(self.message_id)))


@dataclass(frozen=True)
class MilkyImage(Image):
    resource_id: str = ""
    sub_type: str = "normal"

    @classmethod
    def from_wire(cls, payload: ImageWire) -> MilkyImage:
        return cls(
            source=payload.data.temp_url or payload.data.resource_id,
            alt=payload.data.summary,
            width=payload.data.width,
            height=payload.data.height,
            resource_id=payload.data.resource_id,
            sub_type=payload.data.sub_type,
        )

    def to_wire(self) -> OutImageWire:
        return OutImageWire(
            data=OutImageData(
                uri=self.source or self.resource_id,
                sub_type=self.sub_type,
                summary=self.alt,
            )
        )


@dataclass(frozen=True)
class MilkyAudio(Audio):
    resource_id: str = ""

    @classmethod
    def from_wire(cls, payload: RecordWire) -> MilkyAudio:
        return cls(
            source=payload.data.temp_url or payload.data.resource_id,
            duration=float(payload.data.duration) if payload.data.duration is not None else None,
            resource_id=payload.data.resource_id,
        )

    def to_wire(self) -> OutRecordWire:
        return OutRecordWire(data=OutRecordData(uri=self.source or self.resource_id))


@dataclass(frozen=True)
class MilkyVideo(Video):
    resource_id: str = ""

    @classmethod
    def from_wire(cls, payload: VideoWire) -> MilkyVideo:
        return cls(
            source=payload.data.temp_url or payload.data.resource_id,
            duration=float(payload.data.duration) if payload.data.duration is not None else None,
            resource_id=payload.data.resource_id,
        )

    def to_wire(self) -> OutVideoWire:
        return OutVideoWire(data=OutVideoData(uri=self.source or self.resource_id, thumb_uri=self.thumbnail))


@dataclass(frozen=True)
class MilkyFile(File):
    file_hash: str | None = None

    @classmethod
    def from_wire(cls, payload: FileWire) -> MilkyFile:
        return cls(
            source=payload.data.file_id,
            name=payload.data.file_name or None,
            size=payload.data.file_size or None,
            file_id=payload.data.file_id or None,
            file_hash=payload.data.file_hash,
        )

    def to_wire(self) -> FileWire:
        raise TypeError("Milky cannot send a received file segment; upload it instead")


class MilkyForward(Forward):
    @classmethod
    def from_wire(cls, payload: ForwardWire) -> MilkyForward:
        return cls(forward_id=payload.data.forward_id)

    def to_wire(self) -> ForwardWire:
        raise TypeError("Milky cannot send a forwarded message by id; send its nodes instead")


@dataclass(frozen=True)
class MilkyForwardNode(ForwardNode):
    message_seq: str = ""
    time: int = 0

    @classmethod
    def from_wire(cls, payload: IncomingForwardedMessage, codec: MilkySegmentCodec | None = None) -> MilkyForwardNode:
        decoder = codec or MilkySegmentCodec()
        return cls(
            user_id="",
            display_name=payload.sender_name,
            message=decoder.decode_segments(payload.segments),
            message_seq=str(payload.message_seq) if payload.message_seq is not None else "",
            time=payload.time,
        )

    def to_wire(self) -> ForwardedMessageData:
        return ForwardedMessageData(
            user_id=int(self.user_id) if self.user_id else 0,
            sender_name=self.display_name,
            segments=MilkySegmentCodec().encode_segments(self.message),
        )

    @classmethod
    def from_node(cls, node: ForwardNode) -> MilkyForwardNode:
        if isinstance(node, MilkyForwardNode):
            return node
        return cls(user_id=node.user_id, display_name=node.display_name, message=node.message)


@dataclass(frozen=True)
class MilkyMarketFace(Segment):
    emoji_package_id: int | None = None
    emoji_id: str = ""
    key: str = ""
    summary: str | None = None
    url: str = ""

    @classmethod
    def from_wire(cls, payload: MarketFaceWire) -> MilkyMarketFace:
        return cls(
            emoji_package_id=payload.data.emoji_package_id,
            emoji_id=payload.data.emoji_id,
            key=payload.data.key,
            summary=payload.data.summary,
            url=payload.data.url,
        )

    def to_wire(self) -> FaceWire:
        raise TypeError("Milky cannot send a market face segment")

    @override
    def display_text(self) -> str:
        return f"[商城表情: {self.summary or self.emoji_id}]"


@dataclass(frozen=True)
class MilkyLightApp(Segment):
    app_name: str = ""
    json_payload: str = ""

    @classmethod
    def from_wire(cls, payload: LightAppWire) -> MilkyLightApp:
        return cls(app_name=payload.data.app_name, json_payload=payload.data.json_payload)

    def to_wire(self) -> OutLightAppWire:
        return OutLightAppWire(data=OutLightAppData(json_payload=self.json_payload))

    @override
    def display_text(self) -> str:
        return "[小程序]"


@dataclass(frozen=True)
class MilkyXml(Segment):
    service_id: int = 0
    xml_payload: str = ""

    @classmethod
    def from_wire(cls, payload: XmlWire) -> MilkyXml:
        return cls(service_id=payload.data.service_id, xml_payload=payload.data.xml_payload)

    def to_wire(self) -> LightAppWire:
        raise TypeError("Milky cannot send an XML segment; send a light_app segment instead")

    @override
    def display_text(self) -> str:
        return "[XML]"


class MilkyMarkdown(Markdown):
    @classmethod
    def from_wire(cls, payload: MarkdownWire) -> MilkyMarkdown:
        return cls(text=payload.data.content)

    def to_wire(self) -> TextWire:
        raise TypeError("Milky has no outgoing markdown segment")


class MilkyWireSegment(Protocol):
    """A segment class that knows how to cross the Milky wire boundary."""

    @classmethod
    def from_wire(cls, payload: Any) -> Segment: ...

    def to_wire(self) -> Any: ...


SceneAwareDecoder: TypeAlias = Callable[[Any, str | None, int | str | None], Segment]


def _wire_methods(segment_type: type[Segment]) -> MilkyWireSegment:
    return cast(MilkyWireSegment, segment_type)


def _wire_decoder(adapter: TypeAdapter[Any], from_wire: Callable[..., Any]) -> SegmentDecoder:
    def decode(item: Any) -> Segment:
        return from_wire(adapter.validate_python(item))

    return decode


def _scene_aware_decoder(adapter: TypeAdapter[Any], from_wire: Callable[..., Any]) -> SegmentDecoder:
    # A reply segment names the message it quotes, which is only addressable within
    # the scene the message was read from, so the caller passes that context in.
    def decode(item: Any, scene: str | None = None, peer_id: int | str | None = None) -> Segment:
        return from_wire(adapter.validate_python(item), scene, peer_id)

    return cast(SegmentDecoder, decode)


def _wire_encoder(to_wire: Callable[..., Any]) -> SegmentEncoder:
    def encode(segment: Segment) -> dict[str, Any]:
        return to_wire(segment).model_dump(mode="json")

    return encode


def _adapting_encoder(target: type[Any]) -> SegmentEncoder:
    # Core segments carry the fields their Milky counterpart needs, so the shared
    # names are copied over and the counterpart does the actual wire encoding.
    names = tuple(field.name for field in fields(target))
    encode_target = _wire_encoder(target.to_wire)

    def encode(segment: Segment) -> dict[str, Any]:
        values = {name: getattr(segment, name) for name in names if hasattr(segment, name)}
        return encode_target(target(**values))

    return encode


def _quote_id(scene: str | None, peer_id: int | str | None, message_seq: int | str) -> str:
    if scene and peer_id is not None:
        return encode_message_id(scene, peer_id, message_seq)
    return str(message_seq)


def _message_seq(message_id: object) -> int:
    text = str(message_id)
    try:
        _, _, sequence = decode_message_id(text)
    except ValueError:
        sequence = text
    return int(sequence)


# wire type, wire model, adapter-side segment class
_WIRE_SEGMENTS: tuple[tuple[str, type[Any], type[Segment]], ...] = (
    ("text", TextWire, MilkyText),
    ("mention", MentionWire, MilkyMention),
    ("mention_all", MentionAllWire, MentionAll),
    ("face", FaceWire, MilkyFace),
    ("reply", ReplyWire, MilkyQuote),
    ("image", ImageWire, MilkyImage),
    ("record", RecordWire, MilkyAudio),
    ("video", VideoWire, MilkyVideo),
    ("file", FileWire, MilkyFile),
    ("forward", ForwardWire, MilkyForward),
    ("market_face", MarketFaceWire, MilkyMarketFace),
    ("light_app", LightAppWire, MilkyLightApp),
    ("xml", XmlWire, MilkyXml),
    ("markdown", MarkdownWire, MilkyMarkdown),
)

# core segment, wire type, adapter-side counterpart used to encode it
_CORE_SEGMENTS: tuple[tuple[type[Segment], str, type[Segment]], ...] = (
    (Text, "text", MilkyText),
    (Mention, "mention", MilkyMention),
    (Image, "image", MilkyImage),
    (Audio, "record", MilkyAudio),
    (Video, "video", MilkyVideo),
    (File, "file", MilkyFile),
    (Quote, "reply", MilkyQuote),
    (Forward, "forward", MilkyForward),
    (Face, "face", MilkyFace),
    (Markdown, "markdown", MilkyMarkdown),
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
        if wire_type == "mention_all":
            decode = _wire_decoder(adapter, _decode_mention_all)
            encode = _wire_encoder(_encode_mention_all)
        elif wire_type == "reply":
            decode = _scene_aware_decoder(adapter, wire_segment.from_wire)
            encode = _wire_encoder(wire_segment.to_wire)
        else:
            decode = _wire_decoder(adapter, wire_segment.from_wire)
            encode = _wire_encoder(wire_segment.to_wire)
        registry.register(segment_type, wire_type=wire_type, decode=decode, encode=encode)
    for core_type, wire_type, adapter_type in _CORE_SEGMENTS:
        registry.register(
            core_type,
            wire_type=wire_type,
            decode=_register_decoder(registry, wire_type),
            encode=_adapting_encoder(adapter_type),
        )


class MilkySegmentCodec:
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

    def decode_segments(
        self,
        payload: list[dict[str, Any]],
        *,
        scene: str | None = None,
        peer_id: int | str | None = None,
    ) -> Message:
        return Message(*(self._decode_segment(item, scene, peer_id) for item in payload))

    def _decode_segment(self, item: Any, scene: str | None, peer_id: int | str | None) -> Segment:
        wire_type = str(item.get("type", "unknown")) if isinstance(item, dict) else "unknown"
        decode = self.registry.decoder(wire_type)
        if decode is None:
            return self._unsupported_segment(wire_type)
        try:
            if wire_type == "reply":
                return cast(SceneAwareDecoder, decode)(item, scene, peer_id)
            return decode(item)
        except Exception:  # noqa: BLE001
            # Registered decoders may raise anything. A segment that cannot be decoded
            # keeps the rest of the message readable instead of failing it.
            return self._unsupported_segment(wire_type)

    @staticmethod
    def _unsupported_segment(wire_type: str) -> Text:
        # Milky 1.2 asks application ends to fall back to text for unknown segment
        # types instead of dropping the segment or failing the whole message.
        logger.warning(f"忽略不支持的 Milky 消息段：{wire_type}")
        return Text(text=f"[不支持的消息段: {wire_type}]")

    def encode_segments(self, message: Message) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        nodes: list[MilkyForwardNode] = []
        for segment in message:
            if isinstance(segment, ForwardNode):
                nodes.append(MilkyForwardNode.from_node(segment))
                continue
            if nodes:
                payload.append(_encode_forward(nodes))
                nodes = []
            payload.append(self._encode_segment(segment))
        if nodes:
            payload.append(_encode_forward(nodes))
        return payload

    def _encode_segment(self, segment: Segment) -> dict[str, Any]:
        encode = self.registry.encoder_for(type(segment))
        if encode is None:
            raise TypeError(f"unsupported Milky segment: {type(segment).__name__}")
        return encode(segment)

    def supports(self, segment_type: type[Segment]) -> bool:
        return self.registry.supports(segment_type)

    def decode_message(
        self,
        payload: list[dict[str, Any]],
        *,
        scene: str | None = None,
        peer_id: int | str | None = None,
    ) -> Message:
        if not isinstance(payload, list):
            raise TypeError("Milky message must be an array")
        return self.decode_segments(payload, scene=scene, peer_id=peer_id)

    def encode_message(self, message: Message) -> list[dict[str, Any]]:
        return self.encode_segments(message)


def _encode_forward(nodes: list[MilkyForwardNode]) -> dict[str, Any]:
    wire = OutForwardWire(data=OutForwardData(messages=[node.to_wire() for node in nodes]))
    return wire.model_dump(mode="json", exclude_none=True)


def decode_forwarded_messages(
    payload: list[dict[str, Any]],
    codec: MilkySegmentCodec | None = None,
) -> list[MilkyForwardNode]:
    decoder = codec or MilkySegmentCodec()
    nodes: list[MilkyForwardNode] = []
    for item in payload:
        try:
            message = IncomingForwardedMessage.model_validate(item)
        except Exception:  # noqa: BLE001
            logger.warning("忽略无法解析的合并转发消息")
            continue
        nodes.append(MilkyForwardNode.from_wire(message, decoder))
    return nodes


__all__ = [
    "IncomingForwardedMessage",
    "MilkyAudio",
    "MilkyFace",
    "MilkyFile",
    "MilkyForward",
    "MilkyForwardNode",
    "MilkyImage",
    "MilkyLightApp",
    "MilkyMarkdown",
    "MilkyMarketFace",
    "MilkyQuote",
    "MilkySegmentCodec",
    "MilkyText",
    "MilkyVideo",
    "MilkyXml",
    "decode_forwarded_messages",
]
