from hyperot.common import Message
from hyperot.segments import At, Image, Text


def test_builtin_segments_serialize_to_wire_json():
    assert Text("hello").to_json() == {"type": "text", "data": {"text": "hello"}}
    assert At(qq="123").to_json() == {"type": "at", "data": {"qq": "123"}}
    assert Image(file="http://example.com/x.png").to_json() == {
        "type": "image",
        "data": {"file": "http://example.com/x.png", "summary": "[图片]"},
    }


def test_message_stringifies_and_serializes_its_contents():
    message = Message(Text("hi"), At(qq="123"))

    assert str(message) == "hi@123"
    assert message.get_sync() == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "at", "data": {"qq": "123"}},
    ]


def test_message_container_operations_match_python_sequences():
    message = Message(Text("a"))
    message.add(Text("b"))
    message[0] = Text("c")

    assert list(message) == [Text("c"), Text("b")]
    assert len(message + Message(Text("d"))) == 3

    message += Message(Text("e"))
    assert str(message) == "cbe"


def test_message_addition_does_not_mutate_operands():
    left = Message(Text("a"))
    right = Message(Text("b"))

    combined = left + right

    assert str(combined) == "ab"
    assert str(left) == "a"
    assert str(right) == "b"
