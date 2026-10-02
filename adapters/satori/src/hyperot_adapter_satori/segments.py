"""Message elements.

Satori encodes message content as a string of XHTML-like message elements instead of a
structured segment array, so this module holds both halves: a parser and serializer for
that markup, and the codec that maps elements onto V2 segments.

The markup rules follow the protocol specification (``protocol/message.md`` and
``protocol/elements.md``) and the reference implementation the official SDK depends on,
``@cordisjs/element``: the same tag grammar, the same attribute grammar, the same
escaping rules, and the same treatment of comments and unpaired tags.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import cast

from pydantic import JsonValue

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
    UnknownSegment,
    Video,
)

from .ids import decode_message_id, encode_message_id

logger = Logger.fetch("hyperot.v2.events")

# Satori message ids only mean something together with their channel: every
# message.get/delete/update and reaction call takes both. The adapter therefore hands
# ids out packed as "channel:message", and the codec needs the channel of the message
# being decoded to do the same for the ids nested in its content.
_CURRENT_CHANNEL: ContextVar[str | None] = ContextVar("satori_message_channel", default=None)

# Same shape as the tag pattern of the reference element parser: an HTML comment, or a
# start, end or self-closing tag whose name holds no whitespace, slash or bang.
_TAG_PATTERN = re.compile(
    r"(?P<comment><!--[\s\S]*?-->)"
    r"|(?P<tag><(?P<close>/?)(?P<name>[^!\s>/]*)(?P<extra>[^>]*?)\s*(?P<empty>/?)>)"
)
_ATTR_PATTERN = re.compile(r"(?P<key>[^\s=]+)(?:=\"(?P<dquoted>[^\"]*)\"|='(?P<squoted>[^']*)')?")
# Text keeps its indentation, but whitespace runs that cross a line boundary at either
# end are formatting only and get dropped.
_LEADING_SPACE = re.compile(r"^\s*\n\s*")
_TRAILING_SPACE = re.compile(r"\s*\n\s*$")

_DECIMAL_ESCAPE = re.compile(r"&#(\d+);")
_HEX_ESCAPE = re.compile(r"&#x([0-9a-f]+);", re.IGNORECASE)
_AMPERSAND_ESCAPE = re.compile(r"&(amp|#38|#x26);")

_CAMEL_BOUNDARY = re.compile(r"[-_]([a-zA-Z0-9])")
_HYPHEN_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")

#: Channel type of a private channel, per the ChannelType enum of the specification.
DIRECT_CHANNEL = 1

# Standard elements whose only job is to wrap or annotate their content, so decoding
# them keeps the content and drops the wrapper.
_PASSTHROUGH_TAGS = frozenset(
    {
        "p",
        "b",
        "strong",
        "i",
        "em",
        "u",
        "ins",
        "s",
        "del",
        "spl",
        "code",
        "sup",
        "sub",
        "author",
        "button",
        "i18n",
    }
)


def escape(text: str, inline: bool = False) -> str:
    result = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return result.replace('"', "&quot;") if inline else result


def unescape(text: str) -> str:
    result = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    result = _DECIMAL_ESCAPE.sub(_decimal_char, result)
    result = _HEX_ESCAPE.sub(_hex_char, result)
    return _AMPERSAND_ESCAPE.sub("&", result)


def _decimal_char(match: re.Match[str]) -> str:
    code = match.group(1)
    return match.group(0) if code == "38" else chr(int(code))


def _hex_char(match: re.Match[str]) -> str:
    code = match.group(1)
    return match.group(0) if code.lower() == "26" else chr(int(code, 16))


def _camelize(key: str) -> str:
    return _CAMEL_BOUNDARY.sub(lambda match: match.group(1).upper(), key)


def _hyphenate(key: str) -> str:
    return _HYPHEN_BOUNDARY.sub(r"\1-\2", key).lower()


def _text(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value)
    return text or None


def _integer(value: object) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _number(value: object) -> float | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class Node:
    """One parsed message element."""

    tag: str
    attrs: dict[str, JsonValue] = field(default_factory=dict)
    children: tuple[Node | str, ...] = ()

    def attr(self, name: str) -> JsonValue:
        return self.attrs.get(name)


_OPEN, _CLOSE, _EMPTY = 0, 1, 2


@dataclass
class _Token:
    name: str
    position: int
    extra: str
    children: list[str | _Token] = field(default_factory=list)


def _parse_attrs(extra: str) -> dict[str, JsonValue]:
    attrs: dict[str, JsonValue] = {}
    for match in _ATTR_PATTERN.finditer(extra):
        key = match.group("key")
        value = match.group("dquoted")
        if value is None:
            value = match.group("squoted")
        if value is not None:
            attrs[_camelize(key)] = unescape(value)
        elif key.startswith("no-"):
            # The reference parser strips the "no-" prefix before camelizing the key.
            attrs[_camelize(key[3:])] = False
        else:
            attrs[_camelize(key)] = True
    return attrs


def _fold(tokens: Sequence[str | _Token]) -> list[str | _Token]:
    root = _Token("", _OPEN, "")
    stack: list[_Token] = [root]
    for token in tokens:
        if isinstance(token, str):
            stack[-1].children.append(token)
            continue
        if token.position == _CLOSE:
            # An end tag only closes the element it matches; anything else is dropped.
            if len(stack) > 1 and stack[-1].name == token.name:
                stack.pop()
        elif token.position == _OPEN:
            stack[-1].children.append(token)
            stack.append(token)
        else:
            stack[-1].children.append(token)
    return root.children


def _materialize(tokens: Sequence[str | _Token]) -> list[Node | str]:
    nodes: list[Node | str] = []
    for token in tokens:
        if isinstance(token, str):
            nodes.append(token)
            continue
        nodes.append(
            Node(
                tag=token.name,
                attrs=_parse_attrs(token.extra),
                children=tuple(_materialize(token.children)),
            )
        )
    return nodes


def _push_text(tokens: list[str | _Token], chunk: str) -> None:
    if not chunk:
        return
    text = _LEADING_SPACE.sub("", unescape(chunk))
    text = _TRAILING_SPACE.sub("", text)
    if text:
        tokens.append(text)


def parse(content: str) -> list[Node | str]:
    """Parse message content into text chunks and elements."""
    tokens: list[str | _Token] = []
    position = 0
    for match in _TAG_PATTERN.finditer(content):
        _push_text(tokens, content[position : match.start()])
        position = match.end()
        if match.group("comment") is not None:
            continue
        close = bool(match.group("close"))
        empty = bool(match.group("empty"))
        tokens.append(
            _Token(
                name=match.group("name") or "",
                position=_CLOSE if close else _EMPTY if empty else _OPEN,
                extra=match.group("extra") or "",
            )
        )
    _push_text(tokens, content[position:])
    return _materialize(_fold(tokens))


def _dump_attrs(attrs: Mapping[str, JsonValue]) -> str:
    parts: list[str] = []
    for key, value in attrs.items():
        if value is None:
            continue
        name = _hyphenate(key)
        if value is True:
            parts.append(f" {name}")
        elif value is False:
            parts.append(f" no-{name}")
        else:
            parts.append(f' {name}="{escape(str(value), True)}"')
    return "".join(parts)


def dump(nodes: Iterable[Node | str]) -> str:
    """Serialize text chunks and elements back into message content."""
    return "".join(_dump_node(node) for node in nodes)


def _dump_node(node: Node | str) -> str:
    if isinstance(node, str):
        return escape(node)
    attrs = _dump_attrs(node.attrs)
    if not node.children:
        return f"<{node.tag}{attrs}/>"
    return f"<{node.tag}{attrs}>{dump(node.children)}</{node.tag}>"


def _find(nodes: Iterable[Node | str], tag: str) -> Node | None:
    for node in nodes:
        if isinstance(node, Node) and node.tag == tag:
            return node
    return None


def _source(node: Node) -> str:
    return _text(node.attr("src")) or _text(node.attr("id")) or ""


def _resource_element(
    tag: str,
    source: str,
    *,
    title: str | None = None,
    width: int | None = None,
    height: int | None = None,
    duration: float | None = None,
    poster: str | None = None,
    file_id: str | None = None,
) -> str:
    attrs: dict[str, JsonValue] = {"src": source}
    if title:
        attrs["title"] = title
    if width is not None:
        attrs["width"] = width
    if height is not None:
        attrs["height"] = height
    if duration is not None:
        attrs["duration"] = duration
    if poster:
        attrs["poster"] = poster
    if file_id:
        attrs["id"] = file_id
    return f"<{tag}{_dump_attrs(attrs)}/>"


def _merge_text(segments: list[Segment]) -> list[Segment]:
    merged: list[Segment] = []
    for segment in segments:
        if isinstance(segment, Text) and merged and isinstance(merged[-1], Text):
            merged[-1] = Text(text=merged[-1].text + segment.text)
            continue
        merged.append(segment)
    return merged


class SatoriSegmentCodec:
    """Translates between V2 messages and Satori message content."""

    def __init__(self) -> None:
        self.registry = SegmentRegistry()
        self._register_segments(self.registry)

    def register_segment(
        self,
        segment_type: type[Segment],
        *,
        wire_type: str,
        decode: SegmentDecoder,
        encode: SegmentEncoder,
        replace: bool = False,
    ) -> None:
        """Register a segment type with this codec so it survives a wire round trip.

        ``decode`` receives the parsed :class:`Node` of an element whose tag equals
        ``wire_type``; ``encode`` returns the element markup for the segment.
        """
        self.registry.register(
            segment_type,
            wire_type=wire_type,
            decode=decode,
            encode=encode,
            replace=replace,
        )

    def decode_message(self, content: str | None, *, channel_id: str | None = None) -> Message:
        """Decode message content.

        ``channel_id`` is the channel the message was received in. Satori message ids
        are channel scoped, so passing it packs the ids of quoted and forwarded
        messages the same way as the ids the adapter hands out for the message itself.
        """
        if not content:
            return Message()
        if not isinstance(content, str):
            raise TypeError("Satori message content must be a string")
        token = _CURRENT_CHANNEL.set(channel_id)
        try:
            return Message(*self._decode_nodes(parse(content)))
        finally:
            _CURRENT_CHANNEL.reset(token)

    def encode_message(self, message: Message) -> str:
        return self._encode_segments(list(message))

    def supports(self, segment_type: type[Segment]) -> bool:
        return self.registry.supports(segment_type)

    def _decode_nodes(self, nodes: Sequence[Node | str]) -> list[Segment]:
        segments: list[Segment] = []
        for node in nodes:
            if isinstance(node, str):
                segments.append(Text(text=node))
                continue
            segments.extend(self._decode_element(node))
        return _merge_text(segments)

    def _decode_element(self, node: Node) -> list[Segment]:
        decode = self.registry.decoder(node.tag)
        if decode is not None:
            try:
                return [decode(node)]
            except Exception:  # noqa: BLE001
                # A decoder that cannot read its element must not take the whole
                # message down; keep the element readable instead.
                logger.warning(f"忽略无法解析的 Satori 消息元素：{node.tag}")
                return [UnknownSegment(wire_type=node.tag, data=dict(node.attrs))]
        segments = self._decode_builtin(node)
        if segments is not None:
            return segments
        # Platform native elements keep their markup so they survive a round trip.
        return [UnknownSegment(wire_type=node.tag, data=dict(node.attrs))]

    def _encode_segments(self, segments: Sequence[Segment]) -> str:
        parts: list[str] = []
        for segment in segments:
            if isinstance(segment, UnknownSegment):
                parts.append(dump([Node(tag=segment.wire_type, attrs=dict(segment.data))]))
                continue
            if isinstance(segment, Markdown):
                # The standard elements have no rich text container, so markdown text
                # is sent as plain text.
                parts.append(escape(segment.text))
                continue
            encode = self.registry.encoder_for(type(segment))
            if encode is None:
                raise TypeError(f"unsupported Satori segment: {type(segment).__name__}")
            parts.append(encode(segment))
        return "".join(parts)

    def _decode_builtin(self, node: Node) -> list[Segment] | None:
        """Decode the standard elements that need more than one flat segment."""
        if node.tag == "sharp":
            name = _text(node.attr("name")) or _text(node.attr("id")) or ""
            return [Text(text=f"#{name}")]
        if node.tag == "a":
            href = _text(node.attr("href"))
            children = self._decode_nodes(node.children)
            if not children:
                return [Text(text=href)] if href else []
            if href:
                children.append(Text(text=f" ({href})"))
            return children
        if node.tag == "br":
            return [Text(text="\n")]
        if node.tag in _PASSTHROUGH_TAGS:
            # Modifiers, metadata and interaction elements carry no structure of their
            # own; keep whatever they wrap.
            return self._decode_nodes(node.children)
        return None

    def _register_segments(self, registry: SegmentRegistry) -> None:
        registry.register(
            Text,
            wire_type="text",
            decode=_decode_text,
            encode=lambda segment: escape(cast(Text, segment).text),
        )
        registry.register(
            Mention,
            wire_type="at",
            decode=_decode_at,
            encode=lambda segment: f'<at id="{escape(cast(Mention, segment).user_id, True)}"/>',
        )
        registry.register(
            MentionAll,
            wire_type="at",
            decode=_decode_at,
            encode=lambda _segment: '<at type="all"/>',
        )
        registry.register(
            Face,
            wire_type="emoji",
            decode=_decode_emoji,
            encode=lambda segment: f'<emoji id="{escape(cast(Face, segment).face_id, True)}"/>',
        )
        registry.register(
            Image,
            wire_type="img",
            decode=_decode_img,
            encode=lambda segment: _resource_element(
                "img",
                cast(Image, segment).source,
                title=cast(Image, segment).alt,
                width=cast(Image, segment).width,
                height=cast(Image, segment).height,
            ),
        )
        registry.register(
            Audio,
            wire_type="audio",
            decode=_decode_audio,
            encode=lambda segment: _resource_element(
                "audio",
                cast(Audio, segment).source,
                title=cast(Audio, segment).title,
                duration=cast(Audio, segment).duration,
            ),
        )
        registry.register(
            Video,
            wire_type="video",
            decode=_decode_video,
            encode=lambda segment: _resource_element(
                "video",
                cast(Video, segment).source,
                duration=cast(Video, segment).duration,
                poster=cast(Video, segment).thumbnail,
            ),
        )
        registry.register(
            File,
            wire_type="file",
            decode=_decode_file,
            encode=lambda segment: _resource_element(
                "file",
                cast(File, segment).source,
                title=cast(File, segment).name,
                file_id=cast(File, segment).file_id,
            ),
        )
        quote_decoder = self._quote_decoder()
        registry.register(
            Quote,
            wire_type="quote",
            decode=quote_decoder,
            encode=lambda segment: _encode_quote(cast(Quote, segment), self),
        )
        message_decoder = self._message_decoder()
        registry.register(
            Forward,
            wire_type="message",
            decode=message_decoder,
            encode=lambda segment: (
                f'<message id="{escape(_wire_message_id(cast(Forward, segment).forward_id), True)}" forward/>'
            ),
        )
        registry.register(
            ForwardNode,
            wire_type="message",
            decode=message_decoder,
            encode=lambda segment: _encode_forward_node(cast(ForwardNode, segment), self),
        )

    def _quote_decoder(self) -> SegmentDecoder:
        def decode(node: Node) -> Segment:
            return Quote(message_id=_packed_id(node.attr("id")), message=self._children_message(node))

        return decode

    def _message_decoder(self) -> SegmentDecoder:
        def decode(node: Node) -> Segment:
            if node.children:
                author = _find(node.children, "author")
                return ForwardNode(
                    user_id=(_text(author.attr("id")) or "") if author is not None else "",
                    display_name=(_text(author.attr("name")) or "") if author is not None else "",
                    message=self._children_message(node, skip="author") or Message(),
                )
            # <message id=".." forward/> forwards a message, so its id is a message id.
            return Forward(forward_id=_packed_id(node.attr("id")))

        return decode

    def _children_message(self, node: Node, skip: str | None = None) -> Message | None:
        children = [child for child in node.children if not (skip and isinstance(child, Node) and child.tag == skip)]
        if not children:
            return None
        return Message(*self._decode_nodes(children))


def _decode_text(node: Node) -> Segment:
    return Text(text=str(node.attr("text") or ""))


def _packed_id(value: object) -> str:
    """Pack a message id from message content with the channel it was received in."""
    message_id = _text(value)
    if message_id is None:
        return ""
    channel_id = _CURRENT_CHANNEL.get()
    return encode_message_id(channel_id, message_id) if channel_id else message_id


def _decode_at(node: Node) -> Segment:
    mention_type = _text(node.attr("type"))
    if mention_type in ("all", "here"):
        return MentionAll()
    user_id = _text(node.attr("id"))
    if user_id is not None:
        return Mention(user_id=user_id)
    name = _text(node.attr("name"))
    return Text(text=f"@{name}" if name is not None else "@")


def _decode_emoji(node: Node) -> Segment:
    return Face(face_id=_text(node.attr("id")) or _text(node.attr("name")) or "")


def _decode_img(node: Node) -> Segment:
    return Image(
        source=_source(node),
        alt=_text(node.attr("title")),
        width=_integer(node.attr("width")),
        height=_integer(node.attr("height")),
    )


def _decode_audio(node: Node) -> Segment:
    return Audio(
        source=_source(node),
        title=_text(node.attr("title")),
        duration=_number(node.attr("duration")),
    )


def _decode_video(node: Node) -> Segment:
    return Video(
        source=_source(node),
        duration=_number(node.attr("duration")),
        thumbnail=_text(node.attr("poster")),
    )


def _decode_file(node: Node) -> Segment:
    return File(
        source=_source(node),
        name=_text(node.attr("title")),
        file_id=_text(node.attr("id")),
    )


def _wire_message_id(message_id: str) -> str:
    """Quote ids travel packed with their channel, but the element wants the inner id."""
    _channel_id, inner = decode_message_id(message_id)
    return inner


def _encode_quote(segment: Quote, codec: SatoriSegmentCodec) -> str:
    attrs = f' id="{escape(_wire_message_id(segment.message_id), True)}"'
    if segment.message is None:
        # The reference serializer writes an element with no children self-closing.
        return f"<quote{attrs}/>"
    return f"<quote{attrs}>{codec._encode_segments(list(segment.message))}</quote>"


def _encode_forward_node(segment: ForwardNode, codec: SatoriSegmentCodec) -> str:
    author = f'<author id="{escape(segment.user_id, True)}" name="{escape(segment.display_name, True)}"/>'
    return f"<message>{author}{codec._encode_segments(list(segment.message))}</message>"


__all__ = [
    "DIRECT_CHANNEL",
    "Node",
    "SatoriSegmentCodec",
    "dump",
    "escape",
    "parse",
    "unescape",
]
