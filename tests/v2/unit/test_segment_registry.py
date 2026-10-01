import dataclasses

import pytest

from hyperot.v2.messages import Segment, SegmentRegistry


class Alpha(Segment):
    value: str


class Beta(Segment):
    value: str


def decode_alpha(payload: object) -> Segment:
    return Alpha(value="decoded")


def encode_alpha(segment: Segment) -> dict[str, object]:
    return {"value": "encoded"}


def decode_beta(payload: object) -> Segment:
    return Beta(value="decoded-beta")


def encode_beta(segment: Segment) -> dict[str, object]:
    return {"value": "encoded-beta"}


def build_registry() -> SegmentRegistry:
    registry = SegmentRegistry()
    registry.register(Alpha, wire_type="alpha", decode=decode_alpha, encode=encode_alpha)
    return registry


def test_registry_decodes_by_wire_type():
    registry = build_registry()

    assert registry.decoder("alpha") is decode_alpha
    assert registry.decoder("nope") is None
    assert registry.wire_types() == frozenset({"alpha"})
    assert registry.wire_type(Alpha) == "alpha"


def test_registry_encodes_and_reports_support():
    registry = build_registry()

    assert registry.encoder_for(Alpha) is encode_alpha
    assert registry.supports(Alpha)
    assert not registry.supports(Beta)
    assert registry.segment_types() == frozenset({Alpha})


def test_registry_encoder_falls_back_to_registered_base():
    registry = build_registry()

    class Unregistered(Alpha):
        pass

    assert registry.encoder_for(Unregistered) is encode_alpha
    assert registry.supports(Unregistered)
    assert registry.wire_type(Unregistered) == "alpha"


def test_registry_rejects_duplicate_segment_and_wire_type():
    registry = build_registry()

    with pytest.raises(ValueError):
        registry.register(Beta, wire_type="alpha", decode=decode_beta, encode=encode_beta)
    with pytest.raises(ValueError):
        registry.register(Alpha, wire_type="beta", decode=decode_alpha, encode=encode_alpha)


def test_registry_replace_overrides_both_directions():
    registry = build_registry()
    registry.register(
        Beta,
        wire_type="alpha",
        decode=decode_beta,
        encode=encode_beta,
        replace=True,
    )

    assert registry.decoder("alpha") is decode_beta
    assert registry.encoder_for(Beta) is encode_beta
    assert registry.segment_types() == frozenset({Alpha, Beta})


def test_registry_rejects_non_segment_type():
    registry = SegmentRegistry()

    with pytest.raises(TypeError):
        registry.register(str, wire_type="alpha", decode=decode_alpha, encode=encode_alpha)  # type: ignore[type-arg]


def test_annotated_subclass_is_a_frozen_dataclass():
    assert dataclasses.is_dataclass(Alpha)
    assert [field.name for field in dataclasses.fields(Alpha)] == ["value"]

    segment = Alpha(value="x")

    with pytest.raises(dataclasses.FrozenInstanceError):
        segment.value = "y"
    assert hash(segment) == hash(Alpha(value="x"))
    assert segment == Alpha(value="x")
