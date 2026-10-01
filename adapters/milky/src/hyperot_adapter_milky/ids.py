"""Message identifiers.

Milky identifies messages by the scene they live in plus a per-scene sequence
number, so there is no protocol-wide message id. This module packs the triple
into a stable string so the core layer can pass ids around opaquely.
"""

from __future__ import annotations

SCENE_FRIEND = "friend"
SCENE_GROUP = "group"
SCENE_TEMP = "temp"

SEPARATOR = ":"


def encode_message_id(scene: str, peer_id: int | str, message_seq: int | str) -> str:
    return f"{scene}{SEPARATOR}{peer_id}{SEPARATOR}{message_seq}"


def decode_message_id(message_id: object) -> tuple[str, str, str]:
    text = str(message_id)
    scene, separator, rest = text.partition(SEPARATOR)
    if not separator:
        raise ValueError(f"invalid Milky message id: {text}")
    peer_id, separator, seq = rest.partition(SEPARATOR)
    if not separator or not seq:
        raise ValueError(f"invalid Milky message id: {text}")
    return scene, peer_id, seq


def encode_group_request_id(group_id: int | str, notification_seq: int | str) -> str:
    return f"group_request{SEPARATOR}{group_id}{SEPARATOR}{notification_seq}"


def decode_group_request_id(request_id: object) -> tuple[str, str]:
    return _decode_pair_id(request_id, "group_request")


def encode_group_invitation_id(group_id: int | str, invitation_seq: int | str) -> str:
    return f"group_invitation{SEPARATOR}{group_id}{SEPARATOR}{invitation_seq}"


def decode_group_invitation_id(request_id: object) -> tuple[str, str]:
    return _decode_pair_id(request_id, "group_invitation")


def _decode_pair_id(request_id: object, kind: str) -> tuple[str, str]:
    text = str(request_id)
    prefix, separator, rest = text.partition(SEPARATOR)
    if prefix != kind or not separator:
        raise ValueError(f"invalid Milky {kind} id: {text}")
    group_id, separator, seq = rest.partition(SEPARATOR)
    if not separator or not seq:
        raise ValueError(f"invalid Milky {kind} id: {text}")
    return group_id, seq


__all__ = [
    "SCENE_FRIEND",
    "SCENE_GROUP",
    "SCENE_TEMP",
    "decode_group_invitation_id",
    "decode_group_request_id",
    "decode_message_id",
    "encode_group_invitation_id",
    "encode_group_request_id",
    "encode_message_id",
]
