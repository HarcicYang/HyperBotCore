"""Identifiers the Satori API needs but the V2 core does not carry.

Satori addresses messages, requests and logins by pairs: a message id only means
something together with its channel id, a request id only means something together
with whether it is a friend request, a join request or a guild invitation, and every
API call needs the login it belongs to. This module packs those into stable strings
so the core layer can pass ids around opaquely.
"""

from __future__ import annotations

SEPARATOR = ":"

FRIEND_REQUEST = "friend"
GUILD_MEMBER_REQUEST = "member"
GUILD_REQUEST = "guild"


def encode_message_id(channel_id: object, message_id: object) -> str:
    return f"{channel_id}{SEPARATOR}{message_id}"


def decode_message_id(message_id: object) -> tuple[str, str]:
    """Split a packed message id into ``(channel_id, message_id)``.

    A message id without the separator has no channel context, which the caller has
    to report rather than guess.
    """
    text = str(message_id)
    channel, separator, rest = text.partition(SEPARATOR)
    if not separator:
        return "", text
    return channel, rest


def encode_friend_request_id(message_id: object) -> str:
    return f"{FRIEND_REQUEST}{SEPARATOR}{message_id}"


def encode_guild_member_request_id(guild_id: object, message_id: object) -> str:
    return f"{GUILD_MEMBER_REQUEST}{SEPARATOR}{guild_id}{SEPARATOR}{message_id}"


def encode_guild_request_id(guild_id: object, message_id: object) -> str:
    return f"{GUILD_REQUEST}{SEPARATOR}{guild_id}{SEPARATOR}{message_id}"


def decode_request_id(request_id: object) -> tuple[str, str, str]:
    """Split a packed request id into ``(kind, guild_id, message_id)``."""
    text = str(request_id)
    kind, separator, rest = text.partition(SEPARATOR)
    if not separator:
        raise ValueError(f"invalid Satori request id: {text}")
    if kind == FRIEND_REQUEST:
        return kind, "", rest
    guild_id, separator, message_id = rest.partition(SEPARATOR)
    if not separator:
        raise ValueError(f"invalid Satori request id: {text}")
    return kind, guild_id, message_id


def encode_login_id(platform: object, user_id: object) -> str:
    return f"{platform}{SEPARATOR}{user_id}"


__all__ = [
    "FRIEND_REQUEST",
    "GUILD_MEMBER_REQUEST",
    "GUILD_REQUEST",
    "SEPARATOR",
    "decode_message_id",
    "decode_request_id",
    "encode_friend_request_id",
    "encode_guild_member_request_id",
    "encode_guild_request_id",
    "encode_login_id",
    "encode_message_id",
]
