from typing import Any

from hyperot_adapter_satori.segments import (
    Node,
    SatoriSegmentCodec,
    dump,
    escape,
    parse,
    unescape,
)

from hyperot.v2.messages import (
    Audio,
    File,
    Forward,
    ForwardNode,
    Image,
    Mention,
    MentionAll,
    Message,
    Quote,
    Segment,
    Text,
    UnknownSegment,
    Video,
)


def _decode(content: str) -> Message:
    return SatoriSegmentCodec().decode_message(content)


def test_parse_keeps_text_and_elements():
    nodes = parse('hi <at id="1"/> there')
    assert nodes == ["hi ", Node(tag="at", attrs={"id": "1"}), " there"]


def test_parse_drops_comments():
    assert parse("a <!-- note --> b") == ["a ", " b"]


def test_parse_treats_stray_angle_brackets_as_text():
    # An unescaped "<" always starts a tag, so it has to be escaped to stay text.
    assert parse("1 &lt; 2 &amp; 3 &gt; 2") == ["1 < 2 & 3 > 2"]


def test_parse_reads_a_bare_angle_pair_as_an_empty_element():
    # The reference parser accepts a tag with no name; the trailing text is its content.
    assert parse("1 < 2 > 2") == ["1 ", Node(tag="", attrs={"2": True}, children=(" 2",))]


def test_parse_drops_unmatched_end_tags():
    assert parse("a </b> b") == ["a ", " b"]


def test_parse_keeps_unclosed_start_tags_as_elements():
    assert parse("<b>bold") == [Node(tag="b", attrs={}, children=("bold",))]


def test_parse_attribute_grammar():
    nodes = parse('<t a="1" b=\'2\' c d no-e/>')
    assert nodes == [Node(tag="t", attrs={"a": "1", "b": "2", "c": True, "d": True, "e": False})]


def test_parse_strips_the_no_prefix_before_camelizing():
    # Only a bare "no-" attribute becomes false; one with a value keeps its key.
    assert parse("<t no-end-time/>") == [Node(tag="t", attrs={"endTime": False})]
    assert parse('<t no-end-time="1"/>') == [Node(tag="t", attrs={"noEndTime": "1"})]


def test_parse_hyphenates_attribute_names_into_camel_case():
    assert parse('<audio kook:cover="u" end-time="7"/>') == [
        Node(tag="audio", attrs={"kook:cover": "u", "endTime": "7"})
    ]


def test_parse_trims_line_leading_and_trailing_space_runs():
    assert parse("<p>\n    spaced\n</p>") == [Node(tag="p", attrs={}, children=("spaced",))]
    assert parse("keep  inner\nnewline") == ["keep  inner\nnewline"]


def test_escape_and_unescape_round_trip():
    assert escape('a<b>&"c') == "a&lt;b&gt;&amp;\"c"
    assert escape('a"b', True) == 'a&quot;b'
    assert unescape("a&lt;b&gt;&amp;&quot;c&#39;&#x27;") == 'a<b>&"c\'\''
    assert unescape("&amp;#38;") == "&#38;"


def test_dump_round_trips_platform_native_elements():
    content = '<kook:card size="lg"><kook:countdown end-time="1"/></kook:card>'
    assert dump(parse(content)) == '<kook:card size="lg"><kook:countdown end-time="1"/></kook:card>'


def test_decode_resource_elements():
    content = (
        '<img src="i" title="pic" width="10" height="20"/>'
        '<audio src="a" duration="3"/>'
        '<video src="v" duration="2.5" poster="p"/>'
        '<file src="f" title="n.txt"/>'
    )
    message = _decode(content)
    assert [type(segment) for segment in message] == [Image, Audio, Video, File]
    image = message[0]
    assert (image.source, image.alt, image.width, image.height) == ("i", "pic", 10, 20)


def test_decode_mentions_and_emoji():
    message = _decode('<at id="1"/><at type="all"/><at name="bob"/><emoji id="7"/>')
    assert isinstance(message[0], Mention) and message[0].user_id == "1"
    assert isinstance(message[1], MentionAll)
    assert str(Message(message[2])) == "@bob"
    assert str(Message(message[3])) == "[表情: 7]"


def test_decode_quote_and_forward():
    message = _decode('<quote id="q">quoted</quote><message id="99" forward/>')
    quote = message[0]
    assert isinstance(quote, Quote)
    assert (quote.message_id, str(quote.message)) == ("q", "quoted")
    assert isinstance(message[1], Forward) and message[1].forward_id == "99"


