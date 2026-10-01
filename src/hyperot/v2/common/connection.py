from __future__ import annotations

import errno
import socket
import ssl
from typing import NamedTuple
from urllib.parse import urlsplit

import httpx
from websockets.exceptions import (
    InvalidHandshake,
    InvalidStatus,
    InvalidURI,
    SecurityError,
)

from .errors import AdapterConnectionError


class _Hint(NamedTuple):
    """Two ways to say the same fix: one for dialing out, one for listening."""

    outbound: str
    inbound: str | None = None


# errno constants differ per platform, so they are resolved by name instead of hardcoded.
_OS_REASONS: tuple[tuple[str, str], ...] = (
    ("EACCES", "permission denied"),
    ("EADDRINUSE", "address already in use"),
    ("EADDRNOTAVAIL", "address not available"),
    ("ECONNABORTED", "connection aborted"),
    ("ECONNREFUSED", "connection refused"),
    ("ECONNRESET", "connection reset by the peer"),
    ("EHOSTDOWN", "host is down"),
    ("EHOSTUNREACH", "host unreachable"),
    ("ENETDOWN", "network is down"),
    ("ENETRESET", "connection reset by the network"),
    ("ENETUNREACH", "network unreachable"),
    ("EPERM", "permission denied"),
    ("ETIMEDOUT", "connection timed out"),
)

_OS_HINTS: tuple[tuple[str, _Hint], ...] = (
    ("ECONNREFUSED", _Hint("check that the {label} end is running and listening on {endpoint}")),
    (
        "EACCES",
        _Hint(
            "this process is not allowed to connect to {endpoint}",
            "this process is not allowed to listen on {endpoint}",
        ),
    ),
    ("EADDRINUSE", _Hint("check that {endpoint} is reachable", "another process is already listening on {endpoint}")),
    ("EADDRNOTAVAIL", _Hint("check that {endpoint} is reachable", "{endpoint} is not available on this machine")),
    ("EHOSTUNREACH", _Hint("check the network path to {endpoint}")),
    ("ENETDOWN", _Hint("check the network path to {endpoint}")),
    ("ENETUNREACH", _Hint("check the network path to {endpoint}")),
    (
        "EPERM",
        _Hint(
            "this process is not allowed to connect to {endpoint}",
            "this process is not allowed to listen on {endpoint}",
        ),
    ),
    ("ETIMEDOUT", _Hint("check that {endpoint} is reachable and not blocked by a firewall")),
)

_OS_FALLBACK = _Hint("check that {endpoint} is reachable", "check that {endpoint} is available on this machine")


def _lookup(table: tuple[tuple[str, str], ...], code: int | None) -> str | None:
    if code is None:
        return None
    for name, value in table:
        if getattr(errno, name, None) == code:
            return value
    return None


def _hint_for(code: int | None) -> _Hint | None:
    if code is None:
        return None
    for name, hint in _OS_HINTS:
        if getattr(errno, name, None) == code:
            return hint
    return None


def _better_socket_error(current: OSError | None, candidate: OSError) -> OSError:
    """Prefer the error that carries an errno, since that is the one worth naming."""
    if current is None or (current.errno is None and candidate.errno is not None):
        return candidate
    return current


def _socket_error(exc: BaseException) -> OSError | None:
    """Find the OS-level error behind a wrapped exception, preferring one with an errno.

    httpx and httpcore both re-wrap socket errors and httpcore raises ``from None``, so the
    original is often only reachable through ``__context__`` or an exception group.
    """
    found: OSError | None = None
    stack: list[BaseException] = [exc]
    seen: set[int] = set()
    while stack and len(seen) < 12:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, BaseExceptionGroup):
            stack.extend(node.exceptions)
            continue
        if node is not exc and isinstance(node, OSError):
            found = _better_socket_error(found, node)
        for link in ("__cause__", "__context__"):
            if (nxt := getattr(node, link, None)) is not None:
                stack.append(nxt)
    return found


def _endpoint(target: str) -> str:
    try:
        parts = urlsplit(target)
    except ValueError:
        return target
    host = parts.hostname
    if not host:
        return target
    host = f"[{host}]" if ":" in host else host
    return f"{host}:{parts.port}" if parts.port is not None else host


def describe(exc: BaseException, *, target: str, label: str, listening: bool = False) -> tuple[str, str | None]:
    """Return why a connection attempt failed, plus a hint on how to fix it."""
    target_endpoint = _endpoint(target)

    def hint(found: _Hint | None) -> str | None:
        if found is None:
            return None
        template = (found.inbound or found.outbound) if listening else found.outbound
        return template.format(endpoint=target_endpoint, label=label)

    if isinstance(exc, socket.gaierror):
        return "cannot resolve the hostname", f"check that {target_endpoint} can be resolved on this machine"
    if isinstance(exc, ssl.SSLError):
        return f"TLS error: {exc}", "check that the endpoint uses the configured scheme and a trusted certificate"
    if isinstance(exc, TimeoutError):
        return "connection timed out", hint(_hint_for(errno.ETIMEDOUT))
    if isinstance(exc, InvalidURI):
        return f"invalid connection URL: {exc}", "check the configured URL host and scheme"
    if isinstance(exc, InvalidStatus):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            return (
                f"server rejected the handshake with HTTP {status}",
                f"check that access_token matches the token set on the {label} end",
            )
        return (
            f"server rejected the handshake with HTTP {status}",
            f"check that the path is a WebSocket endpoint on the {label} end",
        )
    if isinstance(exc, SecurityError):
        return f"handshake rejected by a security rule: {exc}", f"check the access_token on the {label} end"
    if isinstance(exc, InvalidHandshake):
        return f"handshake rejected: {exc}", f"check the path and access_token on the {label} end"
    if isinstance(exc, httpx.HTTPError):
        inner = _socket_error(exc)
        if inner is not None:
            return describe(inner, target=target, label=label, listening=listening)
        if isinstance(exc, httpx.ConnectTimeout | httpx.ReadTimeout | httpx.PoolTimeout):
            return "request timed out", hint(_hint_for(errno.ETIMEDOUT))
        if isinstance(exc, httpx.UnsupportedProtocol):
            return "unsupported URL scheme", "use an http:// or https:// URL"
        return f"{type(exc).__name__}: {exc}", None
    if isinstance(exc, OSError):
        reason = _lookup(_OS_REASONS, exc.errno) or str(exc) or type(exc).__name__
        return reason, hint(_hint_for(exc.errno)) or hint(_OS_FALLBACK)
    if isinstance(exc, SystemExit):
        return "the process exited during startup", hint(_hint_for(errno.EADDRINUSE))
    return f"{type(exc).__name__}: {exc}", None


def _message(exc: BaseException, *, target: str, label: str, subject: str, listening: bool) -> str:
    reason, note = describe(exc, target=target, label=label, listening=listening)
    message = f"{label} {subject} {target} failed: {reason}"
    return f"{message} ({note})" if note else message


def connection_error(exc: BaseException, *, label: str, target: str, kind: str) -> AdapterConnectionError:
    """Describe an outbound connection attempt that could not be established."""
    subject = kind if kind.endswith(" to") else f"{kind} to"
    return AdapterConnectionError(_message(exc, target=target, label=label, subject=subject, listening=False))


def bind_error(exc: BaseException, *, label: str, target: str) -> AdapterConnectionError:
    """Describe an inbound listener that could not start."""
    return AdapterConnectionError(_message(exc, target=target, label=label, subject="listener on", listening=True))


__all__ = ["bind_error", "connection_error", "describe"]
