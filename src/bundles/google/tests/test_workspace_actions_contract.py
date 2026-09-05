"""Contract tests for the five wave-1 Google Workspace actions.

Each action is driven end to end — component inputs in, Google request out,
recorded response in, Langflow ``Data`` out — with no network and no
credentials. What is pinned here is the part a Google SDK upgrade or a component
refactor could silently change: the request Google actually receives, the shape
of the returned data, and the mapping from provider failures onto the sanitized
error vocabulary.
"""

from __future__ import annotations

import base64
import email
import json
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import FAKE_ACCESS_TOKEN, FAKE_REFRESHED_TOKEN, json_response, load_fixture, media_response, wire
from lfx.integrations import AuthExpiredError, ProviderUnavailableError, RateLimitedError, ScopeMissingError
from lfx_google.components.google import (
    GmailSendComponent,
    GoogleCalendarCreateComponent,
    GoogleCalendarListComponent,
    GoogleDriveFetchComponent,
    GoogleDriveListComponent,
)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"
CALENDAR_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def query_of(uri: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(uri).query)


def _authorization(recorded_request) -> str:
    """Return the Authorization header of one recorded httplib2 request."""
    headers = recorded_request[3] or {}
    for key, value in headers.items():
        if key.lower() == "authorization":
            return value
    return ""


def gmail_send_component(**overrides):
    defaults = {
        "to": ["recipient@example.com"],
        "cc": [],
        "bcc": [],
        "subject": "Quarterly report",
        "body": "Attached below.",
        "body_is_html": False,
        "attachments": [],
        "thread_id": "",
    }
    defaults.update(overrides)
    return GmailSendComponent(**defaults)


def drive_list_component(**overrides):
    defaults = {
        "query": "",
        "page_size": 100,
        "page_token": "",
        "order_by": "",
        "include_shared_drives": False,
        "fields": "",
    }
    defaults.update(overrides)
    return GoogleDriveListComponent(**defaults)


def drive_fetch_component(**overrides):
    defaults = {
        "file_id": "drive-file-quarterly-report",
        "export_mime_type": "",
        "acknowledge_abuse": False,
        "supports_all_drives": False,
    }
    defaults.update(overrides)
    return GoogleDriveFetchComponent(**defaults)


def calendar_list_component(**overrides):
    defaults = {
        "calendar_id": "primary",
        "time_min": "",
        "time_max": "",
        "query": "",
        "max_results": 250,
        "single_events": True,
        "order_by": "startTime",
        "page_token": "",
    }
    defaults.update(overrides)
    return GoogleCalendarListComponent(**defaults)


def calendar_create_component(**overrides):
    defaults = {
        "calendar_id": "primary",
        "summary": "Langflow sync",
        "start_time": "2026-09-10T14:00:00Z",
        "end_time": "2026-09-10T15:00:00Z",
        "description": "",
        "location": "",
        "attendees": [],
        "send_updates": "none",
        "recurrence": [],
        "conference_data_version": 0,
    }
    defaults.update(overrides)
    return GoogleCalendarCreateComponent(**defaults)


# --------------------------------------------------------------------------
# Gmail: Send Email
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_gmail_send_posts_a_base64url_rfc2822_message() -> None:
    component = gmail_send_component(
        to=["one@example.com", "two@example.com"],
        cc=["cc@example.com"],
        subject="Quarterly report",
        body="Numbers attached.",
        thread_id="thread-0001",
    )
    http = wire(component, [json_response("gmail_send_response")])

    result = await component.send_message()

    uri, method, body, _headers = http.request_sequence[0]
    assert method == "POST"
    assert uri.startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages/send")
    payload = json.loads(body)
    assert payload["threadId"] == "thread-0001"
    message = email.message_from_bytes(base64.urlsafe_b64decode(payload["raw"]))
    assert message["To"] == "one@example.com, two@example.com"
    assert message["Cc"] == "cc@example.com"
    assert message["Subject"] == "Quarterly report"
    assert result.data == load_fixture("gmail_send_response")


async def test_gmail_send_requests_only_the_send_scope(resolver) -> None:
    component = gmail_send_component()
    wire(component, [json_response("gmail_send_response")])

    await component.send_message()

    assert resolver.requests[0].required_scopes == frozenset({GMAIL_SEND_SCOPE})
    assert resolver.requests[0].ref.to_handle() == "google/work"


