"""Unit tests for the OAuth-based cloud connectors.

Covers ``GoogleDriveSource``, ``OneDriveSource``, and
``SharePointSource`` + the shared ``OAuthConnectorBase`` /
``MicrosoftGraphSource`` plumbing. All HTTP is mocked via
``httpx.MockTransport`` so the tests stay fast and offline.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from lfx.base.knowledge_bases.ingestion_sources import (
    GoogleDriveSource,
    OneDriveSource,
    SharePointSource,
    SourceType,
)


def _make_transport_and_recorder(routes: dict[str, Any]) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """Build a MockTransport that returns canned payloads by method+path match.

    ``routes`` keys are ``"GET https://host/path"`` style; value is
    either a dict (JSON body) or a tuple ``(status, body)`` — dict for
    200 JSON, tuple for explicit status/body control. Raw bytes go
    through as-is when the value is bytes.
    """
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        key = f"{request.method} {str(request.url).split('?')[0]}"
        if key not in routes:
            return httpx.Response(404, content=b"unrouted")
        value = routes[key]
        if isinstance(value, tuple):
            status, body = value
            if isinstance(body, (dict, list)):
                return httpx.Response(status, json=body)
            return httpx.Response(status, content=body)
        if isinstance(value, (dict, list)):
            return httpx.Response(200, json=value)
        if isinstance(value, bytes):
            return httpx.Response(200, content=value)
        return httpx.Response(200, content=str(value).encode())

    return httpx.MockTransport(handler), recorded


@pytest.fixture
def drive_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id-123")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret-abc")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "refresh-xyz")


@pytest.fixture
def ms_env(monkeypatch):
    monkeypatch.setenv("MICROSOFT_OAUTH_CLIENT_ID", "ms-client-id")
    monkeypatch.setenv("MICROSOFT_OAUTH_CLIENT_SECRET", "ms-client-secret")
    monkeypatch.setenv("MICROSOFT_OAUTH_REFRESH_TOKEN", "ms-refresh-token")
    monkeypatch.setenv("MICROSOFT_OAUTH_TENANT_ID", "common")


class TestGoogleDriveValidation:
    async def test_missing_refresh_token_raises(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "x")
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "y")
        monkeypatch.delenv("GOOGLE_OAUTH_REFRESH_TOKEN", raising=False)
        source = GoogleDriveSource(user_id=None, source_config={})
        with pytest.raises(ValueError, match="GOOGLE_OAUTH_REFRESH_TOKEN"):
            await source.validate_config()

    async def test_env_vars_satisfy(self, drive_env):  # noqa: ARG002
        source = GoogleDriveSource(user_id=None, source_config={})
        await source.validate_config()  # no raise

    async def test_bad_max_size_rejected(self, drive_env):  # noqa: ARG002
        source = GoogleDriveSource(user_id=None, source_config={"max_file_size_bytes": -1})
        with pytest.raises(ValueError, match="positive integer"):
            await source.validate_config()


class TestGoogleDriveListAndFetch:
    async def test_lists_and_respects_extension_filter(self, drive_env, monkeypatch):  # noqa: ARG002
        # Route table: token refresh + one files.list page + one
        # folder-scan page (empty) so recursion exits.
        transport, _ = _make_transport_and_recorder(
            {
                "POST https://oauth2.googleapis.com/token": {
                    "access_token": "tok-1",
                    "expires_in": 3600,
                },
                "GET https://www.googleapis.com/drive/v3/files": {
                    "files": [
                        {
                            "id": "a1",
                            "name": "alpha.pdf",
                            "mimeType": "application/pdf",
                            "size": "100",
                            "modifiedTime": "2026-04-01T00:00:00Z",
                            "webViewLink": "https://drive/a1",
                        },
                        {
                            "id": "b2",
                            "name": "beta.jpg",
                            "mimeType": "image/jpeg",
                            "size": "200",
                        },
                        {
                            "id": "c3",
                            "name": "Annual Report",
                            "mimeType": "application/vnd.google-apps.document",
                        },
                    ],
                },
            }
        )

        # Wire the MockTransport into every httpx.AsyncClient the
        # source opens — monkeypatching the constructor so we don't
        # need to reach into the source.
        original_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        source = GoogleDriveSource(
            user_id=None,
            source_config={"extensions": ["pdf", "docx"], "recursive": False},
        )
        items = [i async for i in source.list_items()]

        names = [item.display_name for item in items]
        # alpha.pdf kept (matches extension). beta.jpg filtered out.
        # Annual Report (Google Doc) kept because effective filename
        # becomes Annual Report.docx which matches the filter.
        assert "alpha.pdf" in names
        assert "Annual Report" in names
        assert "beta.jpg" not in names

    async def test_fetch_content_exports_google_doc_as_docx(self, drive_env, monkeypatch):  # noqa: ARG002
        transport, _ = _make_transport_and_recorder(
            {
                "POST https://oauth2.googleapis.com/token": {
                    "access_token": "tok-2",
                    "expires_in": 3600,
                },
                "GET https://www.googleapis.com/drive/v3/files/c3/export": b"FAKE_DOCX_BYTES",
            }
        )
        original_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **kw: original_init(self, *a, **{**kw, "transport": transport}),
        )

        source = GoogleDriveSource(user_id=None, source_config={})
        # Simulate an IngestionItem carrying the Google-native mime.
        from lfx.base.knowledge_bases.ingestion_sources.base import IngestionItem

        item = IngestionItem(
            item_id="c3",
            display_name="Annual Report",
            mime_type="application/vnd.google-apps.document",
            source_metadata={"mime_type": "application/vnd.google-apps.document"},
        )
        content = await source.fetch_content(item)
        assert content.raw_bytes == b"FAKE_DOCX_BYTES"
        # Export path tacks on the OOXML extension so the extractor dispatches correctly.
        assert content.file_name == "Annual Report.docx"

    async def test_token_cache_avoids_extra_refreshes(self, drive_env, monkeypatch):  # noqa: ARG002
        hits: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            key = f"{request.method} {str(request.url).split('?')[0]}"
            if key == "POST https://oauth2.googleapis.com/token":
                hits.append(1)
                return httpx.Response(200, json={"access_token": "tok-cached", "expires_in": 3600})
            if key == "GET https://www.googleapis.com/drive/v3/files":
                return httpx.Response(200, json={"files": []})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        original_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **kw: original_init(self, *a, **{**kw, "transport": transport}),
        )

        source = GoogleDriveSource(user_id=None, source_config={"recursive": False})
        # Two consecutive get_access_token calls should hit the
        # network exactly once.
        t1 = await source.get_access_token()
        t2 = await source.get_access_token()
        assert t1 == t2 == "tok-cached"
        assert len(hits) == 1


class TestOneDriveValidation:
    async def test_missing_tenant_falls_back_to_common(self, ms_env, monkeypatch):  # noqa: ARG002
        monkeypatch.delenv("MICROSOFT_OAUTH_TENANT_ID", raising=False)
        source = OneDriveSource(user_id=None, source_config={})
        # validate_config only checks the core triple; tenant is
        # resolved at refresh time with 'common' fallback.
        await source.validate_config()


class TestOneDriveList:
    async def test_walks_drive_with_extension_filter(self, ms_env, monkeypatch):  # noqa: ARG002
        transport, _ = _make_transport_and_recorder(
            {
                "POST https://login.microsoftonline.com/common/oauth2/v2.0/token": {
                    "access_token": "ms-tok",
                    "expires_in": 3600,
                },
                "GET https://graph.microsoft.com/v1.0/me/drive/root/children": {
                    "value": [
                        {
                            "id": "item1",
                            "name": "alpha.pdf",
                            "size": 50,
                            "file": {"mimeType": "application/pdf"},
                            "webUrl": "https://od/1",
                        },
                        {
                            "id": "item2",
                            "name": "ignore.jpg",
                            "size": 10,
                            "file": {"mimeType": "image/jpeg"},
                        },
                        {
                            "id": "subfolder",
                            "name": "Subfolder",
                            "folder": {"childCount": 0},
                        },
                    ],
                },
                # Recursive descent into Subfolder.
                "GET https://graph.microsoft.com/v1.0/me/drive/root:/Subfolder:/children": {
                    "value": [],
                },
            }
        )
        original_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **kw: original_init(self, *a, **{**kw, "transport": transport}),
        )

        source = OneDriveSource(user_id=None, source_config={"extensions": ["pdf"], "recursive": True})
        items = [i async for i in source.list_items()]
        names = [item.display_name for item in items]
        assert names == ["alpha.pdf"]  # jpg filtered + folder skipped


class TestSharePointValidation:
    async def test_missing_site_id_rejected(self, ms_env):  # noqa: ARG002
        source = SharePointSource(user_id=None, source_config={})
        with pytest.raises(ValueError, match="site_id"):
            await source.validate_config()

    async def test_happy_path_validation(self, ms_env):  # noqa: ARG002
        source = SharePointSource(
            user_id=None,
            source_config={"site_id": "contoso.sharepoint.com,111,222"},
        )
        await source.validate_config()  # no raise


class TestSharePointList:
    async def test_walks_site_default_drive(self, ms_env, monkeypatch):  # noqa: ARG002
        transport, _ = _make_transport_and_recorder(
            {
                "POST https://login.microsoftonline.com/common/oauth2/v2.0/token": {
                    "access_token": "sp-tok",
                    "expires_in": 3600,
                },
                "GET https://graph.microsoft.com/v1.0/sites/contoso.sharepoint.com%2C111%2C222/drive/root/children": {
                    "value": [
                        {
                            "id": "sp1",
                            "name": "policy.pdf",
                            "size": 200,
                            "file": {"mimeType": "application/pdf"},
                            "webUrl": "https://sp/sp1",
                        },
                    ],
                },
            }
        )
        original_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **kw: original_init(self, *a, **{**kw, "transport": transport}),
        )

        source = SharePointSource(
            user_id=None,
            source_config={"site_id": "contoso.sharepoint.com,111,222"},
        )
        items = [i async for i in source.list_items()]
        assert [i.display_name for i in items] == ["policy.pdf"]
        assert items[0].source_metadata["site_id"] == "contoso.sharepoint.com,111,222"


class TestDescribeRedaction:
    def test_gdrive_describe_exposes_only_variable_names(self, drive_env):  # noqa: ARG002
        source = GoogleDriveSource(
            user_id=None,
            source_config={
                "folder_id": "root123",
                "client_id_variable": "MY_GDRIVE_ID",
                "refresh_token_variable": "MY_GDRIVE_REFRESH",  # pragma: allowlist secret
            },
        )
        described = source.describe()
        assert described["source_type"] == SourceType.GOOGLE_DRIVE.value
        config = described["config"]
        assert config["client_id_variable"] == "MY_GDRIVE_ID"
        assert config["refresh_token_variable"] == "MY_GDRIVE_REFRESH"  # noqa: S105  # pragma: allowlist secret
        # No resolved secrets in the describe output.
        for value in config.values():
            if not isinstance(value, str):
                continue
            assert "refresh-xyz" not in value
            assert "client-secret" not in value

    def test_onedrive_describe_carries_tenant_variable(self, ms_env):  # noqa: ARG002
        source = OneDriveSource(
            user_id=None,
            source_config={"folder_path": "/Docs"},
        )
        described = source.describe()
        # Ensure the describe payload exposes both OAuth and OneDrive-
        # specific config fields.
        expected_keys = {
            "folder_path",
            "client_id_variable",
            "refresh_token_variable",
            "tenant_id_variable",
            "scope",
        }
        assert expected_keys.issubset(described["config"].keys())

    def test_sharepoint_describe_includes_site_and_drive(self, ms_env):  # noqa: ARG002
        source = SharePointSource(
            user_id=None,
            source_config={
                "site_id": "contoso.sharepoint.com,abc,def",
                "drive_id": "drive-1",
                "folder_path": "Shared Documents",
            },
        )
        described = source.describe()
        assert described["config"]["site_id"] == "contoso.sharepoint.com,abc,def"
        assert described["config"]["drive_id"] == "drive-1"

    def test_gdrive_describe_config_values_never_contain_secrets(self, drive_env):  # noqa: ARG002
        source = GoogleDriveSource(user_id=None, source_config={})
        described = source.describe()
        for value in described["config"].values():
            if not isinstance(value, str):
                continue
            assert "refresh-xyz" not in value
            assert "client-secret-abc" not in value


class TestTokenRefreshFailureSurfaces:
    async def test_bad_refresh_response_raises_value_error(self, drive_env, monkeypatch):  # noqa: ARG002
        transport, _ = _make_transport_and_recorder(
            {
                "POST https://oauth2.googleapis.com/token": (
                    400,
                    {"error": "invalid_grant"},
                ),
            }
        )
        original_init = httpx.AsyncClient.__init__
        monkeypatch.setattr(
            httpx.AsyncClient,
            "__init__",
            lambda self, *a, **kw: original_init(self, *a, **{**kw, "transport": transport}),
        )
        source = GoogleDriveSource(user_id=None, source_config={})
        with pytest.raises(ValueError, match="OAuth token refresh failed"):
            await source.get_access_token()


def _write_fixtures(tmp_path, data: dict) -> None:  # pragma: no cover — kept for potential fs-backed fixtures
    path = tmp_path / "fixtures.json"
    path.write_text(json.dumps(data))
