"""Regression coverage for connection reuse, bounded I/O and Graph continuations."""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from lfx.integrations.errors import AuthExpiredError, ProviderUnavailableError, ScopeMissingError
from lfx.utils import file_path_security
from lfx_microsoft import (
    OutlookCalendarListComponent,
    OutlookSearchComponent,
    OutlookSendComponent,
    SharePointListComponent,
)
from lfx_microsoft.components.microsoft import outlook_send
from lfx_microsoft.graph import GraphClient, drive_children_path, drive_item_path
from microsoft_testkit import RecordingResolver, TransportRecorder, build_component, credential, json_response
from test_graph_client import lease_for


@pytest.mark.parametrize(
    ("component_class", "method", "scope", "inputs"),
    [
        (OutlookSearchComponent, "search_messages", "Mail.Read", {}),
        (
            OutlookCalendarListComponent,
            "list_events",
            "Calendars.Read",
            {"start_time": "2026-09-01", "end_time": "2026-09-02"},
        ),
        (SharePointListComponent, "list_items", "Files.Read", {}),
    ],
)
async def test_listing_outputs_share_a_request_but_new_runs_resolve_again(
    resolver_factory, component_class, method, scope, inputs
):
    resolver_factory(credential("old", scopes={scope}))
    replies = [
        {"value": [{"id": "old"}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"},
        {"value": [{"id": "new"}]},
    ]
    recorder = TransportRecorder(lambda _: json_response(replies.pop(0)))
    component = build_component(component_class, recorder, connection="microsoft/work", top=1, **inputs)
    component._pre_run_setup()
    assert (await component.next_page_link()).text.endswith("/next")
    assert (await getattr(component, method)())[0].data["id"] == "old"
    assert len(recorder.requests) == 1

    resolver_factory(credential("new", scopes={scope}))
    component._pre_run_setup()
    assert (await getattr(component, method)())[0].data["id"] == "new"
    assert (await component.next_page_link()).text == ""
    assert [r.headers["authorization"] for r in recorder.requests] == ["Bearer old", "Bearer new"]


@pytest.mark.parametrize("blank", ["", " \t "])
async def test_blank_optional_drive_fields_do_not_require_elevated_scopes(resolver_factory, blank):
    resolver_factory(credential(scopes={"Files.Read"}))
    recorder = TransportRecorder(lambda _: json_response({"value": []}))
    component = build_component(
        SharePointListComponent, recorder, connection="microsoft/work", drive_id=blank, site_id=blank
    )
    await component.list_items()
    assert recorder.last.url.path == "/v1.0/me/drive/root/children"


async def test_unverified_scopes_fail_before_graph(resolver_factory):
    resolver_factory(credential(scopes={"Files.Read"}, scopes_verified=False))
    recorder = TransportRecorder(lambda _: json_response({"value": []}))
    component = build_component(SharePointListComponent, recorder, connection="microsoft/work")
    with pytest.raises(ScopeMissingError):
        await component.list_items()
    assert recorder.requests == []


@pytest.mark.parametrize("kind", ["outside", "other-user", "symlink", "allowed"])
async def test_outlook_attachments_obey_storage_containment(resolver_factory, tmp_path, monkeypatch, kind):
    resolver_factory(credential(scopes={"Mail.Send"}))
    storage = tmp_path / "storage"
    own = storage / "user-1"
    other = storage / "user-2"
    own.mkdir(parents=True)
    other.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    path = {
        "outside": outside,
        "other-user": other / "private.txt",
        "symlink": own / "link.txt",
        "allowed": own / "notes, final.txt",
    }[kind]
    if kind == "symlink":
        path.symlink_to(outside)
    else:
        path.write_text("hello")
    monkeypatch.setenv("LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS", "true")
    monkeypatch.setattr(
        file_path_security,
        "get_settings_service",
        lambda: SimpleNamespace(
            settings=SimpleNamespace(config_dir=storage, restrict_local_file_access=True, database_url="")
        ),
    )
    recorder = TransportRecorder(lambda _: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="File",
        body="Attached",
        attachments=[str(path)],
    )
    component._user_id = "user-1"
    if kind == "allowed":
        await component.send_mail()
        assert json.loads(recorder.last.content)["message"]["attachments"][0]["name"] == path.name
    else:
        with pytest.raises(file_path_security.LocalFileAccessError):
            await component.send_mail()
        assert recorder.requests == []


async def test_attachment_read_is_bounded_even_when_stat_understates_the_size(resolver_factory, tmp_path, monkeypatch):
    resolver_factory(credential(scopes={"Mail.Send"}))
    path = tmp_path / "growing.txt"
    path.touch()
    monkeypatch.setattr(outlook_send, "MAX_ATTACHMENT_BYTES", 4)
    reads = []

    class GrowingFile(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: GrowingFile(b"unbounded input"))
    recorder = TransportRecorder(lambda _: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="File",
        body="Attached",
        attachments=[str(path)],
    )
    with pytest.raises(ValueError, match="exceed"):
        await component.send_mail()
    assert reads == [5]
    assert recorder.requests == []


async def test_attachment_work_runs_off_the_event_loop(resolver_factory, monkeypatch):
    resolver_factory(credential(scopes={"Mail.Send"}))
    loop_thread = threading.get_ident()
    original = OutlookSendComponent._message

    def message(self):
        assert threading.get_ident() != loop_thread
        return original(self)

    monkeypatch.setattr(OutlookSendComponent, "_message", message)
    component = build_component(
        OutlookSendComponent,
        TransportRecorder(lambda _: httpx.Response(202)),
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="Hi",
        body="Hello",
    )
    await component.send_mail()


async def test_outlook_checks_the_encoded_message_size(resolver_factory, monkeypatch):
    resolver_factory(credential(scopes={"Mail.Send"}))
    monkeypatch.setattr(outlook_send, "MAX_MESSAGE_BYTES", 100)
    recorder = TransportRecorder(lambda _: httpx.Response(202))
    component = build_component(
        OutlookSendComponent, recorder, connection="microsoft/work", to="ada@contoso.com", subject="Hi", body="x" * 100
    )
    with pytest.raises(ValueError, match="message exceeds"):
        await component.send_mail()
    assert recorder.requests == []


@pytest.mark.parametrize(
    "next_link",
    [
        "https://example.com/steal",
        "http://graph.microsoft.com/v1.0/next",
        "https://graph.microsoft.com:444/v1.0/next",
        "https://user@graph.microsoft.com/v1.0/next",
    ],
)
async def test_pagination_never_sends_bearer_to_another_origin(next_link):
    recorder = TransportRecorder(lambda _: json_response({"value": [], "@odata.nextLink": next_link}))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.paginate("/me/messages")
    assert len(recorder.requests) == 1


async def test_a_continuation_preserves_the_whole_last_page():
    pages = [
        {"value": [{"id": 1}, {"id": 2}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/page2"},
        {"value": [{"id": 3}, {"id": 4}], "@odata.nextLink": "https://graph.microsoft.com/v1.0/page3"},
    ]
    recorder = TransportRecorder(lambda _: json_response(pages.pop(0)))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        items, next_link = await client.paginate("/me/messages", limit=3)
    assert [item["id"] for item in items] == [1, 2, 3, 4]
    assert next_link.endswith("/page3")


@pytest.mark.parametrize("status", [200, 500])
async def test_direct_downloads_and_error_bodies_are_bounded(status):
    served = []

    async def chunks():
        for index in range(1000):
            served.append(index)
            yield b"x" * 1024

    recorder = TransportRecorder(lambda _: httpx.Response(status, content=chunks()))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        if status == 200:
            assert await client.download("/me/drive/items/id/content", max_bytes=2048) == b"x" * 2048
            assert len(served) == 2
        else:
            with pytest.raises(ProviderUnavailableError):
                await client.download("/me/drive/items/id/content", max_bytes=2048)
            assert len(served) <= 64


@pytest.mark.parametrize("persistent", [False, True])
async def test_streaming_download_reauthorizes_once(persistent):
    resolver = RecordingResolver([credential("old"), credential("new")])
    replies = [httpx.Response(401), httpx.Response(401 if persistent else 200, content=b"ok")]
    recorder = TransportRecorder(lambda _: replies.pop(0))
    async with GraphClient(lease_for(resolver), transport=recorder.transport) as client:
        if persistent:
            with pytest.raises(AuthExpiredError):
                await client.download("/me/drive/items/id/content")
        else:
            assert await client.download("/me/drive/items/id/content") == b"ok"
    assert [r.headers["authorization"] for r in recorder.requests] == ["Bearer old", "Bearer new"]
    assert resolver.calls == 2


@pytest.mark.parametrize(
    "target", ["http://example.com/file", "https://127.0.0.1/file", "https://user@example.com/file"]
)
async def test_every_download_redirect_is_checked(target, monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    replies = [
        httpx.Response(302, headers={"Location": "https://contoso-my.sharepoint.com/file"}),
        httpx.Response(302, headers={"Location": target}),
    ]
    recorder = TransportRecorder(lambda _: replies.pop(0))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.download("/me/drive/items/id/content")
    assert len(recorder.requests) == 2


async def test_anonymous_hops_drop_caller_credentials_and_cookies():
    replies = [
        httpx.Response(
            302,
            headers={
                "Location": "https://contoso-my.sharepoint.com/file",
                "Set-Cookie": "graph=secret; Domain=.sharepoint.com",
            },
        ),
        httpx.Response(302, headers={"Location": "/second", "Set-Cookie": "download=secret"}),
        httpx.Response(200, content=b"ok"),
    ]
    recorder = TransportRecorder(lambda _: replies.pop(0))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        assert (
            await client.download(
                "/me/drive/items/id/content",
                headers={
                    "Authorization": "secret",
                    "Cookie": "secret",
                    "Proxy-Authorization": "secret",
                    "Range": "bytes=0-1",
                },
            )
            == b"ok"
        )
    for request in recorder.requests[1:]:
        assert not any(name in request.headers for name in ["Authorization", "Cookie", "Proxy-Authorization"])
        assert request.headers["Range"] == "bytes=0-1"


async def test_redirects_are_not_successful_json_actions():
    recorder = TransportRecorder(lambda _: httpx.Response(302, headers={"Location": "https://example.com"}))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.get_json("/me/messages")
    assert len(recorder.requests) == 1


def test_drive_paths_encode_reserved_characters_without_changing_folder_separators():
    assert drive_item_path("/me/drive", path="Reports/a#b?100%.txt") == "/me/drive/root:/Reports/a%23b%3F100%25.txt:"
    assert drive_children_path("/me/drive", path="a#b/c?d") == "/me/drive/root:/a%23b/c%3Fd:/children"


@pytest.mark.parametrize(
    ("component_class", "method", "scope"),
    [
        (OutlookSearchComponent, "search_messages", "Mail.Read"),
        (OutlookCalendarListComponent, "list_events", "Calendars.Read"),
        (SharePointListComponent, "list_items", "Files.Read"),
    ],
)
async def test_negative_result_budgets_fail_before_graph(resolver_factory, component_class, method, scope):
    resolver_factory(credential(scopes={scope}))
    recorder = TransportRecorder(lambda _: json_response({"value": []}))
    component = build_component(component_class, recorder, connection="microsoft/work", top=-1)
    with pytest.raises(ValueError, match="Result Budget"):
        await getattr(component, method)()
    assert recorder.requests == []


async def test_outlook_rejects_combined_search_and_filter(resolver_factory):
    resolver_factory(credential(scopes={"Mail.Read"}))
    recorder = TransportRecorder(lambda _: json_response({"value": []}))
    component = build_component(
        OutlookSearchComponent, recorder, connection="microsoft/work", search="budget", filter="isRead eq false"
    )
    with pytest.raises(ValueError, match="either Search or Filter"):
        await component.search_messages()
    assert recorder.requests == []


@pytest.mark.parametrize(("content", "truncated"), [(b"123", False), (b"1234", False), (b"12345", True)])
async def test_truncation_requires_an_actual_discarded_byte(resolver_factory, content, truncated):
    from lfx_microsoft import SharePointFetchComponent

    resolver_factory(credential(scopes={"Files.Read"}))
    replies = [json_response({"id": "file"}), httpx.Response(200, content=content)]
    recorder = TransportRecorder(lambda _: replies.pop(0))
    component = build_component(
        SharePointFetchComponent, recorder, connection="microsoft/work", item_id="file", max_bytes=4
    )
    result = await component.fetch_item()
    assert result.data["truncated"] is truncated
    assert result.data["text"] == content[:4].decode()


async def test_component_downloads_have_a_finite_ceiling(resolver_factory, monkeypatch):
    from lfx_microsoft import SharePointFetchComponent
    from lfx_microsoft.components.microsoft import sharepoint_fetch

    monkeypatch.setattr(sharepoint_fetch, "MAX_DOWNLOAD_BYTES", 4)
    resolver_factory(credential(scopes={"Files.Read"}))
    replies = [json_response({"id": "file"}), httpx.Response(200, content=b"123456789")]
    recorder = TransportRecorder(lambda _: replies.pop(0))
    component = build_component(
        SharePointFetchComponent, recorder, connection="microsoft/work", item_id="file", max_bytes=10**12
    )
    result = await component.fetch_item()
    assert result.data["content_bytes"] == 4
    assert result.data["truncated"] is True


async def test_pagination_rejects_a_cycle_without_files():
    recorder = TransportRecorder(
        lambda _: json_response({"value": [], "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages"})
    )
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.paginate("/me/messages")
    assert len(recorder.requests) == 1


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("insufficient_scope", ScopeMissingError),
        ("accessDenied", "provider"),
        ("insufficient_claims", "provider"),
    ],
)
async def test_graph_denials_distinguish_explicit_missing_scopes_from_other_permissions(code, expected):
    from lfx.integrations.errors import ConnectionNotAuthorizedError

    recorder = TransportRecorder(lambda _: httpx.Response(403, json={"error": {"code": code}}))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(ConnectionNotAuthorizedError if expected == "provider" else expected):
            await client.get_json("/me/messages")


async def test_download_does_not_treat_no_content_as_a_file():
    recorder = TransportRecorder(lambda _: httpx.Response(204))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        with pytest.raises(ProviderUnavailableError):
            await client.download("/me/drive/items/id/content")


async def test_download_urls_are_hidden_without_suppressing_other_tasks(caplog):
    import asyncio
    import logging

    from lfx.utils.url_redaction import suppress_sensitive_http_logs

    caplog.set_level(logging.DEBUG)
    inside = asyncio.Event()
    outside = asyncio.Event()

    async def sensitive():
        async with suppress_sensitive_http_logs():
            inside.set()
            await outside.wait()
            logging.getLogger("httpx").info("signed URL must stay private")
            logging.getLogger("httpcore.http11").debug("signed Location must stay private")

    async def ordinary():
        await inside.wait()
        logging.getLogger("httpx").info("ordinary request")
        outside.set()

    await asyncio.gather(sensitive(), ordinary())
    assert "ordinary request" in caplog.text
    assert "must stay private" not in caplog.text

    replies = [
        httpx.Response(302, headers={"Location": "https://contoso-my.sharepoint.com/file?SECRET=signed"}),
        httpx.Response(200, content=b"ok"),
    ]
    recorder = TransportRecorder(lambda _: replies.pop(0))
    async with GraphClient(lease_for(RecordingResolver([credential()])), transport=recorder.transport) as client:
        assert await client.download("/me/drive/items/id/content") == b"ok"
    assert "signed" not in caplog.text
