import errno
import socket
import ssl
from types import SimpleNamespace

import httpx
import pytest
from websockets.exceptions import InvalidStatus, InvalidURI

from hyperot.v2.common import AdapterConnectionError, bind_error, connection_error, describe


def test_refused_connection_names_the_endpoint():
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


def test_httpx_error_unwraps_the_refused_socket():
    try:
        raise httpx.ConnectError("All connection attempts failed") from ConnectionRefusedError(
            errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5700)"
        )
    except httpx.HTTPError as exc:
        error = connection_error(exc, label="OneBot", target="http://127.0.0.1:5700/get_status", kind="HTTP call")

    assert str(error) == (
        "OneBot HTTP call to http://127.0.0.1:5700/get_status failed: connection refused "
        "(check that the OneBot end is running and listening on 127.0.0.1:5700)"
    )


def test_dns_failure_is_reported_separately():
    reason, hint = describe(
        socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"),
        target="ws://localhost.example:5004",
        label="OneBot",
    )

    assert reason == "cannot resolve the hostname"
    assert "localhost.example:5004" in hint


def test_httpx_error_follows_the_context_chain():
    # httpcore re-raises with `from None`, so the socket error only survives in __context__.
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

    assert str(error) == (
        "OneBot HTTP call to http://127.0.0.1:5700 failed: connection refused "
        "(check that the OneBot end is running and listening on 127.0.0.1:5700)"
    )


def test_exception_group_still_yields_the_socket_error():
    oserrors = [
        OSError("All connection attempts failed"),
        ConnectionRefusedError(errno.ECONNREFUSED, "Connect call failed ('127.0.0.1', 5700)"),
    ]
    try:
        try:
            raise ExceptionGroup("multiple connection attempts failed", oserrors)
        except ExceptionGroup as group:
            raise OSError("All connection attempts failed") from group
    except OSError as aggregated:
        try:
            raise httpx.ConnectError("All connection attempts failed") from aggregated
        except httpx.HTTPError as exc:
            error = connection_error(exc, label="OneBot", target="http://127.0.0.1:5700", kind="HTTP call")

    assert "connection refused" in str(error)
    reason, hint = describe(
        socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution"),
        target="ws://localhost.example:5004",
        label="OneBot",
    )

    assert reason == "cannot resolve the hostname"
    assert "localhost.example:5004" in hint


def test_listener_port_conflict_points_at_the_address():
    error = bind_error(
        OSError(errno.EADDRINUSE, "Address already in use"),
        label="OneBot",
        target="127.0.0.1:6701",
    )

    assert str(error) == (
        "OneBot listener on 127.0.0.1:6701 failed: address already in use "
        "(another process is already listening on 127.0.0.1:6701)"
    )


def test_listener_failures_are_worded_for_listening():
    denied = bind_error(OSError(errno.EACCES, "Permission denied"), label="OneBot", target="0.0.0.0:80")
    assert "not allowed to listen on 0.0.0.0:80" in str(denied)

    odd = bind_error(OSError(errno.EBADF, "Bad file descriptor"), label="OneBot", target="127.0.0.1:6701")
    assert "available on this machine" in str(odd)


def test_rejected_handshake_mentions_the_access_token():
    cases = {401: "access_token", 404: "WebSocket endpoint"}
    for status, expected in cases.items():
        reason, hint = describe(
            InvalidStatus(SimpleNamespace(status_code=status)),
            target="ws://127.0.0.1:5004/event",
            label="OneBot",
        )
        assert reason == f"server rejected the handshake with HTTP {status}"
        assert expected in hint


def test_tls_failure_mentions_the_certificate():
    reason, hint = describe(
        ssl.SSLError("certificate verify failed"),
        target="wss://onebot.example:5004",
        label="OneBot",
    )

    assert reason.startswith("TLS error")
    assert "certificate" in hint


def test_unknown_failures_stay_descriptive():
    reason, hint = describe(RuntimeError("boom"), target="ws://127.0.0.1:5004", label="OneBot")
    assert reason == "RuntimeError: boom"
    assert hint is None


@pytest.mark.parametrize(
    "target",
    ["ws://127.0.0.1:5004/event", "127.0.0.1:5004", "ws://[::1]:5004/event"],
)
def test_message_keeps_the_configured_target(target: str):
    error = connection_error(
        OSError(errno.ECONNREFUSED, "refused"),
        label="Milky",
        target=target,
        kind="websocket connection",
    )
    assert target in str(error)


def test_invalid_url_scheme_is_reported():
    reason, hint = describe(InvalidURI("ws://", "isn't a valid URI"), target="ws://", label="OneBot")
    assert reason.startswith("invalid connection URL")
    assert "host" in hint
