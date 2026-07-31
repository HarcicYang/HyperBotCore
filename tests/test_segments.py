from hyperot.common import Message
from hyperot.segments import At, Image, Text, message_types


def test_text_to_json():
    assert Text("hello").to_json() == {"type": "text", "data": {"text": "hello"}}


def test_at_to_json():
    assert At(qq="123").to_json() == {"type": "at", "data": {"qq": "123"}}


def test_image_to_json():
    img = Image(file="http://example.com/x.png")
    data = img.to_json()
    assert data["type"] == "image"
    assert data["data"]["file"] == "http://example.com/x.png"


def test_segment_equality():
    assert At(qq="1") == At(qq="1")
    assert At(qq="1") != At(qq="2")


def test_message_build_and_str():
    m = Message(Text("hi"), At(qq="123"))
    assert str(m) == "hi@123"
    assert m.get_sync() == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "at", "data": {"qq": "123"}},
    ]


def test_message_sequence_ops():
    m = Message()
    m.add(Text("a"))
    assert len(m) == 1
    assert m[0] == Text("a")
    m[0] = Text("b")
    assert m[0] == Text("b")
    del m[0]
    assert len(m) == 0


def test_message_add():
    a = Message(Text("a"))
    b = Message(Text("b"))
    a += b
    assert len(a) == 2
    c = Message(Text("c")) + Message(Text("d"))
    assert len(c) == 2
    assert list(c) == [Text("c"), Text("d")]


def test_message_iter():
    assert [str(s) for s in Message(Text("a"), Text("b"))] == ["a", "b"]


def test_message_types_registry():
    assert "text" in message_types
    assert "at" in message_types
    assert "image" in message_types


def test_message_builder():
    m = Message.builder.text("hi").at("123").build()
    assert str(m) == "hi@123"