def test_decode_packs_quoted_and_forwarded_ids_with_the_channel():
    codec = SatoriSegmentCodec()
    message = codec.decode_message('<quote id="m1"/><message id="m2" forward/>', channel_id="chan1")
    quote, forward = message[0], message[1]
    assert isinstance(quote, Quote) and quote.message_id == "chan1:m1"
    assert isinstance(forward, Forward) and forward.forward_id == "chan1:m2"
    # Element ids are the protocol's bare message ids again on the way out.
    assert codec.encode_message(message) == '<quote id="m1"/><message id="m2" forward/>'


def test_nested_quoted_ids_keep_the_channel():
    codec = SatoriSegmentCodec()
    message = codec.decode_message('<quote id="m1"><quote id="m0">old</quote></quote>', channel_id="chan1")
    outer = message[0]
    assert isinstance(outer, Quote) and outer.message_id == "chan1:m1"
    inner = outer.message[0]
    assert isinstance(inner, Quote) and inner.message_id == "chan1:m0"


def test_encode_quote_unpacks_the_channel_and_self_closes_when_empty():
    codec = SatoriSegmentCodec()
    packed = Message(Quote(message_id="chan1:m1"))
    assert codec.encode_message(packed) == '<quote id="m1"/>'
    with_body = Message(Quote(message_id="chan1:m1", message=Message(Text(text="old"))))
    assert codec.encode_message(with_body) == '<quote id="m1">old</quote>'


def test_decode_nested_message_becomes_a_forward_node():
    message = _decode('<message><author id="1" name="A"/>hi</message>')
    node = message[0]
    assert isinstance(node, ForwardNode)
    assert (node.user_id, node.display_name, str(node.message)) == ("1", "A", "hi")


def test_decode_modifiers_keep_their_content():
    assert str(_decode("<b>bold <i>both</i></b>")) == "bold both"
    assert str(_decode("a<br/>b")) == "a\nb"
    assert str(_decode('<a href="https://x">link</a>')) == "link (https://x)"


def test_decode_unknown_elements_keep_their_markup():
    codec = SatoriSegmentCodec()
    message = codec.decode_message('<kook:card size="lg"/>')
    segment = message[0]
    assert isinstance(segment, UnknownSegment)
    assert (segment.wire_type, segment.data) == ("kook:card", {"size": "lg"})
    assert codec.encode_message(message) == '<kook:card size="lg"/>'


def test_encode_standard_segments():
    codec = SatoriSegmentCodec()
    message = Message(
        Text(text="hi "),
        Mention(user_id="1"),
        MentionAll(),
        Image(source="i", alt="pic", width=10, height=20),
        Quote(message_id="q", message=Message(Text(text="old"))),
        ForwardNode(user_id="1", display_name="A", message=Message(Text(text="n"))),
    )
    assert codec.encode_message(message) == (
        "hi "
        '<at id="1"/>'
        '<at type="all"/>'
        '<img src="i" title="pic" width="10" height="20"/>'
        '<quote id="q">old</quote>'
        '<message><author id="1" name="A"/>n</message>'
    )


def test_encode_rejects_segments_without_an_element():
    codec = SatoriSegmentCodec()

    class Strange(Segment):
        value: int = 1

    try:
        codec.encode_message(Message(Strange()))
    except TypeError as exc:
        assert "unsupported Satori segment" in str(exc)
    else:  # pragma: no cover - the encode must fail
        raise AssertionError("expected TypeError")


def test_custom_segments_survive_a_round_trip():
    codec = SatoriSegmentCodec()

    class Weather(Segment):
        city: str

    def decode_weather(node: Any) -> Segment:
        return Weather(city=str(node.attr("city") or "no"))

    def encode_weather(segment: Segment) -> str:
        return f'<weather city="{escape(segment.city, True)}"/>'

    codec.register_segment(Weather, wire_type="weather", decode=decode_weather, encode=encode_weather)
    message = codec.decode_message('<weather city="sh"/>')
    assert isinstance(message[0], Weather) and message[0].city == "sh"
    assert codec.encode_message(message) == '<weather city="sh"/>'


def test_empty_content_decodes_to_an_empty_message():
    codec = SatoriSegmentCodec()
    assert len(codec.decode_message(None)) == 0
    assert len(codec.decode_message("")) == 0
