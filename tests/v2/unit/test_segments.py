from hyperot_adapter_onebot.segments import OneBotSegmentCodec
from typing_extensions import override

from hyperot.v2 import Image, Mention, Message, Text, UserId
from hyperot.v2.messages import Segment


class CustomSegment(Segment):
    value: str

    @override
    def display_text(self) -> str:
        return f"<{self.value}>"


def test_segment_display_is_owned_by_segment():
    assert Message(Text(text="a"), Mention(user_id=UserId("1"))).__str__() == "a@1"
    assert Message(CustomSegment(value="x")).__str__() == "<x>"


def test_image_alt_is_used_for_display_and_onebot_summary():
    image = Image(source="https://example.com/a.png", alt="项目截图")
    assert Message(image).__str__() == "项目截图"
    wire = OneBotSegmentCodec().encode_message(Message(image))
    assert wire[0]["data"]["summary"] == "项目截图"
