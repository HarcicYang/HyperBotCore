import pytest
from hyperot_adapter_onebot.segments import OneBotSegmentCodec
from typing_extensions import override

from hyperot.v2 import Face, ForwardNode, Image, Mention, Message, Quote, Text, UnknownSegment
from hyperot.v2.messages import Segment


class CustomSegment(Segment):
    value: str

    @override
    def display_text(self) -> str:
        return f"<{self.value}>"


def test_segment_display_is_owned_by_segment():
    assert str(Message(Text(text="a"), Mention(user_id="1"))) == "a@1"
    assert str(Message(CustomSegment(value="x"))) == "<x>"

    image = Image(source="https://example.com/a.png", alt="项目截图")
    assert str(Message(image)) == "项目截图"
    assert OneBotSegmentCodec().encode_message(Message(image))[0]["data"]["summary"] == "项目截图"


def test_message_accepts_supported_construction_forms():
    segments = [Text("a"), Text("b")]

    assert Message().segments == ()
    assert Message(*segments).segments == tuple(segments)
    assert Message(segments).segments == tuple(segments)
    assert Message(tuple(segments)).segments == tuple(segments)
    assert Message(segments=segments).segments == tuple(segments)

    with pytest.raises(TypeError):
        Message(Text("a"), segments=[Text("b")])


def test_message_keeps_its_container_api():
    message = Message.text("hi").add(Text("!"))

    assert str(message) == "hi!"
    assert len(message) == 2
    assert list(message) == [message[0], message[1]]
    assert (message + Message.text("?")).segments == (*message.segments, Text("?"))
    assert Message.text("a") + Message.text("b") == Message(Text("a"), Text("b"))


def test_segments_accept_positional_and_keyword_fields():
    assert Text("hi") == Text(text="hi")
    assert Face("1") == Face(face_id="1", is_large=False)
    assert Image("u", alt="a") == Image(source="u", alt="a")
    assert Quote("m1") == Quote(message_id="m1")
    assert ForwardNode("1", "nick", Message(Text("x"))) == ForwardNode(
        user_id="1", display_name="nick", message=Message(Text("x"))
    )


def test_unknown_segment_round_trips_its_raw_payload():
    codec = OneBotSegmentCodec()
    payload = {"type": "mystery", "data": {"k": "v"}}

    message = codec.decode_message([payload])

    assert isinstance(message[0], UnknownSegment)
    assert message[0].wire_type == "mystery"
    assert message[0].data == {"k": "v"}
    assert codec.encode_message(message) == [payload]
    assert str(message) == "[unknown:mystery]"
