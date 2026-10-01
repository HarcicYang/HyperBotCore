from hyperot_adapter_onebot.segments import OneBotSegmentCodec
from typing_extensions import override

from hyperot.v2 import Image, Mention, Message, Text
from hyperot.v2.messages import Segment


class CustomSegment(Segment):
    value: str

    @override
    def display_text(self) -> str:
        return f"<{self.value}>"


def test_segment_display_is_owned_by_segment():
    assert Message(Text(text="a"), Mention(user_id="1")).__str__() == "a@1"
    assert Message(CustomSegment(value="x")).__str__() == "<x>"


def test_image_alt_is_used_for_display_and_onebot_summary():
    image = Image(source="https://example.com/a.png", alt="项目截图")
    assert Message(image).__str__() == "项目截图"
    wire = OneBotSegmentCodec().encode_message(Message(image))
    assert wire[0]["data"]["summary"] == "项目截图"


def test_message_takes_segments_varargs_list_and_tuple():
    segments = [Text("a"), Text("b")]

    assert Message().segments == ()
    assert Message(*segments).segments == tuple(segments)
    assert Message(segments).segments == tuple(segments)
    assert Message(tuple(segments)).segments == tuple(segments)
    assert Message(segments=segments).segments == tuple(segments)


def test_message_rejects_mixing_positional_segments_with_the_keyword():
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


def test_segments_are_frozen_and_hashable():
    segment = Text("hi")

    with pytest.raises(dataclasses.FrozenInstanceError):
        segment.text = "other"
    assert hash(segment) == hash(Text("hi"))
    assert segment != Text("other")
    assert segment != "hi"


def test_decorated_and_annotated_subclasses_both_build_dataclasses():
    class Annotated(Segment):
        value: str

    @dataclasses.dataclass(frozen=True)
    class Decorated(Segment):
        value: str

    assert Annotated(value="a").value == "a"
    assert Decorated(value="a").value == "a"
    assert dataclasses.fields(Annotated)[0].name == "value"


def test_unknown_segment_round_trips_its_raw_payload():
    codec = OneBotSegmentCodec()
    payload = {"type": "mystery", "data": {"k": "v"}}

    message = codec.decode_message([payload])

    assert isinstance(message[0], UnknownSegment)
    assert message[0].wire_type == "mystery"
    assert message[0].data == {"k": "v"}
    assert codec.encode_message(message) == [payload]
    assert str(message) == "[unknown:mystery]"


import dataclasses

import pytest
from typing_extensions import override

from hyperot.v2 import (
    Face,
    ForwardNode,
    Quote,
    UnknownSegment,
)
from hyperot.v2.messages import Segment
