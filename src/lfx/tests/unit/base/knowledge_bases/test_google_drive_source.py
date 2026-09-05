"""Google Drive knowledge-base ingestion source (INT-10).

Two properties carry the risk here and both are tested rather than assumed:

* **Identity.** Ingestion is a background job, so the source resolves under a
  non-interactive ``job_owner`` principal. The portable deny floor refuses a
  user-owned connection for such a principal unless the connection opted into
  ``allow_non_interactive``, and the source must surface that as the typed
  ``connection-not-authorized`` error rather than swallowing it.
* **Reach.** The source asks for ``drive.file`` and nothing else, and an empty
  listing under that scope is a normal outcome, not a failure.

HTTP is driven through ``httpx.MockTransport`` so nothing leaves the process.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest
from lfx.base.knowledge_bases.ingestion_sources import (
    GOOGLE_DRIVE_ENABLED_ENV_VAR,
    GoogleDriveSource,
    google_drive_source_enabled,
    registered_sources,
)
from lfx.base.knowledge_bases.ingestion_sources.base import SourceType
from lfx.base.knowledge_bases.ingestion_sources.google_drive import DRIVE_FILE_SCOPE
from lfx.integrations.errors import ConnectionNotAuthorizedError, ScopeMissingError
from lfx.integrations.models import ResolvedCredential
from lfx.services.connection.base import BaseConnectionResolverService
from pydantic import SecretStr

USER_ID = uuid4()
FAKE_TOKEN = "fake-drive-access-token"  # noqa: S105  # pragma: allowlist secret

BINARY_FILE = {
    "id": "drive-file-notes",
    "name": "notes.txt",
    "mimeType": "text/plain",
    "size": "9",
    "modifiedTime": "2026-08-30T09:14:02.113Z",
    "webViewLink": "https://drive.google.com/file/d/drive-file-notes/view",
}
NATIVE_DOC = {
    "id": "drive-doc-meeting-notes",
    "name": "Meeting notes",
    "mimeType": "application/vnd.google-apps.document",
    "modifiedTime": "2026-09-01T16:42:55.008Z",
}
FOLDER = {
    "id": "drive-folder-reports",
    "name": "Reports",
    "mimeType": "application/vnd.google-apps.folder",
}


class RecordingResolver(BaseConnectionResolverService):
    """Applies the real deny floor, then hands back a canned credential."""

    def __init__(self, *, allow_non_interactive: bool = True, owner_id: str | None = None) -> None:
        super().__init__()
        self.requests: list = []
        self.allow_non_interactive = allow_non_interactive
        self.owner_id = owner_id if owner_id is not None else str(USER_ID)
        self.set_ready()

    async def resolve(self, request):
        self.requests.append(request)
        denial = self.authorize_principal(
            request,
            connection_owner_id=self.owner_id,
            owner_kind="user",
            allow_non_interactive=self.allow_non_interactive,
        )
        if denial is not None:
            raise denial
        missing = request.required_scopes - {DRIVE_FILE_SCOPE}
        if missing:
            raise ScopeMissingError(frozenset(missing), provider="google")
        return ResolvedCredential(
            access_token=SecretStr(FAKE_TOKEN),
            granted_scopes=frozenset({DRIVE_FILE_SCOPE}),
            scopes_verified=True,
            owner_kind="user",
            provider="google",
            name="work",
        )


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> RecordingResolver:
    instance = RecordingResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: instance)
    return instance


def _transport(responses: list[httpx.Response]) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return remaining.pop(0)

    return httpx.MockTransport(handler), seen


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch):
    """Route every AsyncClient the source opens through a canned transport."""

    def install(responses: list[httpx.Response]) -> list[httpx.Request]:
        transport, seen = _transport(responses)
        original = httpx.AsyncClient.__init__

        def patched(self, *args, **kwargs):
            kwargs["transport"] = transport
            original(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)
        return seen

    return install


def _source(**config) -> GoogleDriveSource:
    return GoogleDriveSource(user_id=USER_ID, source_config={"connection": "google/work", **config})


def _json(payload: dict) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(payload), headers={"content-type": "application/json"})


# -- registration -----------------------------------------------------------


def test_source_is_not_registered_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """It stays out of the connector picker until INT-6 stamps a job principal."""
    monkeypatch.delenv(GOOGLE_DRIVE_ENABLED_ENV_VAR, raising=False)

    assert google_drive_source_enabled() is False
    assert SourceType.GOOGLE_DRIVE not in registered_sources()


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on"])
def test_the_opt_in_switch_accepts_the_usual_truthy_spellings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(GOOGLE_DRIVE_ENABLED_ENV_VAR, value)

    assert google_drive_source_enabled() is True


def test_the_opt_in_switch_rejects_other_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(GOOGLE_DRIVE_ENABLED_ENV_VAR, "maybe")

    assert google_drive_source_enabled() is False


# -- identity ---------------------------------------------------------------


async def test_resolution_uses_a_non_interactive_job_owner_principal(resolver) -> None:
    source = _source()

    await source._token()

    principal = resolver.requests[0].principal
    assert principal.kind == "job_owner"
    assert principal.user_id == str(USER_ID)
    assert principal.interactive is False


async def test_resolution_requests_only_the_drive_file_scope(resolver) -> None:
    source = _source()

    await source._token()

    assert resolver.requests[0].required_scopes == frozenset({DRIVE_FILE_SCOPE})


async def test_a_connection_without_non_interactive_consent_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user has to opt in before a background job may act on their behalf."""
    strict = RecordingResolver(allow_non_interactive=False)
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: strict)
    source = _source()

    with pytest.raises(ConnectionNotAuthorizedError):
        await source.validate_config()


