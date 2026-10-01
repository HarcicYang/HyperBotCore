from typing import Any

import pytest
from hyperot_adapter_milky.segments import MilkySegmentCodec, decode_forwarded_messages

from hyperot.v2 import (
    ForwardNode,
    Image,
    Markdown,
    Mention,
    MentionAll,
    Message,
    Quote,
    Segment,
    Text,
)


class WeatherCard(Segment):
    city: str
    temperature: int

    def display_text(self) -> str:
        return f"[天气: {self.city} {self.temperature}C]"


def decode_weather(item: Any) -> Segment:
    data = item["data"]
    return WeatherCard(city=data["city"], temperature=data["temperature"])


def encode_weather(segment: Segment) -> dict[str, Any]:
    return {"type": "weather", "data": {"city": segment.city, "temperature": segment.temperature}}


BUILTIN_WIRE: list[dict[str, Any]] = [
    {"type": "text", "data": {"text": "hi"}},
    {"type": "mention", "data": {"user_id": 10001, "name": "某人"}},
    {"type": "mention_all", "data": {}},
    {"type": "face", "data": {"face_id": "4", "is_large": True}},
    {
        "type": "reply",
        "data": {
            "message_seq": 42,
            "sender_id": 7,
            "time": 1,
            "segments": [{"type": "text", "data": {"text": "orig"}}],
        },
    },
    {
        "type": "image",
        "data": {
            "resource_id": "r1",
            "temp_url": "http://x/a.png",
            "width": 1,
            "height": 2,
            "summary": "图",
            "sub_type": "sticker",
        },
    },
    {"type": "record", "data": {"resource_id": "r2", "temp_url": "http://x/a.mp3", "duration": 3}},
    {"type": "video", "data": {"resource_id": "r3", "temp_url": "http://x/a.mp4"}},
    {"type": "file", "data": {"file_id": "f1", "file_name": "a.zip", "file_size": 10, "file_hash": "h"}},
    {"type": "forward", "data": {"forward_id": "fw1", "title": "t"}},
    {"type": "market_face", "data": {"emoji_package_id": 2, "emoji_id": "e1", "key": "k", "summary": "s", "url": "u"}},
    {"type": "light_app", "data": {"app_name": "app", "json_payload": "{}"}},
    {"type": "xml", "data": {"service_id": 1, "xml_payload": "<x/>"}},
    {"type": "markdown", "data": {"content": "# hi"}},
]


def test_builtin_wire_types_decode():
    message = MilkySegmentCodec().decode_message(BUILTIN_WIRE, scene="group", peer_id=123)

    assert [type(segment).__name__ for segment in message] == [
        "MilkyText",
        "MilkyMention",
        "MentionAll",
        "MilkyFace",
        "MilkyQuote",
        "MilkyImage",
        "MilkyAudio",
        "MilkyVideo",
        "MilkyFile",
        "MilkyForward",
        "MilkyMarketFace",
        "MilkyLightApp",
        "MilkyXml",
        "MilkyMarkdown",
    ]


def test_incoming_segments_carry_protocol_details():
    codec = MilkySegmentCodec()

    image = codec._decode_segment(BUILTIN_WIRE[5], None, None)
    assert image.source == "http://x/a.png"  # type: ignore[attr-defined]
    assert image.resource_id == "r1"  # type: ignore[attr-defined]
    assert image.sub_type == "sticker"  # type: ignore[attr-defined]
    assert image.display_text() == "图"

    audio = codec._decode_segment(BUILTIN_WIRE[6], None, None)
    assert audio.duration == 3.0  # type: ignore[attr-defined]

    file_segment = codec._decode_segment(BUILTIN_WIRE[8], None, None)
    assert file_segment.file_hash == "h"  # type: ignore[attr-defined]

    market_face = codec._decode_segment(BUILTIN_WIRE[10], None, None)
    assert market_face.display_text() == "[商城表情: s]"


