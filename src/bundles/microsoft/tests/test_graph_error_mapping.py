"""Graph rejections that retrying cannot fix must not read as a provider outage."""

from __future__ import annotations

import httpx
import pytest
from lfx.integrations.errors import (
    ActionUnsupportedError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
)
from lfx_microsoft.graph import GraphClient, integration_error_for_response
from microsoft_testkit import RecordingResolver, TransportRecorder, credential
from test_graph_client import lease_for

SPO_LICENSE_BODY = {"error": {"code": "BadRequest", "message": "Tenant does not have a SPO license."}}


def _response(status: int, body: dict | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://graph.microsoft.com/v1.0/me/drive")
    return httpx.Response(status, json=body or {}, request=request)


def test_an_unlicensed_workload_is_a_non_retryable_setup_error() -> None:
    error = integration_error_for_response(_response(400, SPO_LICENSE_BODY))

    assert isinstance(error, InvalidRequestError)
    assert error.code == "invalid-request"
    assert error.retryable is False
    assert error.http_status == 400
    assert "license" in error.message
    assert "Microsoft 365 license" in (error.hint or "")
    assert "retry" not in error.message.casefold()


def test_the_provider_message_is_not_echoed_verbatim() -> None:
    error = integration_error_for_response(_response(400, SPO_LICENSE_BODY))

    assert "SPO" not in error.message
    assert "SPO" not in (error.hint or "")


def test_a_mailbox_that_graph_cannot_reach_is_a_setup_error_not_an_unsupported_action() -> None:
    body = {
        "error": {
            "code": "MailboxNotEnabledForRESTAPI",
            "message": "The mailbox is either inactive, soft-deleted, or is hosted on-premise.",
        }
    }

    error = integration_error_for_response(_response(404, body))

    assert isinstance(error, InvalidRequestError)
    assert not isinstance(error, ActionUnsupportedError)
    assert error.retryable is False
    assert "Exchange Online" in (error.hint or "")


@pytest.mark.parametrize("status", [400, 409, 412, 413, 422])
def test_other_client_rejections_are_invalid_requests(status: int) -> None:
    body = {"error": {"code": "invalidRequest", "message": "Invalid filter clause"}}

    error = integration_error_for_response(_response(status, body))

    assert isinstance(error, InvalidRequestError)
    assert error.retryable is False
    assert error.http_status == status


@pytest.mark.parametrize("status", [408, 500, 502, 504])
def test_timeouts_and_server_failures_stay_provider_unavailable(status: int) -> None:
    error = integration_error_for_response(_response(status, {"error": {"code": "generalException"}}))

    assert isinstance(error, ProviderUnavailableError)
    assert error.retryable is True


def test_service_unavailable_is_still_rate_limited() -> None:
    assert isinstance(integration_error_for_response(_response(503)), RateLimitedError)


async def test_a_client_request_to_an_unlicensed_tenant_raises_the_setup_error() -> None:
    recorder = TransportRecorder(lambda _request: httpx.Response(400, json=SPO_LICENSE_BODY))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(InvalidRequestError, match="license"):
            await client.get_json("/me/drive")
    assert len(recorder.requests) == 1
