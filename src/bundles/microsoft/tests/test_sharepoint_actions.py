"""Recorded-fixture contract tests for the OneDrive/SharePoint actions."""

from __future__ import annotations

import base64

import httpx
import pytest
from lfx.integrations.errors import ScopeMissingError
from lfx_microsoft import SharePointFetchComponent, SharePointListComponent
from microsoft_testkit import TransportRecorder, build_component, credential, graph_fixture, json_response

DOWNLOAD_URL = "https://contoso-my.sharepoint.com/personal/_layouts/15/download.aspx?SECRET=preauth"


def _drive_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host != "graph.microsoft.com":
        return httpx.Response(200, content=b"hello from onedrive")
    if request.url.path.endswith("/content"):
        return httpx.Response(302, headers={"Location": DOWNLOAD_URL})
    return json_response(graph_fixture("drive_item"))


async def test_list_items_defaults_to_the_users_onedrive_root(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("drive_children")))
    component = build_component(SharePointListComponent, recorder, connection="microsoft/work", top=10)

    rows = await component.list_items()

    assert recorder.last.url.path == "/v1.0/me/drive/root/children"
    assert [row.data["name"] for row in rows] == ["Quarterly plan.docx", "Archive"]


async def test_list_items_uses_the_drive_and_item_scope(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read", "Files.Read.All"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("drive_children")))
    component = build_component(
        SharePointListComponent,
        recorder,
        connection="microsoft/work",
        drive_id="b!drive",
        item_id="root-item",
        order_by="name asc",
    )

    await component.list_items()

    assert recorder.last.url.path == "/v1.0/drives/b!drive/items/root-item/children"
    assert recorder.last.url.params["$orderby"] == "name asc"


async def test_list_items_uses_the_site_drive_and_path(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read", "Sites.Read.All"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("drive_children")))
    component = build_component(
        SharePointListComponent,
        recorder,
        connection="microsoft/work",
        site_id="contoso.sharepoint.com,site",
        path="/Reports/2026",
    )

    await component.list_items()

    assert recorder.last.url.path == "/v1.0/sites/contoso.sharepoint.com,site/drive/root:/Reports/2026:/children"


async def test_a_drive_id_activates_the_conditional_files_read_all_scope(resolver_factory) -> None:
    """``resolve_connection`` cannot see conditional scopes, so we pre-flight."""
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("drive_children")))
    component = build_component(
        SharePointListComponent,
        recorder,
        connection="microsoft/work",
        drive_id="b!drive",
    )

    with pytest.raises(ScopeMissingError) as excinfo:
        await component.list_items()
    assert excinfo.value.missing == frozenset({"Files.Read.All"})
    assert recorder.requests == []


async def test_a_site_id_activates_the_conditional_sites_read_all_scope(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("drive_children")))
    component = build_component(
        SharePointFetchComponent,
        recorder,
        connection="microsoft/work",
        site_id="contoso.sharepoint.com,site",
        item_id="item-1",
    )

    with pytest.raises(ScopeMissingError) as excinfo:
        await component.fetch_item()
    assert excinfo.value.missing == frozenset({"Sites.Read.All"})
    assert recorder.requests == []


async def test_fetch_item_returns_metadata_and_content_without_the_download_url(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(_drive_handler)
    component = build_component(
        SharePointFetchComponent,
        recorder,
        connection="microsoft/work",
        item_id="01BYE5RZ6QN3ZWBTUFOFD3GSPGOHDJD36K",
    )

    result = await component.fetch_item()

    paths = [request.url.path for request in recorder.requests[:2]]
    assert paths == [
        "/v1.0/me/drive/items/01BYE5RZ6QN3ZWBTUFOFD3GSPGOHDJD36K",
        "/v1.0/me/drive/items/01BYE5RZ6QN3ZWBTUFOFD3GSPGOHDJD36K/content",
    ]
    assert result.data["name"] == "notes.txt"
    assert result.data["text"] == "hello from onedrive"
    assert base64.b64decode(result.data["content_base64"]) == b"hello from onedrive"
    assert result.data["truncated"] is False
    # The preauthenticated download URL is a credential; it must not survive.
    serialized = repr(result.data)
    assert "downloadUrl" not in serialized
    assert "SECRET" not in serialized


async def test_fetch_item_addresses_an_item_by_path(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(_drive_handler)
    component = build_component(
        SharePointFetchComponent,
        recorder,
        connection="microsoft/work",
        path="Documents/notes.txt",
    )

    await component.fetch_item()

    assert recorder.requests[0].url.path == "/v1.0/me/drive/root:/Documents/notes.txt:"
    assert recorder.requests[1].url.path == "/v1.0/me/drive/root:/Documents/notes.txt:/content"


async def test_fetch_item_requires_an_item_id_or_a_path(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(_drive_handler)
    component = build_component(SharePointFetchComponent, recorder, connection="microsoft/work")

    with pytest.raises(ValueError, match="item id or a path"):
        await component.fetch_item()


async def test_fetch_item_truncates_at_max_bytes(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(_drive_handler)
    component = build_component(
        SharePointFetchComponent,
        recorder,
        connection="microsoft/work",
        item_id="item-1",
        max_bytes=5,
    )

    result = await component.fetch_item()

    assert result.data["content_bytes"] == 5
    assert result.data["truncated"] is True
    assert result.data["text"] == "hello"


async def test_fetch_item_forwards_a_byte_range(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(_drive_handler)
    component = build_component(
        SharePointFetchComponent,
        recorder,
        connection="microsoft/work",
        item_id="item-1",
        range="bytes=0-4",
    )

    await component.fetch_item()

    assert recorder.requests[1].headers["range"] == "bytes=0-4"
