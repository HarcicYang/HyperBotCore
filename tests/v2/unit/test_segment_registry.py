import pytest

from hyperot.v2.messages import Segment, SegmentRegistry


class Alpha(Segment):
    value: str


class Beta(Segment):
    value: str


def decode_alpha(_payload: object) -> Segment:
    return Alpha(value="decoded")


def encode_alpha(_segment: Segment) -> dict[str, object]:
    return {"value": "encoded"}


def decode_beta(_payload: object) -> Segment:
    return Beta(value="decoded-beta")


def encode_beta(_segment: Segment) -> dict[str, object]:
    return {"value": "encoded-beta"}


def build_registry() -> SegmentRegistry:
    registry = SegmentRegistry()
    registry.register(Alpha, wire_type="alpha", decode=decode_alpha, encode=encode_alpha)
    return registry


def test_registry_maps_wire_types_and_encoders():
    registry = build_registry()

    assert registry.decoder("alpha") is decode_alpha
    assert registry.decoder("nope") is None
    assert registry.wire_types() == frozenset({"alpha"})
    assert registry.wire_type(Alpha) == "alpha"
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


def test_registry_rejects_duplicates_and_supports_replacement():
    registry = build_registry()

    with pytest.raises(ValueError):
        registry.register(Beta, wire_type="alpha", decode=decode_beta, encode=encode_beta)
    with pytest.raises(ValueError):
        registry.register(Alpha, wire_type="beta", decode=decode_alpha, encode=encode_alpha)

    registry.register(Beta, wire_type="alpha", decode=decode_beta, encode=encode_beta, replace=True)

    assert registry.decoder("alpha") is decode_beta
    assert registry.encoder_for(Beta) is encode_beta
    assert registry.segment_types() == frozenset({Alpha, Beta})


def test_registry_rejects_non_segment_types():
    registry = SegmentRegistry()

    with pytest.raises(TypeError):
        registry.register(str, wire_type="alpha", decode=decode_alpha, encode=encode_alpha)  # type: ignore[type-arg]
