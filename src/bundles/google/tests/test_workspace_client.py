"""Credential lifetime and transport cleanup at the Google SDK boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from conftest import FAKE_ACCESS_TOKEN, FAKE_REFRESHED_TOKEN, RecordedHttp, json_response, wire
from lfx.integrations import ProviderUnavailableError
from lfx_google.components.google._workspace_client import WorkspaceService
from lfx_google.components.google.google_drive_list import GoogleDriveListComponent


async def test_every_request_uses_the_current_lease_token():
    lease = SimpleNamespace(get_token=AsyncMock(side_effect=[FAKE_ACCESS_TOKEN, FAKE_REFRESHED_TOKEN]))
    http = RecordedHttp([json_response("drive_list_response"), json_response("drive_list_response")])
    service = WorkspaceService(lease, "drive", "v3", http=http)
    await service.execute(lambda client: client.files().list())
    await service.execute(lambda client: client.files().list())

    assert lease.get_token.await_count == 2
    headers = http.request_sequence[-1][3]
    authorization = headers.get("authorization", headers.get("Authorization", ""))
    assert FAKE_REFRESHED_TOKEN in str(authorization)
    assert http.close_count == 1  # Superseded token's client was closed.
    await service.aclose()
    assert http.close_count == 2


@pytest.mark.usefixtures("resolver")
@pytest.mark.parametrize("fails", [False, True])
async def test_action_closes_the_sdk_transport_on_success_and_failure(fails):
    component = GoogleDriveListComponent()
    response = ({"status": "503"}, b'{"error":{"code":503}}') if fails else json_response("drive_list_response")
    http = wire(component, [response])
    if fails:
        with pytest.raises(ProviderUnavailableError):
            await component.list_page()
    else:
        await component.list_page()
    assert http.close_count == 1


@pytest.mark.parametrize(
    ("status", "reason", "code"),
    [
        (403, "insufficientPermissions", "scope-missing"),
        (403, "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "scope-missing"),
        (403, "insufficientFilePermissions", "connection-not-authorized"),
        (403, "appNotAuthorizedToFile", "connection-not-authorized"),
        (403, "forbidden", "connection-not-authorized"),
        (403, "accessNotConfigured", "connection-not-authorized"),
        (403, "", "connection-not-authorized"),
        (403, "fileNotDownloadable", "invalid-request"),
        (403, "exportSizeLimitExceeded", "invalid-request"),
        (400, "badRequest", "invalid-request"),
        (404, "notFound", "resource-not-found"),
        (405, "", "action-unsupported"),
        (501, "", "action-unsupported"),
    ],
)
def test_google_errors_preserve_the_recovery_action(status, reason, code):
    import json

    from googleapiclient.errors import HttpError
    from httplib2 import Response
    from lfx_google.components.google._workspace_client import normalize_google_error

    payload = {"error": {"message": "private-provider-payload", "errors": [{"reason": reason}]}}
    error = normalize_google_error(HttpError(Response({"status": str(status)}), json.dumps(payload).encode()))
    assert error.code == code
    assert error.http_status == status
    assert error.retryable is False
    assert "private-provider-payload" not in str(error)
    if code != "scope-missing":
        assert "reconnect" not in (error.hint or "").lower()
