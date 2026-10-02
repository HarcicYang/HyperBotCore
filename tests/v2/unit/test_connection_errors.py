import errno
import socket
import ssl
from types import SimpleNamespace

import httpx
import pytest
from websockets.exceptions import InvalidStatus, InvalidURI

from hyperot.v2.common import AdapterConnectionError, bind_error, connection_error, describe


def test_connection_error_wraps_the_refused_socket_and_target():
    error = connection_error(
        ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5004)"),
        label="OneBot",
        target="ws://127.0.0.1:5004",
        kind="websocket connection",
    )

    assert isinstance(error, AdapterConnectionError)
    assert str(error) == (
        "OneBot websocket connection to ws://127.0.0.1:5004 failed: connection refused "
        "(check that the OneBot end is running and listening on 127.0.0.1:5004)"
    )


def test_httpx_errors_follow_the_context_chain():
    try:
        try:
            raise ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5700)")
        except OSError as socket_error:
            raise OSError("All connection attempts failed") from socket_error
    except OSError as aggregated:
        try:
            raise httpx.ConnectError("All connection attempts failed") from aggregated
        except httpx.HTTPError as exc:
            error = connection_error(exc, label="OneBot", target="http://127.0.0.1:5700", kind="HTTP call")

    assert "connection refused" in str(error)


@pytest.mark.parametrize(
    ("exception", "expected_reason", "expected_hint"),
    [
        (
            socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"),
            "cannot resolve the hostname",
            "localhost.example:5004",
        ),
        (ssl.SSLError("certificate verify failed"), "TLS error", "certificate"),
        (RuntimeError("boom"), "RuntimeError: boom", None),
    ],
)
def test_describe_classifies_connection_failures(exception, expected_reason, expected_hint):
    reason, hint = describe(exception, target="ws://localhost.example:5004", label="OneBot")

    if expected_reason == "TLS error":
        assert reason.startswith(expected_reason)
    else:
        assert reason == expected_reason
    if expected_hint is None:
        assert hint is None
    else:
        assert expected_hint in hint


def test_handshake_and_url_failures_include_actionable_hints():
    unauthorized = describe(
        InvalidStatus(SimpleNamespace(status_code=401)),
        target="ws://127.0.0.1:5004/event",
        label="OneBot",
    )
    not_found = describe(
        InvalidStatus(SimpleNamespace(status_code=404)),
        target="ws://127.0.0.1:5004/event",
        label="OneBot",
    )
    invalid = describe(InvalidURI("ws://", "isn't a valid URI"), target="ws://", label="OneBot")

    assert unauthorized[0] == "server rejected the handshake with HTTP 401"
    assert "access_token" in unauthorized[1]
    assert "WebSocket endpoint" in not_found[1]
    assert invalid[0].startswith("invalid connection URL")
    assert "host" in invalid[1]


def test_bind_errors_name_the_listening_address():
    occupied = bind_error(
        OSError(errno.EADDRINUSE, "Address already in use"),
        label="OneBot",
        target="127.0.0.1:6701",
    )
    denied = bind_error(OSError(errno.EACCES, "Permission denied"), label="OneBot", target="0.0.0.0:80")
    odd = bind_error(OSError(errno.EBADF, "Bad file descriptor"), label="OneBot", target="127.0.0.1:6701")

    assert "127.0.0.1:6701" in str(occupied)
    assert "already listening" in str(occupied)
    assert "not allowed to listen on 0.0.0.0:80" in str(denied)
    assert "available on this machine" in str(odd)


@pytest.mark.parametrize("target", ["ws://127.0.0.1:5004/event", "127.0.0.1:5004", "ws://[::1]:5004/event"])
def test_error_message_keeps_the_configured_target(target: str):
    error = connection_error(OSError(errno.ECONNREFUSED, "refused"), label="Milky", target=target, kind="connection")

    assert target in str(error)
