"""Recorded-fixture contract tests for the Outlook mail and calendar actions."""

from __future__ import annotations

import json

import httpx
import pytest
from lfx.integrations.errors import RateLimitedError, ScopeMissingError
from lfx_microsoft import (
    OutlookCalendarCreateComponent,
    OutlookCalendarListComponent,
    OutlookSearchComponent,
    OutlookSendComponent,
)
from lfx_microsoft.components.microsoft.outlook_send import MAX_ATTACHMENT_BYTES
from microsoft_testkit import TransportRecorder, build_component, credential, graph_error, graph_fixture, json_response


async def test_send_mail_posts_the_graph_message_shape(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Mail.Send"}))
    recorder = TransportRecorder(lambda _request: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to=["ada@contoso.com", "grace@contoso.com"],
        cc="alan@contoso.com",
        subject="Quarterly plan",
        body="<p>Draft attached.</p>",
        body_is_html=True,
        save_to_sent_items=False,
    )

    result = await component.send_mail()

    request = recorder.last
    assert request.method == "POST"
    assert str(request.url) == "https://graph.microsoft.com/v1.0/me/sendMail"
    payload = json.loads(request.content)
    assert payload["saveToSentItems"] is False
    assert payload["message"]["subject"] == "Quarterly plan"
    assert payload["message"]["body"] == {"contentType": "html", "content": "<p>Draft attached.</p>"}
    assert payload["message"]["toRecipients"] == [
        {"emailAddress": {"address": "ada@contoso.com"}},
        {"emailAddress": {"address": "grace@contoso.com"}},
    ]
    assert payload["message"]["ccRecipients"] == [{"emailAddress": {"address": "alan@contoso.com"}}]
    assert "bccRecipients" not in payload["message"]
    assert result.data["accepted"] is True
    assert result.data["status_code"] == 202


async def test_send_mail_defaults_to_plain_text_and_sent_items(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Mail.Send"}))
    recorder = TransportRecorder(lambda _request: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="Ping",
        body="hello",
    )

    await component.send_mail()

    payload = json.loads(recorder.last.content)
    assert payload["saveToSentItems"] is True
    assert payload["message"]["body"]["contentType"] == "text"


async def test_send_mail_attaches_files_as_base64_file_attachments(resolver_factory, tmp_path) -> None:
    resolver_factory(credential(scopes={"Mail.Send"}))
    attachment = tmp_path / "notes.txt"
    attachment.write_bytes(b"hello")
    recorder = TransportRecorder(lambda _request: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="With attachment",
        body="see attached",
        attachments=[str(attachment)],
    )

    result = await component.send_mail()

    payload = json.loads(recorder.last.content)
    assert payload["message"]["attachments"] == [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "notes.txt",
            "contentBytes": "aGVsbG8=",
        }
    ]
    assert result.data["attachment_count"] == 1


async def test_send_mail_refuses_attachments_over_the_inline_graph_limit(resolver_factory, tmp_path) -> None:
    """Graph caps the sendMail body at 4 MB; refuse before reading the file, not after a 413."""
    resolver_factory(credential(scopes={"Mail.Send"}))
    attachment = tmp_path / "big.bin"
    attachment.write_bytes(b"0" * (MAX_ATTACHMENT_BYTES + 1))
    recorder = TransportRecorder(lambda _request: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="Too big",
        body="see attached",
        attachments=[str(attachment)],
    )

    with pytest.raises(ValueError, match="exceed"):
        await component.send_mail()
    assert recorder.requests == []


async def test_send_mail_surfaces_rate_limits_with_retry_after(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Mail.Send"}))
    recorder = TransportRecorder(
        lambda _request: graph_error("ApplicationThrottled", 429, headers={"Retry-After": "31"})
    )
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="Ping",
        body="hello",
    )

    with pytest.raises(RateLimitedError) as excinfo:
        await component.send_mail()
    assert excinfo.value.retry_after == 31.0


async def test_send_mail_rejects_a_connection_without_mail_send(resolver_factory) -> None:
    """The pre-flight fires before any Graph request is made."""
    resolver_factory(credential(scopes={"Mail.Read"}))
    recorder = TransportRecorder(lambda _request: httpx.Response(202))
    component = build_component(
        OutlookSendComponent,
        recorder,
        connection="microsoft/work",
        to="ada@contoso.com",
        subject="Ping",
        body="hello",
    )

    with pytest.raises(ScopeMissingError) as excinfo:
        await component.send_mail()
    assert excinfo.value.missing == frozenset({"Mail.Send"})
    assert recorder.requests == []


async def test_search_mail_builds_the_odata_query(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Mail.Read"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("messages_page1")))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        connection="microsoft/work",
        search="budget",
        folder_id="inbox",
        top=2,
        select=["id", "subject"],
        include_body=True,
    )

    rows = await component.search_messages()

    request = recorder.last
    assert request.url.path == "/v1.0/me/mailFolders/inbox/messages"
    assert request.url.params["$search"] == '"budget"'
    assert request.url.params["$top"] == "2"
    assert request.url.params["$select"] == "id,subject"
    assert request.headers["prefer"] == "outlook.body-content-type=text"
    assert [row.data["id"] for row in rows] == ["AAMkAGI2TG93AAA=", "AAMkAGI2TG94AAA="]
    next_link = await component.next_page_link()
    assert next_link.text == "https://graph.microsoft.com/v1.0/me/messages?%24skip=2"


async def test_search_mail_defaults_to_the_whole_mailbox(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Mail.Read"}))
    recorder = TransportRecorder(lambda _request: json_response({"value": []}))
    component = build_component(OutlookSearchComponent, recorder, connection="microsoft/work")

    rows = await component.search_messages()

    assert rows == []
    assert recorder.last.url.path == "/v1.0/me/messages"
    assert recorder.last.url.params["$top"] == "10"
    assert "prefer" not in recorder.last.headers


async def test_calendar_list_sends_the_window_and_timezone(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Calendars.Read"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("calendar_view")))
    component = build_component(
        OutlookCalendarListComponent,
        recorder,
        connection="microsoft/work",
        start_time="2026-09-01T00:00:00",
        end_time="2026-09-02T00:00:00",
        time_zone="Pacific Standard Time",
        top=25,
    )

    rows = await component.list_events()

    request = recorder.last
    assert request.url.path == "/v1.0/me/calendarView"
    assert request.url.params["startDateTime"] == "2026-09-01T00:00:00"
    assert request.url.params["endDateTime"] == "2026-09-02T00:00:00"
    assert request.headers["prefer"] == 'outlook.timezone="Pacific Standard Time"'
    assert [row.data["subject"] for row in rows] == ["Team sync"]


async def test_calendar_list_targets_a_named_calendar(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Calendars.Read"}))
    recorder = TransportRecorder(lambda _request: json_response({"value": []}))
    component = build_component(
        OutlookCalendarListComponent,
        recorder,
        connection="microsoft/work",
        start_time="2026-09-01T00:00:00",
        end_time="2026-09-02T00:00:00",
        calendar_id="cal-1",
    )

    await component.list_events()

    assert recorder.last.url.path == "/v1.0/me/calendars/cal-1/calendarView"


async def test_calendar_create_builds_the_event_resource(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Calendars.ReadWrite"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("event_created"), status_code=201))
    component = build_component(
        OutlookCalendarCreateComponent,
        recorder,
        connection="microsoft/work",
        subject="Design review",
        start_time="2026-09-02T15:00:00",
        end_time="2026-09-02T16:00:00",
        time_zone="UTC",
        body="Agenda in the doc.",
        location="Room 1",
        attendees=["ada@contoso.com"],
        is_online_meeting=True,
        transaction_id="txn-1",
    )

    result = await component.create_event()

    request = recorder.last
    assert request.method == "POST"
    assert request.url.path == "/v1.0/me/events"
    assert request.headers["prefer"] == 'outlook.timezone="UTC"'
    payload = json.loads(request.content)
    assert payload["start"] == {"dateTime": "2026-09-02T15:00:00", "timeZone": "UTC"}
    assert payload["end"] == {"dateTime": "2026-09-02T16:00:00", "timeZone": "UTC"}
    assert payload["location"] == {"displayName": "Room 1"}
    assert payload["attendees"] == [{"emailAddress": {"address": "ada@contoso.com"}, "type": "required"}]
    assert payload["isOnlineMeeting"] is True
    assert payload["transactionId"] == "txn-1"
    assert result.data["id"] == "AAMkAGV2bmV3AAA="


async def test_calendar_create_omits_optional_members(resolver_factory) -> None:
    resolver_factory(credential(scopes={"Calendars.ReadWrite"}))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("event_created"), status_code=201))
    component = build_component(
        OutlookCalendarCreateComponent,
        recorder,
        connection="microsoft/work",
        subject="Focus time",
        start_time="2026-09-02T15:00:00",
        end_time="2026-09-02T16:00:00",
    )

    await component.create_event()

    payload = json.loads(recorder.last.content)
    assert set(payload) == {"subject", "start", "end"}
    assert payload["start"]["timeZone"] == "UTC"
