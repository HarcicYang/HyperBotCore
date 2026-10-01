from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from typing_extensions import override

from hyperot.v2.common import FileId, MessageId, UserId
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


WireSegmentUnion = Annotated[
    TextWire
    | MentionWire
    | QuoteWire
    | FaceWire
    | PokeWire
    | ImageWire
    | AudioWire
    | VideoWire
    | FileWire
    | NodeWire
    | ForwardWire
    | JsonWire
    | MarketFaceWire
    | RpsWire
    | DiceWire
    | GreyTipsWire,
    Field(discriminator="type"),
]
WIRE_SEGMENT_ADAPTER = TypeAdapter(WireSegmentUnion)


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
        return cls(user_id=UserId(str(payload.data.qq)))

    def to_wire(self) -> MentionWire:
        return MentionWire(data=MentionData(qq=str(self.user_id)))


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


class OneBotFile(File):
    file_hash: str = ""

    @classmethod
    def from_wire(cls, payload: FileWire) -> OneBotFile:
        return cls(
            source=payload.data.url or payload.data.file_id,
            name=payload.data.file_name or None,
            file_id=FileId(payload.data.file_id) if payload.data.file_id else None,
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
        return cls(message_id=MessageId(str(payload.data.id)))

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
            user_id=UserId(str(payload.data.user_id)),
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


def _to_wire(segment: Segment) -> WireSegmentUnion:
    if isinstance(segment, OneBotText):
        return segment.to_wire()
    if isinstance(segment, OneBotMention):
        return segment.to_wire()
    if isinstance(segment, OneBotImage):
        return segment.to_wire()
    if isinstance(segment, OneBotAudio):
        return segment.to_wire()
    if isinstance(segment, OneBotVideo):
        return segment.to_wire()
    if isinstance(segment, OneBotFile):
        return segment.to_wire()
    if isinstance(segment, OneBotQuote):
        return segment.to_wire()
    if isinstance(segment, OneBotForward):
        return segment.to_wire()
    if isinstance(segment, OneBotForwardNode):
        return segment.to_wire()
    if isinstance(segment, OneBotFace):
        return segment.to_wire()
    if isinstance(segment, OneBotPokeSegment):
        return segment.to_wire()
    if isinstance(segment, OneBotMarketFace):
        return segment.to_wire()
    if isinstance(segment, OneBotJson):
        return segment.to_wire()
    if isinstance(segment, OneBotRps):
        return segment.to_wire()
    if isinstance(segment, OneBotDice):
        return segment.to_wire()
    if isinstance(segment, OneBotGreyTips):
        return segment.to_wire()
    if isinstance(segment, Text):
        return OneBotText(text=segment.text).to_wire()
    if isinstance(segment, Mention):
        return OneBotMention(user_id=segment.user_id).to_wire()
    if isinstance(segment, MentionAll):
        return OneBotMention(user_id=UserId("all")).to_wire()
    if isinstance(segment, Image):
        return OneBotImage(source=segment.source, alt=segment.alt).to_wire()
    if isinstance(segment, Audio):
        return OneBotAudio(source=segment.source, title=segment.title, duration=segment.duration).to_wire()
    if isinstance(segment, Video):
        return OneBotVideo(
            source=segment.source,
            duration=segment.duration,
            thumbnail=segment.thumbnail,
        ).to_wire()
    if isinstance(segment, File):
        return OneBotFile(
            source=segment.source,
            name=segment.name,
            size=segment.size,
            file_id=segment.file_id,
        ).to_wire()
    if isinstance(segment, Quote):
        return OneBotQuote(message_id=segment.message_id, message=segment.message).to_wire()
    if isinstance(segment, Forward):
        return OneBotForward(forward_id=segment.forward_id).to_wire()
    if isinstance(segment, ForwardNode):
        return OneBotForwardNode(
            user_id=segment.user_id,
            display_name=segment.display_name,
            message=segment.message,
        ).to_wire()
    if isinstance(segment, Face):
        return OneBotFace(face_id=segment.face_id, is_large=segment.is_large).to_wire()
    if isinstance(segment, Markdown):
        return OneBotJson(payload=json.dumps({"content": segment.text}, ensure_ascii=False)).to_wire()
    raise TypeError(f"unsupported OneBot segment: {type(segment).__name__}")


def _from_wire(payload: WireSegmentUnion) -> Segment:
    match payload:
        case TextWire():
            return OneBotText.from_wire(payload)
        case MentionWire():
            return OneBotMention.from_wire(payload)
        case QuoteWire():
            return OneBotQuote.from_wire(payload)
        case FaceWire():
            return OneBotFace.from_wire(payload)
        case PokeWire():
            return OneBotPokeSegment.from_wire(payload)
        case ImageWire():
            return OneBotImage.from_wire(payload)
        case AudioWire():
            return OneBotAudio.from_wire(payload)
        case VideoWire():
            return OneBotVideo.from_wire(payload)
        case FileWire():
            return OneBotFile.from_wire(payload)
        case NodeWire():
            return OneBotForwardNode.from_wire(payload)
        case ForwardWire():
            return OneBotForward.from_wire(payload)
        case JsonWire():
            return OneBotJson.from_wire(payload)
        case MarketFaceWire():
            return OneBotMarketFace.from_wire(payload)
        case RpsWire():
            return OneBotRps.from_wire(payload)
        case DiceWire():
            return OneBotDice.from_wire(payload)
        case GreyTipsWire():
            return OneBotGreyTips.from_wire(payload)


class OneBotSegmentCodec:
    def decode_segments(self, payload: list[dict[str, Any]]) -> Message:
        segments: list[Segment] = []
        for item in payload:
            try:
                wire = WIRE_SEGMENT_ADAPTER.validate_python(item)
            except ValidationError:
                wire_type = str(item.get("type", "unknown")) if isinstance(item, dict) else "unknown"
                data = item.get("data", {}) if isinstance(item, dict) else {}
                segments.append(
                    UnknownSegment(
                        wire_type=wire_type,
                        data=data if isinstance(data, dict) else {},
                    )
                )
                continue
            segments.append(_from_wire(wire))
        return Message(*segments)

    def encode_segments(self, message: Message) -> list[dict[str, Any]]:
        return [
            {"type": segment.wire_type, "data": segment.data}
            if isinstance(segment, UnknownSegment)
            else _to_wire(segment).model_dump(mode="json")
            for segment in message
        ]

    def decode_message(self, payload: list[dict[str, Any]]) -> Message:
        if not isinstance(payload, list):
            raise TypeError("OneBot message must be an array")
        return self.decode_segments(payload)

    def encode_message(self, message: Message) -> list[dict[str, Any]]:
        return self.encode_segments(message)