async def test_another_users_connection_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    other = RecordingResolver(owner_id=str(uuid4()))
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: other)
    source = _source()

    with pytest.raises(ConnectionNotAuthorizedError):
        await source.validate_config()


async def test_a_host_without_a_resolver_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: None)
    source = _source()

    with pytest.raises(ConnectionNotAuthorizedError):
        await source.validate_config()


# -- configuration ----------------------------------------------------------


async def test_a_missing_connection_handle_is_rejected() -> None:
    source = GoogleDriveSource(user_id=USER_ID, source_config={})

    with pytest.raises(ValueError, match="requires a managed Google connection"):
        await source.validate_config()


@pytest.mark.usefixtures("resolver")
async def test_an_out_of_range_page_size_is_rejected() -> None:
    source = _source(page_size=5000)

    with pytest.raises(ValueError, match="page_size must be between"):
        await source.validate_config()


# -- listing and fetching ---------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_listing_sends_a_scoped_query_and_bearer_token(mock_http) -> None:
    seen = mock_http([_json({"files": [BINARY_FILE]})])
    source = _source(folder_id="drive-folder-reports")

    items = [item async for item in source.list_items()]

    assert [item.item_id for item in items] == ["drive-file-notes"]
    request = seen[0]
    assert request.headers["authorization"] == f"Bearer {FAKE_TOKEN}"
    assert "trashed = false" in request.url.params["q"]
    assert "'drive-folder-reports' in parents" in request.url.params["q"]


@pytest.mark.usefixtures("resolver")
async def test_listing_follows_pagination(mock_http) -> None:
    seen = mock_http(
        [
            _json({"files": [BINARY_FILE], "nextPageToken": "page-token-2"}),
            _json({"files": [dict(BINARY_FILE, id="drive-file-second", name="second.txt")]}),
        ]
    )
    source = _source()

    items = [item async for item in source.list_items()]

    assert [item.item_id for item in items] == ["drive-file-notes", "drive-file-second"]
    assert seen[1].url.params["pageToken"] == "page-token-2"


@pytest.mark.usefixtures("resolver")
async def test_listing_skips_google_native_types_with_no_useful_export(mock_http) -> None:
    mock_http([_json({"files": [FOLDER, NATIVE_DOC, BINARY_FILE]})])
    source = _source()

    items = [item async for item in source.list_items()]

    assert [item.item_id for item in items] == ["drive-doc-meeting-notes", "drive-file-notes"]


@pytest.mark.usefixtures("resolver")
async def test_an_empty_listing_is_not_an_error(mock_http) -> None:
    """Under drive.file, "no files" is the expected state of a fresh connection."""
    mock_http([_json({"files": []})])
    source = _source()

    assert [item async for item in source.list_items()] == []


@pytest.mark.usefixtures("resolver")
async def test_fetching_a_binary_file_downloads_media(mock_http) -> None:
    seen = mock_http(
        [
            _json({"files": [BINARY_FILE]}),
            httpx.Response(200, content=b"file body"),
        ]
    )
    source = _source()
    items = [item async for item in source.list_items()]

    content = await source.fetch_content(items[0])

    assert content.raw_bytes == b"file body"
    assert content.file_name == "notes.txt"
    assert seen[1].url.params["alt"] == "media"


@pytest.mark.usefixtures("resolver")
async def test_fetching_a_google_doc_exports_it_with_a_usable_extension(mock_http) -> None:
    seen = mock_http(
        [
            _json({"files": [NATIVE_DOC]}),
            httpx.Response(200, content=b"Meeting notes body"),
        ]
    )
    source = _source()
    items = [item async for item in source.list_items()]

    content = await source.fetch_content(items[0])

    assert content.raw_bytes == b"Meeting notes body"
    # Text extraction dispatches on the extension, and a Google Doc has none.
    assert content.file_name == "Meeting notes.txt"
    assert seen[1].url.path.endswith("/export")
    assert seen[1].url.params["mimeType"] == "text/plain"


@pytest.mark.usefixtures("resolver")
async def test_a_provider_error_surfaces_as_a_typed_integration_error(mock_http) -> None:
    mock_http([httpx.Response(403, json={"error": {"code": 403, "message": "Insufficient Permission"}})])
    source = _source()

    with pytest.raises(ScopeMissingError):
        _ = [item async for item in source.list_items()]


# -- describe ---------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
def test_describe_reports_the_scope_and_leaks_no_credential() -> None:
    source = _source()

    described = source.describe()

    assert described["scope"] == DRIVE_FILE_SCOPE
    assert described["uses_managed_connection"] is True
    # The handle is a non-secret reference; no token ever reaches describe().
    assert described["config"]["connection"] == "google/work"
    assert FAKE_TOKEN not in json.dumps(described)