@pytest.mark.usefixtures("resolver")
async def test_gmail_send_html_body_is_multipart_alternative() -> None:
    component = gmail_send_component(body="<p>Hi</p>", body_is_html=True)
    http = wire(component, [json_response("gmail_send_response")])

    await component.send_message()

    payload = json.loads(http.request_sequence[0][2])
    message = email.message_from_bytes(base64.urlsafe_b64decode(payload["raw"]))
    assert message.is_multipart()
    subtypes = {part.get_content_subtype() for part in message.walk() if not part.is_multipart()}
    assert "html" in subtypes


@pytest.mark.usefixtures("resolver")
async def test_gmail_send_with_attachments_uses_the_upload_endpoint(tmp_path) -> None:
    attachment = tmp_path / "report.txt"
    attachment.write_text("quarterly numbers", encoding="utf-8")
    component = gmail_send_component(attachments=[str(attachment)])
    http = wire(component, [json_response("gmail_send_response")])

    await component.send_message()

    uri, method, _body, _headers = http.request_sequence[0]
    assert method == "POST"
    assert "/upload/" in uri
    assert query_of(uri)["uploadType"] == ["multipart"]


@pytest.mark.usefixtures("resolver")
async def test_gmail_send_rejects_an_empty_recipient_list() -> None:
    component = gmail_send_component(to=[])
    wire(component, [json_response("gmail_send_response")])

    with pytest.raises(ValueError, match="At least one recipient"):
        await component.send_message()


# --------------------------------------------------------------------------
# Drive: List Files
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_drive_list_sends_the_declared_query_parameters() -> None:
    component = drive_list_component(
        query="name contains 'report'",
        page_size=25,
        page_token="PAGE-2",  # noqa: S106 - a Drive paging cursor, not a credential
        order_by="modifiedTime desc",
        include_shared_drives=True,
    )
    http = wire(component, [json_response("drive_list_response")])

    await component.list_page()

    uri, method, _body, _headers = http.request_sequence[0]
    assert method == "GET"
    params = query_of(uri)
    assert params["q"] == ["name contains 'report'"]
    assert params["pageSize"] == ["25"]
    assert params["pageToken"] == ["PAGE-2"]
    assert params["orderBy"] == ["modifiedTime desc"]
    assert params["includeItemsFromAllDrives"] == ["true"]
    assert params["supportsAllDrives"] == ["true"]


@pytest.mark.usefixtures("resolver")
async def test_drive_list_omits_shared_drive_flags_by_default() -> None:
    component = drive_list_component()
    http = wire(component, [json_response("drive_list_response")])

    await component.list_page()

    params = query_of(http.request_sequence[0][0])
    assert "includeItemsFromAllDrives" not in params
    assert "supportsAllDrives" not in params


@pytest.mark.usefixtures("resolver")
async def test_drive_list_returns_files_and_paging_metadata() -> None:
    component = drive_list_component()
    wire(component, [json_response("drive_list_response")])
    expected = load_fixture("drive_list_response")

    result = await component.list_page()

    assert result.data["files"] == expected["files"]
    assert result.data["next_page_token"] == expected["nextPageToken"]
    assert result.data["incomplete_search"] is False


@pytest.mark.usefixtures("resolver")
async def test_drive_list_dataframe_has_one_row_per_file() -> None:
    component = drive_list_component()
    wire(component, [json_response("drive_list_response")])

    frame = await component.list_files()

    assert len(frame) == len(load_fixture("drive_list_response")["files"])
    assert list(frame["id"]) == [entry["id"] for entry in load_fixture("drive_list_response")["files"]]


@pytest.mark.usefixtures("resolver")
async def test_drive_list_spends_one_call_for_both_outputs() -> None:
    component = drive_list_component()
    http = wire(component, [json_response("drive_list_response")])

    await component.list_page()
    await component.list_files()

    assert len(http.request_sequence) == 1


@pytest.mark.usefixtures("resolver")
async def test_drive_list_rejects_an_out_of_range_page_size() -> None:
    component = drive_list_component(page_size=5000)
    wire(component, [json_response("drive_list_response")])

    with pytest.raises(ValueError, match="page_size must be between"):
        await component.list_page()


# --------------------------------------------------------------------------
# Drive: Fetch File
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_drive_fetch_downloads_media_for_a_binary_file() -> None:
    component = drive_fetch_component()
    wire(
        component,
        [json_response("drive_fetch_metadata"), media_response(b"line one\nline two\n")],
    )

    result = await component.fetch_file()

    assert result.data["id"] == load_fixture("drive_fetch_metadata")["id"]
    assert result.data["content"] == "line one\nline two\n"
    assert result.data["content_encoding"] == "utf-8"
    assert result.data["content_mime_type"] == "text/plain"
    assert result.data["exported"] is False


