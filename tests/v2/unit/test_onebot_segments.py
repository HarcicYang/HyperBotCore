from typing import Any

import pytest
from hyperot_adapter_onebot.segments import OneBotSegmentCodec

from hyperot.v2 import (
    File,
    Image,
    Markdown,
    MentionAll,
    Message,
    Quote,
    Segment,
    Text,
    UnknownSegment,
)


class WeatherCard(Segment):
    city: str
    temperature: int

    def display_text(self) -> str:
        return f"[天气: {self.city} {self.temperature}°C]"


def decode_weather(item: Any) -> Segment:
    data = item["data"]
    return WeatherCard(city=data["city"], temperature=data["temperature"])


def encode_weather(segment: Segment) -> dict[str, Any]:
    return {"type": "weather", "data": {"city": segment.city, "temperature": segment.temperature}}


BUILTIN_WIRE: list[dict[str, Any]] = [
    {"type": "text", "data": {"text": "hi"}},
    {"type": "at", "data": {"qq": "123"}},
    {"type": "at", "data": {"qq": "all"}},
    {"type": "reply", "data": {"id": 7}},
    {"type": "face", "data": {"id": "4"}},
    {"type": "poke", "data": {"id": "1", "type": "2"}},
    {"type": "image", "data": {"file": "a.png", "summary": "图"}},
    {"type": "record", "data": {"file": "a.mp3"}},
    {"type": "video", "data": {"file": "a.mp4"}},
    {"type": "file", "data": {"file_name": "a.zip", "file_id": "f1"}},
    {"type": "forward", "data": {"id": "res"}},
    {"type": "json", "data": {"data": "{}"}},
    {"type": "mface", "data": {"face_id": "1", "tab_id": "2", "name": "n"}},
    {"type": "rps", "data": {}},
    {"type": "dice", "data": {}},
    {"type": "grey_tips", "data": {"text": "tip"}},
]


def test_builtin_wire_types_decode():
    message = OneBotSegmentCodec().decode_segments(BUILTIN_WIRE)

    assert [type(segment).__name__ for segment in message] == [
        "OneBotText",
        "OneBotMention",
        "MentionAll",
        "OneBotQuote",
        "OneBotFace",
        "OneBotPokeSegment",
        "OneBotImage",
        "OneBotAudio",
        "OneBotVideo",
        "OneBotFile",
        "OneBotForward",
        "OneBotJson",
        "OneBotMarketFace",
        "OneBotRps",
        "OneBotDice",
        "OneBotGreyTips",
    ]


def test_core_segments_encode_without_an_adapter_subclass():
    codec = OneBotSegmentCodec()

    assert codec.encode_segments(Message(Text("hi"))) == [{"type": "text", "data": {"text": "hi"}}]
    assert codec.encode_segments(Message(MentionAll())) == [{"type": "at", "data": {"qq": "all"}}]
    assert codec.encode_segments(Message(Quote("m1"))) == [{"type": "reply", "data": {"id": "m1"}}]
    assert codec.encode_segments(Message(Markdown("# hi"))) == [
        {"type": "json", "data": {"data": '{"content": "# hi"}'}}
    ]
    assert codec.encode_segments(Message(Image(source="u", alt="a")))[0]["data"]["summary"] == "a"
    assert codec.encode_segments(Message(File(source="u", file_id="f")))[0]["data"]["file_id"] == "f"


def test_unknown_wire_type_is_preserved_verbatim():
    codec = OneBotSegmentCodec()
    payload = {"type": "mystery", "data": {"x": 1, "y": ["z"]}}

    message = codec.decode_segments([payload, "not-a-dict"])

    assert isinstance(message[0], UnknownSegment)
    assert message[0].wire_type == "mystery"
    assert message[0].data == {"x": 1, "y": ["z"]}
    assert isinstance(message[1], UnknownSegment)
    assert message[1].wire_type == "unknown"
    assert codec.encode_segments(message)[:1] == [payload]


def test_malformed_known_payload_degrades_to_unknown_segment():
    codec = OneBotSegmentCodec()

    message = codec.decode_segments([{"type": "text", "data": {}}])

    assert isinstance(message[0], UnknownSegment)
    assert message[0].wire_type == "text"
    assert message[0].data == {}


def test_unsupported_segment_cannot_be_encoded():
    codec = OneBotSegmentCodec()

    with pytest.raises(TypeError):
        codec.encode_segments(Message(WeatherCard(city="上海", temperature=26)))


def test_registered_segment_survives_a_wire_round_trip():
    codec = OneBotSegmentCodec()
    codec.register_segment(WeatherCard, wire_type="weather", decode=decode_weather, encode=encode_weather)

    payload = {"type": "weather", "data": {"city": "上海", "temperature": 26}}
    message = codec.decode_segments([payload, {"type": "text", "data": {"text": "hi"}}])

    assert isinstance(message[0], WeatherCard)
    assert str(message) == "[天气: 上海 26°C]hi"
    assert codec.supports(WeatherCard)
    assert codec.encode_segments(message) == [payload, {"type": "text", "data": {"text": "hi"}}]
    assert codec.decode_message(codec.encode_segments(message)) == message


def test_registered_decoder_failure_degrades_to_unknown_segment():
    codec = OneBotSegmentCodec()
    codec.register_segment(
        WeatherCard,
        wire_type="weather",
        decode=lambda item: 1 / 0,
        encode=encode_weather,
    )

    message = codec.decode_segments([{"type": "weather", "data": {"city": "上海", "temperature": 26}}])

    assert isinstance(message[0], UnknownSegment)
    assert message[0].data == {"city": "上海", "temperature": 26}


def test_registered_segment_cannot_steal_builtin_wire_type():
    codec = OneBotSegmentCodec()

    with pytest.raises(ValueError):
        codec.register_segment(WeatherCard, wire_type="text", decode=decode_weather, encode=encode_weather)
