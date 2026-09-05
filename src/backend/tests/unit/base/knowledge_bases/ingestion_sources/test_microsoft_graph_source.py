"""OneDrive and SharePoint ingestion through a Microsoft connection.

These sources resolve their credentials through the host's connection
resolver rather than through hand-managed refresh-token variables. An
ingestion job runs detached from the request that started it, so the
resolution is stamped with a non-interactive ``job_owner`` principal and
the portable deny floor refuses a connection that has not opted into
non-interactive use.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from lfx.base.knowledge_bases.ingestion_sources import (
    OneDriveSource,
    SharePointSource,
    SourceType,
    create_source,
    registered_sources,
)
from lfx.base.knowledge_bases.ingestion_sources import microsoft_graph as graph_module
from lfx.integrations.errors import ConnectionNotAuthorizedError, ScopeMissingError
from lfx.integrations.models import ResolvedCredential
from lfx.services.connection.base import BaseConnectionResolverService
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType
from pydantic import SecretStr

USER_ID = "11111111-1111-1111-1111-111111111111"
DOWNLOAD_URL = "https://contoso-my.sharepoint.com/personal/_layouts/15/download.aspx?SECRET=preauth"


class _Resolver(BaseConnectionResolverService):
    """Records resolution requests and returns a canned credential."""

    def __init__(self, credential: ResolvedCredential | None = None, error: Exception | None = None) -> None:
        super().__init__()
        self._credential = credential
        self._error = error
        self.requests: list[Any] = []
        self.set_ready()

    async def resolve(self, request):
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._credential


def _credential(scopes: set[str] | None = None) -> ResolvedCredential:
    return ResolvedCredential(
        access_token=SecretStr("graph-job-token"),
        granted_scopes=frozenset(scopes or {"Files.Read"}),
        scopes_verified=True,
        owner_kind="user",
        provider="microsoft",
        name="work",
    )


@pytest.fixture
def resolver():
    manager = get_service_manager()
    previous = manager.services.get(ServiceType.CONNECTION_RESOLVER_SERVICE)

    def _install(instance: _Resolver) -> _Resolver:
        manager.services[ServiceType.CONNECTION_RESOLVER_SERVICE] = instance
        return instance

    yield _install

    if previous is None:
        manager.services.pop(ServiceType.CONNECTION_RESOLVER_SERVICE, None)
    else:
        manager.services[ServiceType.CONNECTION_RESOLVER_SERVICE] = previous


@pytest.fixture
def graph_transport(monkeypatch):
    """Route the sources' httpx clients through a recording MockTransport."""
    requests: list[httpx.Request] = []

    def _install(handler) -> list[httpx.Request]:
        def _record(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return handler(request)

        transport = httpx.MockTransport(_record)
        original = graph_module.MicrosoftGraphSource._client

        def _client(self) -> httpx.AsyncClient:
            client = original(self)
            client._transport = transport
            return client

        monkeypatch.setattr(graph_module.MicrosoftGraphSource, "_client", _client)
        return requests

    return _install


def _children(entries: list[dict[str, Any]], next_link: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"value": entries}
    if next_link:
        payload["@odata.nextLink"] = next_link
    return payload


FILE_ENTRY = {
    "id": "01FILE",
    "name": "notes.txt",
    "size": 19,
    "webUrl": "https://contoso.sharepoint.com/Documents/notes.txt",
    "file": {"mimeType": "text/plain"},
    "lastModifiedDateTime": "2026-08-30T18:22:00Z",
    "parentReference": {"driveId": "b!drive", "id": "root"},
}
FOLDER_ENTRY = {"id": "01FOLDER", "name": "Archive", "folder": {"childCount": 1}}


class TestRegistration:
    def test_onedrive_and_sharepoint_are_registered(self) -> None:
        registered = registered_sources()
        assert SourceType.ONEDRIVE in registered
        assert SourceType.SHAREPOINT in registered

    def test_create_source_builds_a_connection_backed_source(self) -> None:
        source = create_source(
            SourceType.ONEDRIVE,
            user_id=USER_ID,
            source_config={"connection": "microsoft/work"},
        )
        assert isinstance(source, OneDriveSource)
        assert source.connection_handle() == "microsoft/work"
        assert source.connection_provider == "microsoft"

    def test_describe_publishes_the_handle_and_no_credential_variables(self) -> None:
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})
        described = source.describe()
        assert described["config"]["connection"] == "microsoft/work"
        assert described["config"]["required_scopes"] == ["Files.Read"]
        assert "refresh_token_variable" not in described["config"]