@pytest.mark.usefixtures("resolver")
async def test_drive_fetch_base64_encodes_non_text_content() -> None:
    metadata = dict(load_fixture("drive_fetch_metadata"), mimeType="application/pdf")
    payload = b"%PDF-1.7\x00\x01\x02"
    wire_responses = [
        ({"status": "200", "content-type": "application/json"}, json.dumps(metadata).encode()),
        media_response(payload),
    ]
    component = drive_fetch_component()
    wire(component, wire_responses)

    result = await component.fetch_file()

    assert result.data["content_encoding"] == "base64"
    assert base64.b64decode(result.data["content"]) == payload


@pytest.mark.usefixtures("resolver")
async def test_drive_fetch_exports_google_native_documents() -> None:
    component = drive_fetch_component(
        file_id="drive-doc-meeting-notes",
        export_mime_type="text/plain",
    )
    http = wire(
        component,
        [json_response("drive_fetch_doc_metadata"), media_response(b"Meeting notes body")],
    )

    result = await component.fetch_file()

    export_uri = http.request_sequence[1][0]
    assert "/export" in export_uri
    assert query_of(export_uri)["mimeType"] == ["text/plain"]
    assert result.data["exported"] is True
    assert result.data["content"] == "Meeting notes body"
    assert result.data["content_mime_type"] == "text/plain"


@pytest.mark.usefixtures("resolver")
async def test_drive_fetch_passes_acknowledge_abuse_only_on_media_downloads() -> None:
    component = drive_fetch_component(acknowledge_abuse=True)
    http = wire(component, [json_response("drive_fetch_metadata"), media_response(b"bytes")])

    await component.fetch_file()

    assert query_of(http.request_sequence[1][0])["acknowledgeAbuse"] == ["true"]


# --------------------------------------------------------------------------
# Calendar: List Events
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_calendar_list_sends_expansion_and_ordering() -> None:
    component = calendar_list_component(
        time_min="2026-09-01T00:00:00Z",
        time_max="2026-09-30T00:00:00Z",
        query="review",
        max_results=50,
    )
    http = wire(component, [json_response("calendar_list_response")])

    await component.list_page()

    uri = http.request_sequence[0][0]
    assert uri.startswith("https://www.googleapis.com/calendar/v3/calendars/primary/events")
    params = query_of(uri)
    assert params["singleEvents"] == ["true"]
    assert params["orderBy"] == ["startTime"]
    assert params["timeMin"] == ["2026-09-01T00:00:00Z"]
    assert params["timeMax"] == ["2026-09-30T00:00:00Z"]
    assert params["q"] == ["review"]
    assert params["maxResults"] == ["50"]


@pytest.mark.usefixtures("resolver")
async def test_calendar_list_returns_events_and_sync_tokens() -> None:
    component = calendar_list_component()
    wire(component, [json_response("calendar_list_response")])
    expected = load_fixture("calendar_list_response")

    result = await component.list_page()

    assert result.data["events"] == expected["items"]
    assert result.data["next_page_token"] == expected["nextPageToken"]
    assert result.data["next_sync_token"] == expected["nextSyncToken"]
    assert result.data["time_zone"] == expected["timeZone"]


@pytest.mark.usefixtures("resolver")
async def test_calendar_list_rejects_start_time_ordering_without_expansion() -> None:
    component = calendar_list_component(single_events=False, order_by="startTime")
    wire(component, [json_response("calendar_list_response")])

    with pytest.raises(ValueError, match="Expand Recurring Events"):
        await component.list_page()


async def test_calendar_list_requests_only_the_readonly_scope(resolver) -> None:
    component = calendar_list_component()
    wire(component, [json_response("calendar_list_response")])

    await component.list_page()

    assert resolver.requests[0].required_scopes == frozenset({CALENDAR_READONLY_SCOPE})


# --------------------------------------------------------------------------
# Calendar: Create Event
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_calendar_create_posts_the_event_body() -> None:
    component = calendar_create_component(
        description="Weekly",
        location="Remote",
        attendees=["teammate@example.com"],
        send_updates="all",
        recurrence=["RRULE:FREQ=WEEKLY;COUNT=4"],
        conference_data_version=1,
    )
    http = wire(component, [json_response("calendar_create_response")])

    result = await component.create_event()

    uri, method, body, _headers = http.request_sequence[0]
    assert method == "POST"
    params = query_of(uri)
    assert params["sendUpdates"] == ["all"]
    assert params["conferenceDataVersion"] == ["1"]
    payload = json.loads(body)
    assert payload["summary"] == "Langflow sync"
    assert payload["start"] == {"dateTime": "2026-09-10T14:00:00Z"}
    assert payload["attendees"] == [{"email": "teammate@example.com"}]
    assert payload["recurrence"] == ["RRULE:FREQ=WEEKLY;COUNT=4"]
    assert result.data == load_fixture("calendar_create_response")