def test_reply_segment_uses_the_scene_it_was_read_from():
    codec = MilkySegmentCodec()

    quote = codec._decode_segment(BUILTIN_WIRE[4], "group", 123)
    assert quote.message_id == "group:123:42"  # type: ignore[attr-defined]
    assert str(quote.message) == "orig"  # type: ignore[attr-defined,call-arg]

    bare = codec._decode_segment(BUILTIN_WIRE[4], None, None)
    assert bare.message_id == "42"  # type: ignore[attr-defined]


def test_core_segments_encode_to_outgoing_wire():
    codec = MilkySegmentCodec()

    assert codec.encode_segments(Message(Text("hi"))) == [{"type": "text", "data": {"text": "hi"}}]
    assert codec.encode_segments(Message(Mention(user_id="1"))) == [{"type": "mention", "data": {"user_id": 1}}]
    assert codec.encode_segments(Message(MentionAll())) == [{"type": "mention_all", "data": {}}]
    assert codec.encode_segments(Message(Quote(message_id="group:123:42"))) == [
        {"type": "reply", "data": {"message_seq": 42}}
    ]
    assert codec.encode_segments(Message(Image(source="u", alt="a")))[0]["data"]["uri"] == "u"


def test_forward_nodes_collapse_into_one_forward_segment():
    codec = MilkySegmentCodec()
    message = Message(
        ForwardNode(user_id="1", display_name="a", message=Message(Text(text="a"))),
        ForwardNode(user_id="2", display_name="b", message=Message(Text(text="b"))),
    )

    payload = codec.encode_segments(message)

    assert payload == [
        {
            "type": "forward",
            "data": {
                "messages": [
                    {"user_id": 1, "sender_name": "a", "segments": [{"type": "text", "data": {"text": "a"}}]},
                    {"user_id": 2, "sender_name": "b", "segments": [{"type": "text", "data": {"text": "b"}}]},
                ]
            },
        }
    ]


def test_unknown_segment_falls_back_to_text():
    codec = MilkySegmentCodec()

    message = codec.decode_segments([{"type": "mystery", "data": {"x": 1}}, "not-a-dict"])

    assert str(message) == "[不支持的消息段: mystery][不支持的消息段: unknown]"


def test_malformed_known_payload_falls_back_to_text():
    codec = MilkySegmentCodec()

    message = codec.decode_segments([{"type": "text", "data": {}}])

    assert isinstance(message[0], Text)
    assert str(message) == "[不支持的消息段: text]"


def test_unsupported_segment_cannot_be_encoded():
    codec = MilkySegmentCodec()

    with pytest.raises(TypeError):
        codec.encode_segments(Message(WeatherCard(city="上海", temperature=26)))


def test_received_only_segments_cannot_be_sent_back():
    codec = MilkySegmentCodec()
    message = codec.decode_message(BUILTIN_WIRE, scene="group", peer_id=123)

    with pytest.raises(TypeError):
        codec.encode_segments(Message(Markdown(text="# hi")))

    with pytest.raises(TypeError):
        codec.encode_segments(Message(message[8]))


def test_registered_segment_survives_a_wire_round_trip():
    codec = MilkySegmentCodec()
    codec.register_segment(WeatherCard, wire_type="weather", decode=decode_weather, encode=encode_weather)

    payload = {"type": "weather", "data": {"city": "上海", "temperature": 26}}
    message = codec.decode_segments([payload, {"type": "text", "data": {"text": "hi"}}])

    assert isinstance(message[0], WeatherCard)
    assert str(message) == "[天气: 上海 26C]hi"
    assert codec.supports(WeatherCard)
    assert codec.encode_segments(message) == [payload, {"type": "text", "data": {"text": "hi"}}]


def test_forwarded_messages_decode_into_nodes():
    nodes = decode_forwarded_messages(
        [
            {
                "message_seq": 5,
                "sender_name": "a",
                "avatar_url": "http://x/a.png",
                "time": 7,
                "segments": [{"type": "text", "data": {"text": "hi"}}],
            },
            {"sender_name": "b", "segments": "not-a-list"},
        ]
    )

    assert len(nodes) == 1
    assert nodes[0].message_seq == "5"
    assert nodes[0].time == 7
    assert str(nodes[0].message) == "hi"