class TestConfiguration:
    def test_onedrive_defaults_to_the_signed_in_users_drive(self) -> None:
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})
        assert source.drive_root() == "/me/drive"
        assert source.required_connection_scopes() == ("Files.Read",)

    def test_an_explicit_drive_id_widens_the_required_scopes(self) -> None:
        source = OneDriveSource(
            user_id=USER_ID,
            source_config={"connection": "microsoft/work", "drive_id": "b!drive"},
        )
        assert source.drive_root() == "/drives/b!drive"
        assert source.required_connection_scopes() == ("Files.Read", "Files.Read.All")

    def test_sharepoint_addresses_a_site_library(self) -> None:
        source = SharePointSource(
            user_id=USER_ID,
            source_config={"connection": "microsoft/work", "site_id": "contoso,site"},
        )
        assert source.drive_root() == "/sites/contoso,site/drive"
        assert source.required_connection_scopes() == ("Files.Read", "Sites.Read.All")

    async def test_sharepoint_requires_a_site_or_drive_id(self) -> None:
        source = SharePointSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})
        with pytest.raises(ValueError, match="site_id"):
            await source.validate_config()

    async def test_a_handle_for_another_provider_is_rejected(self) -> None:
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "google/work"})
        with pytest.raises(ValueError, match="requires 'microsoft'"):
            await source.validate_config()

    def test_a_missing_handle_is_reported_before_resolution(self) -> None:
        source = OneDriveSource(user_id=USER_ID, source_config={})
        with pytest.raises(ValueError, match="requires a connection"):
            source.connection_lease()


class TestPrincipal:
    async def test_resolution_uses_a_non_interactive_job_owner_principal(self, resolver, graph_transport) -> None:
        recorder = resolver(_Resolver(_credential()))
        graph_transport(lambda _request: httpx.Response(200, json=_children([])))
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})

        assert [item async for item in source.list_items()] == []

        assert len(recorder.requests) == 1
        principal = recorder.requests[0].principal
        assert principal.kind == "job_owner"
        assert principal.interactive is False
        assert principal.user_id == USER_ID
        assert principal.family == "knowledge_base_ingestion"
        assert recorder.requests[0].required_scopes == frozenset({"Files.Read"})

    async def test_a_connection_without_non_interactive_use_is_refused(self, resolver, graph_transport) -> None:
        resolver(_Resolver(error=ConnectionNotAuthorizedError(provider="microsoft")))
        requests = graph_transport(lambda _request: httpx.Response(200, json=_children([])))
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})

        with pytest.raises(ConnectionNotAuthorizedError):
            _ = [item async for item in source.list_items()]
        assert requests == []

    async def test_a_missing_scope_is_refused_before_any_graph_call(self, resolver, graph_transport) -> None:
        resolver(_Resolver(error=ScopeMissingError(frozenset({"Sites.Read.All"}), provider="microsoft")))
        requests = graph_transport(lambda _request: httpx.Response(200, json=_children([])))
        source = SharePointSource(
            user_id=USER_ID,
            source_config={"connection": "microsoft/work", "site_id": "contoso,site"},
        )

        with pytest.raises(ScopeMissingError):
            _ = [item async for item in source.list_items()]
        assert requests == []