@pytest.mark.usefixtures("resolver")
async def test_calendar_create_treats_a_bare_date_as_an_all_day_event() -> None:
    component = calendar_create_component(start_time="2026-09-10", end_time="2026-09-11")
    http = wire(component, [json_response("calendar_create_response")])

    await component.create_event()

    payload = json.loads(http.request_sequence[0][2])
    assert payload["start"] == {"date": "2026-09-10"}
    assert payload["end"] == {"date": "2026-09-11"}


async def test_calendar_create_requests_the_write_scope(resolver) -> None:
    component = calendar_create_component()
    wire(component, [json_response("calendar_create_response")])

    await component.create_event()

    assert resolver.requests[0].required_scopes == frozenset({CALENDAR_WRITE_SCOPE})


@pytest.mark.usefixtures("resolver")
async def test_calendar_create_rejects_an_unknown_send_updates_value() -> None:
    component = calendar_create_component(send_updates="everyone")
    wire(component, [json_response("calendar_create_response")])

    with pytest.raises(ValueError, match="send_updates must be one of"):
        await component.create_event()


# --------------------------------------------------------------------------
# Error mapping and the single reactive refresh
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("resolver")
async def test_insufficient_scope_surfaces_as_scope_missing() -> None:
    component = drive_list_component()
    wire(component, [json_response("error_scope_missing", status="403")])

    with pytest.raises(ScopeMissingError) as excinfo:
        await component.list_page()

    assert excinfo.value.code == "scope-missing"
    # The sanitized message never carries Google's own body back to the client.
    assert "insufficient authentication scopes" not in str(excinfo.value)


@pytest.mark.usefixtures("resolver")
async def test_user_rate_limit_403_surfaces_as_rate_limited() -> None:
    component = drive_list_component()
    wire(component, [json_response("error_rate_limited", status="403")])

    with pytest.raises(RateLimitedError) as excinfo:
        await component.list_page()

    assert excinfo.value.code == "rate-limited"
    assert excinfo.value.retryable is True


@pytest.mark.usefixtures("resolver")
async def test_http_429_surfaces_as_rate_limited() -> None:
    component = calendar_list_component()
    wire(component, [({"status": "429"}, b'{"error": {"code": 429, "message": "Too many requests"}}')])

    with pytest.raises(RateLimitedError):
        await component.list_page()


@pytest.mark.usefixtures("resolver")
async def test_server_error_surfaces_as_provider_unavailable() -> None:
    component = calendar_list_component()
    wire(component, [({"status": "503"}, b'{"error": {"code": 503, "message": "Backend error"}}')])

    with pytest.raises(ProviderUnavailableError) as excinfo:
        await component.list_page()

    assert excinfo.value.retryable is True


async def test_auth_rejection_retries_once_with_a_fresh_token(resolver) -> None:
    component = drive_list_component()
    http = wire(
        component,
        [json_response("error_auth_expired", status="401"), json_response("drive_list_response")],
    )

    result = await component.list_page()

    assert result.data["next_page_token"] == load_fixture("drive_list_response")["nextPageToken"]
    assert len(resolver.requests) == 2
    # The second resolution tells the host which token the provider rejected,
    # by digest only, so workers can coordinate one replacement.
    assert resolver.requests[0].rejected_token_digest is None
    assert resolver.requests[1].rejected_token_digest is not None
    assert FAKE_ACCESS_TOKEN not in resolver.requests[1].rejected_token_digest
    assert FAKE_ACCESS_TOKEN in _authorization(http.request_sequence[0])
    assert FAKE_REFRESHED_TOKEN in _authorization(http.request_sequence[-1])


async def test_auth_rejection_is_not_retried_twice(resolver) -> None:
    component = drive_list_component()
    wire(
        component,
        [
            json_response("error_auth_expired", status="401"),
            json_response("error_auth_expired", status="401"),
        ],
    )

    with pytest.raises(AuthExpiredError):
        await component.list_page()

    assert len(resolver.requests) == 2


@pytest.mark.usefixtures("resolver")
async def test_no_access_token_reaches_component_output_or_status() -> None:
    component = gmail_send_component()
    wire(component, [json_response("gmail_send_response")])

    result = await component.send_message()

    rendered = json.dumps(result.data)
    assert FAKE_ACCESS_TOKEN not in rendered
    assert FAKE_ACCESS_TOKEN not in json.dumps(component.status.data)
    logged = json.dumps(getattr(component, "_logs", []), default=str)
    assert FAKE_ACCESS_TOKEN not in logged
