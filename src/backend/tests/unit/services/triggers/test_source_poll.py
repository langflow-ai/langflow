"""Recorded provider page contracts for source expansion and recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.triggers.source_clients import (
    GOOGLE_CALENDAR_ORIGIN,
    GOOGLE_GMAIL_ORIGIN,
    GRAPH_ORIGIN,
    SourceHTTP,
)
from langflow.services.triggers.source_poll import _calendar_changes, _canonical, _gmail_changes, _graph_changes


class _Lease:
    async def get_token(self) -> str:
        return "source-test-token"


def _trigger(*, kind: str, provider: str, state: dict | None = None) -> Trigger:
    return Trigger(
        id=uuid4(),
        flow_id=uuid4(),
        user_id=uuid4(),
        name="source",
        kind=kind,
        provider=provider,
        config={"calendar_id": "primary"},
        provider_state=state or {},
    )


async def test_graph_delta_follows_pages_and_returns_only_the_final_cursor() -> None:
    requests: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "m1", "changeKey": "v1"}],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages/delta?$skiptoken=second",
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [{"id": "m2", "changeKey": "v2"}],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/me/messages/delta?$deltatoken=final",
            },
        )

    async with SourceHTTP(_Lease(), origin=GRAPH_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        items, cursor, baseline, resync = await _graph_changes(
            client, _trigger(kind="microsoft.mail", provider="microsoft")
        )
    assert [item["id"] for item in items] == ["m1", "m2"]
    assert cursor["delta_link"].endswith("final")
    assert baseline is True
    assert resync is False
    assert len(requests) == 2


async def test_graph_rejected_delta_token_rescans_without_baselining() -> None:
    requests: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(410, json={"error": {"code": "syncStateNotFound"}})
        return httpx.Response(200, json={"value": [{"id": "m1", "changeKey": "v2"}], "@odata.deltaLink": "new"})

    trigger = _trigger(
        kind="microsoft.mail",
        provider="microsoft",
        state={
            "delta_link": "https://graph.microsoft.com/v1.0/me/messages/delta?$deltatoken=old",
            "baseline_complete": True,
        },
    )
    async with SourceHTTP(_Lease(), origin=GRAPH_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        items, cursor, baseline, resync = await _graph_changes(client, trigger)
    assert [item["version"] for item in items] == ["v2"]
    assert cursor["delta_link"] == "new"
    assert baseline is False
    assert resync is True
    assert len(requests) == 2


async def test_calendar_sync_token_410_rescans_current_items() -> None:
    requests: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(410, json={"error": {"code": 410}})
        return httpx.Response(200, json={"items": [{"id": "e1", "etag": "v2"}], "nextSyncToken": "new"})

    trigger = _trigger(
        kind="google.calendar", provider="google", state={"sync_token": "old", "baseline_complete": True}
    )
    async with SourceHTTP(_Lease(), origin=GOOGLE_CALENDAR_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        items, cursor, baseline, resync = await _calendar_changes(client, trigger)
    assert [(item["id"], item["version"]) for item in items] == [("e1", "v2")]
    assert cursor["sync_token"] == "new"  # noqa: S105 - mock provider cursor
    assert baseline is False
    assert resync is True


async def test_calendar_window_rolls_forward_before_it_expires() -> None:
    requests: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, json={"value": [], "@odata.deltaLink": "rolled"})

    old = {
        "start": (datetime.now(timezone.utc) - timedelta(days=360)).isoformat(),
        "end": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    trigger = _trigger(
        kind="microsoft.calendar",
        provider="microsoft",
        state={
            "delta_link": "https://graph.microsoft.com/v1.0/me/calendarView/delta?old=1",
            "window": old,
            "baseline_complete": True,
        },
    )
    async with SourceHTTP(_Lease(), origin=GRAPH_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        _items, cursor, baseline, resync = await _graph_changes(client, trigger)
    assert "startDateTime=" in requests[0]
    assert "old=1" not in requests[0]
    assert cursor["window"]["end"] != old["end"]
    assert baseline is False
    assert resync is False


def test_source_items_use_provider_conversation_keys() -> None:
    cases = [
        ("microsoft", "mail:inbox", {"id": "m1", "conversationId": "thread"}, "microsoft:outlook:thread"),
        ("microsoft", "calendar:default", {"id": "e1", "iCalUId": "series"}, "microsoft:calendar:series"),
        ("microsoft", "drive:me", {"id": "f1"}, "microsoft:files:f1"),
        ("google", "calendar:primary", {"id": "e2", "iCalUID": "series2"}, "google:calendar:series2"),
        ("google", "drive:app_files", {"id": "f2"}, "google:files:f2"),
        ("google", "gmail:inbox", {"id": "m2", "threadId": "thread2"}, "google:gmail:thread2"),
    ]
    for provider, resource, item, expected in cases:
        assert _canonical(provider, resource, item, version="v1")["session_key"] == expected


async def test_gmail_history_expansion_includes_inbox_removal_and_thread_key() -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/history"):
            return httpx.Response(
                200,
                json={
                    "historyId": "105",
                    "history": [
                        {"id": "104", "messagesAdded": [{"message": {"id": "m1"}}]},
                        {
                            "id": "105",
                            "labelsRemoved": [{"message": {"id": "m2", "threadId": "t2"}, "labelIds": ["INBOX"]}],
                        },
                    ],
                },
            )
        return httpx.Response(200, json={"id": "m1", "threadId": "t1", "historyId": "104"})

    trigger = _trigger(kind="google.gmail", provider="google", state={"history_id": "100"})
    async with SourceHTTP(_Lease(), origin=GOOGLE_GMAIL_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        items, cursor, baseline, resync = await _gmail_changes(client, trigger)
    assert [(item["id"], item["deleted"], item["session_key"]) for item in items] == [
        ("m1", False, "google:gmail:t1"),
        ("m2", True, "google:gmail:t2"),
    ]
    assert cursor["history_id"] == "105"
    assert baseline is False
    assert resync is False


async def test_expired_gmail_history_starts_at_current_watermark_without_old_messages() -> None:
    paths: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/history"):
            return httpx.Response(404)
        return httpx.Response(200, json={"historyId": "200"})

    trigger = _trigger(kind="google.gmail", provider="google", state={"history_id": "100"})
    async with SourceHTTP(_Lease(), origin=GOOGLE_GMAIL_ORIGIN, transport=httpx.MockTransport(reply)) as client:
        items, cursor, baseline, resync = await _gmail_changes(client, trigger)
    assert items == []
    assert cursor["history_id"] == "200"
    assert baseline is True
    assert resync is False
    assert paths == ["/gmail/v1/users/me/history", "/gmail/v1/users/me/profile"]