class TestWalk:
    async def test_list_items_yields_files_and_descends_into_folders(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        pages = {
            "/v1.0/me/drive/root/children": _children([FILE_ENTRY, FOLDER_ENTRY]),
            "/v1.0/me/drive/items/01FOLDER/children": _children(
                [{**FILE_ENTRY, "id": "01NESTED", "name": "nested.txt"}]
            ),
        }
        requests = graph_transport(lambda request: httpx.Response(200, json=pages[request.url.path]))
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})

        items = [item async for item in source.list_items()]

        assert [item.item_id for item in items] == ["01FILE", "01NESTED"]
        assert items[0].display_name == "notes.txt"
        assert items[0].mime_type == "text/plain"
        assert items[0].source_metadata["drive_id"] == "b!drive"
        assert requests[0].headers["authorization"] == "Bearer graph-job-token"
        assert requests[0].headers["user-agent"] == graph_module.USER_AGENT

    async def test_recursion_can_be_disabled(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        requests = graph_transport(lambda _request: httpx.Response(200, json=_children([FILE_ENTRY, FOLDER_ENTRY])))
        source = OneDriveSource(
            user_id=USER_ID,
            source_config={"connection": "microsoft/work", "recursive": False},
        )

        items = [item async for item in source.list_items()]

        assert [item.item_id for item in items] == ["01FILE"]
        assert len(requests) == 1

    async def test_a_folder_path_addresses_the_starting_point(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        requests = graph_transport(lambda _request: httpx.Response(200, json=_children([])))
        source = OneDriveSource(
            user_id=USER_ID,
            source_config={"connection": "microsoft/work", "folder_path": "/Reports/2026"},
        )

        _ = [item async for item in source.list_items()]

        assert requests[0].url.path == "/v1.0/me/drive/root:/Reports/2026:/children"

    async def test_paging_follows_the_next_link(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        next_link = "https://graph.microsoft.com/v1.0/me/drive/root/children?%24skiptoken=abc"
        pages = [
            _children([FILE_ENTRY], next_link=next_link),
            _children([{**FILE_ENTRY, "id": "01SECOND", "name": "second.txt"}]),
        ]
        graph_transport(lambda _request: httpx.Response(200, json=pages.pop(0)))
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})

        items = [item async for item in source.list_items()]

        assert [item.item_id for item in items] == ["01FILE", "01SECOND"]

    async def test_max_items_bounds_the_walk(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        graph_transport(
            lambda _request: httpx.Response(
                200,
                json=_children([FILE_ENTRY, {**FILE_ENTRY, "id": "01SECOND", "name": "second.txt"}]),
            )
        )
        source = OneDriveSource(
            user_id=USER_ID,
            source_config={"connection": "microsoft/work", "max_items": 1},
        )

        items = [item async for item in source.list_items()]

        assert [item.item_id for item in items] == ["01FILE"]

    async def test_a_graph_listing_failure_surfaces_as_an_oserror(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        graph_transport(lambda _request: httpx.Response(403, json={"error": {"code": "accessDenied"}}))
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})

        with pytest.raises(OSError, match="403"):
            _ = [item async for item in source.list_items()]


class TestFetch:
    async def test_fetch_follows_the_302_without_the_bearer_header(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))

        def _handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "graph.microsoft.com":
                return httpx.Response(302, headers={"Location": DOWNLOAD_URL})
            return httpx.Response(200, content=b"hello from onedrive")

        requests = graph_transport(_handler)
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})
        item = source._to_item(FILE_ENTRY)

        content = await source.fetch_content(item)

        assert content.raw_bytes == b"hello from onedrive"
        assert content.file_name == "notes.txt"
        assert requests[0].url.path == "/v1.0/me/drive/items/01FILE/content"
        assert "authorization" in requests[0].headers
        assert "authorization" not in requests[1].headers

    async def test_a_download_failure_surfaces_as_an_oserror(self, resolver, graph_transport) -> None:
        resolver(_Resolver(_credential()))
        graph_transport(lambda _request: httpx.Response(404, json={"error": {"code": "itemNotFound"}}))
        source = OneDriveSource(user_id=USER_ID, source_config={"connection": "microsoft/work"})

        with pytest.raises(OSError, match="404"):
            await source.fetch_content(source._to_item(FILE_ENTRY))
