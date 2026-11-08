"""Transport failures must explain server connectivity, including on an auth retry."""

import errno
import socket
import ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import FAKE_ACCESS_TOKEN, FAKE_REFRESHED_TOKEN, RecordedHttp
from httplib2 import Response, ServerNotFoundError
from lfx.integrations import IntegrationError, normalize_integration_error
from lfx_google.components.google._workspace_client import WorkspaceService, _build_service

PRIVATE_ERROR = "private-payload user@example.com https://example.com/private?token=secret"


@pytest.mark.parametrize(
    ("failure", "reason", "message"),
    [
        (TimeoutError(PRIVATE_ERROR), "timeout", "timed out"),
        (socket.gaierror(PRIVATE_ERROR), "dns", "DNS lookup failed"),
        (ServerNotFoundError(PRIVATE_ERROR), "dns", "DNS lookup failed"),
        (ConnectionRefusedError(PRIVATE_ERROR), "refused", "connection refused"),
        (ConnectionResetError(PRIVATE_ERROR), "connection", "connection failed"),
        (OSError(errno.ENETUNREACH, PRIVATE_ERROR), "unreachable", "network unreachable"),
        (OSError(errno.EHOSTUNREACH, PRIVATE_ERROR), "unreachable", "network unreachable"),
        (ssl.SSLError(PRIVATE_ERROR), "tls", "TLS connection failed"),
        (ssl.SSLCertVerificationError(PRIVATE_ERROR), "tls", "TLS connection failed"),
    ],
)
@pytest.mark.parametrize("after_refresh", [False, True])
async def test_network_failures_are_actionable_without_replaying_the_action(failure, reason, message, after_refresh):
    lease = SimpleNamespace(
        get_token=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
        get_token_after_auth_error=AsyncMock(return_value=FAKE_REFRESHED_TOKEN),
    )
    http = RecordedHttp([])
    outcomes = [(Response({"status": "401"}), b'{"error":{"code":401}}')] if after_refresh else []
    http.request = Mock(side_effect=[*outcomes, failure])
    service = WorkspaceService(lease, "gmail", "v1", http=http)
    try:
        with pytest.raises(IntegrationError) as raised:
            await service.execute(lambda client: client.users().messages().send(userId="me", body={"raw": "fake"}))
    finally:
        await service.aclose()

    error = raised.value
    assert error.code == "network-error"
    assert error.details == {"reason": reason, "host": "gmail.googleapis.com"}
    assert error.http_status == (504 if reason == "timeout" else 502)
    assert error.retryable is False
    assert "gmail.googleapis.com" in str(error)
    assert message in str(error)
    assert "Check this server's outbound network access" in str(error)
    assert "temporarily unavailable" not in str(error)
    # Python 3.11 can recreate TimeoutError when transferring it from a worker thread.
    assert type(error.__cause__) is type(failure)
    assert error.__cause__.args == failure.args
    assert http.request.call_count == (2 if after_refresh else 1)
    assert lease.get_token_after_auth_error.await_count == int(after_refresh)
    assert http.close_count == (2 if after_refresh else 1)
    for private in ("private-payload", "user@example.com", "token=secret", FAKE_ACCESS_TOKEN):
        assert private not in str(error)
        assert private not in str(error.details)
        assert private not in error.hint


@pytest.mark.parametrize("status", [408, 500, 502, 503, 504])
async def test_actual_http_outages_keep_the_provider_error(status):
    lease = SimpleNamespace(get_token=AsyncMock(return_value=FAKE_ACCESS_TOKEN))
    http = RecordedHttp([({"status": str(status)}, b'{"error":{"message":"private-payload"}}')])
    service = WorkspaceService(lease, "gmail", "v1", http=http)
    try:
        with pytest.raises(IntegrationError) as raised:
            await service.execute(lambda client: client.users().messages().list(userId="me"))
    finally:
        await service.aclose()
    assert raised.value.code == "provider-unavailable"
    assert raised.value.http_status == status
    assert raised.value.retryable is True
    assert "private-payload" not in str(raised.value)


def test_chained_network_errors_are_classified_without_using_raw_exception_text():
    wrapped = RuntimeError(PRIVATE_ERROR)
    wrapped.__cause__ = TimeoutError(PRIVATE_ERROR)
    error = normalize_integration_error(wrapped, provider="google")
    assert error.code == "network-error"
    assert error.details["reason"] == "timeout"
    assert "private-payload" not in str(error)


@pytest.mark.parametrize("failure", [FileNotFoundError(PRIVATE_ERROR), PermissionError(PRIVATE_ERROR), ValueError()])
def test_non_network_failures_are_not_misclassified(failure):
    assert normalize_integration_error(failure, provider="google").code != "network-error"


def test_default_transport_has_a_short_socket_timeout_without_global_changes():
    original_timeout = socket.getdefaulttimeout()
    service = _build_service("gmail", "v1", FAKE_ACCESS_TOKEN, None)
    try:
        assert 0 < service._http.http.timeout <= 10
        assert 308 not in service._http.http.redirect_codes
        assert socket.getdefaulttimeout() == original_timeout
    finally:
        service.close()


async def test_drive_media_downloads_get_the_same_network_diagnostics():
    lease = SimpleNamespace(get_token=AsyncMock(return_value=FAKE_ACCESS_TOKEN))
    http = RecordedHttp([])
    http.request = Mock(side_effect=TimeoutError(PRIVATE_ERROR))
    service = WorkspaceService(lease, "drive", "v3", http=http)
    try:
        with pytest.raises(IntegrationError) as raised:
            await service.download(lambda client: client.files().get_media(fileId="fake"), max_bytes=1024)
    finally:
        await service.aclose()
    assert raised.value.code == "network-error"
    assert "www.googleapis.com" in str(raised.value)
    assert "outbound network access" in str(raised.value)
    assert http.request.call_count == 1
