from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .segments import Segment

SegmentT = TypeVar("SegmentT", bound=Segment)

SegmentDecoder = Callable[[Any], Segment]
SegmentEncoder = Callable[[Segment], Any]

__all__ = ["SegmentDecoder", "SegmentEncoder", "SegmentRegistry"]


class SegmentRegistry:
    """Binds segment classes to the wire payloads of one adapter.

    An adapter owns a single registry, fills it with the segments it understands and
    exposes it, so third parties can register their own segment types for the same
    adapter without touching adapter internals.
    """

    def __init__(self) -> None:
        self._decoders: dict[str, SegmentDecoder] = {}
        self._encoders: dict[type[Segment], SegmentEncoder] = {}
        self._wire_types: dict[type[Segment], str] = {}

    def register(
        self,
        segment_type: type[SegmentT],
        *,
        wire_type: str,
        decode: SegmentDecoder,
        encode: SegmentEncoder,
        replace: bool = False,
    ) -> None:
        if not (isinstance(segment_type, type) and issubclass(segment_type, Segment)):
            raise TypeError(f"not a segment type: {segment_type!r}")
        if segment_type in self._encoders and not replace:
            raise ValueError(f"segment already registered: {segment_type.__name__}")
        known = self._decoders.get(wire_type)
        if known is not None and known is not decode and not replace:
            raise ValueError(f"wire type {wire_type!r} is already decoded by {known!r}")
        self._encoders[segment_type] = encode
        self._wire_types[segment_type] = wire_type
        self._decoders[wire_type] = decode

    def decoder(self, wire_type: str) -> SegmentDecoder | None:
        return self._decoders.get(wire_type)

    def encoder_for(self, segment_type: type[Segment]) -> SegmentEncoder | None:
        for candidate in segment_type.__mro__:
            encoder = self._encoders.get(candidate)
            if encoder is not None:
                return encoder
        return None

    def supports(self, segment_type: type[Segment]) -> bool:
        return self.encoder_for(segment_type) is not None

    def wire_type(self, segment_type: type[Segment]) -> str | None:
        for candidate in segment_type.__mro__:
            wire_type = self._wire_types.get(candidate)
            if wire_type is not None:
                return wire_type
        return None

    def segment_types(self) -> frozenset[type[Segment]]:
        return frozenset(self._encoders)

    def wire_types(self) -> frozenset[str]:
        return frozenset(self._decoders)
