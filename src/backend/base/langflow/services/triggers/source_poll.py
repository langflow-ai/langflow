"""Microsoft Graph delta and Google Workspace change-feed expansion.

Both a Track B timer and a verified Track A notification call ``poll_source``.
The notification only wakes this worker; it never becomes a flow input. All
provider URLs use ``SourceHTTP``'s fixed-origin check and the owner's delegated
credential. A completed round commits normalized items and its new cursor in
one database transaction.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from langflow.services.triggers.constants import FAMILY_TRIGGER_LISTENER, PROVIDER_GOOGLE, PROVIDER_MICROSOFT
from langflow.services.triggers.source_clients import (
    GOOGLE_CALENDAR_ORIGIN,
    GOOGLE_DRIVE_ORIGIN,
    GOOGLE_GMAIL_ORIGIN,
    GRAPH_ORIGIN,
    SourceHTTP,
    source_lease,
)
from langflow.services.triggers.source_delivery import append_and_advance

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.integrations.models import CredentialLease
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger

_MAX_PAGES = 100
_SAFE_GRAPH_ID = re.compile(r"^[A-Za-z0-9_,.!@-]{1,255}$")


def _version(item: dict[str, Any], *fields: str) -> str:
    if "@removed" in item or item.get("removed") or item.get("status") == "cancelled":
        return "deleted"
    for field in fields:
        value = item.get(field)
        if value is not None:
            return str(value)
    return hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()


def _canonical(provider: str, resource: str, item: dict[str, Any], *, version: str) -> dict[str, Any] | None:
    item_id = item.get("id") or item.get("fileId")
    if not isinstance(item_id, str) or not item_id:
        return None
    if resource.startswith("mail:"):
        session_key = f"microsoft:outlook:{item.get('conversationId') or item_id}"
    elif resource.startswith("calendar:"):
        thread_id = (
            item.get("iCalUId")
            or item.get("iCalUID")
            or item.get("recurringEventId")
            or item.get("seriesMasterId")
            or item_id
        )
        session_key = f"{provider}:calendar:{thread_id}"
    elif resource == "gmail:inbox":
        session_key = f"google:gmail:{item.get('threadId') or item_id}"
    else:
        session_key = f"{provider}:files:{item_id}"
    return {
        "provider": provider,
        "resource": resource,
        "id": item_id,
        "version": version,
        "deleted": version == "deleted",
        "data": item,
        "session_key": session_key,
    }


def _graph_start(trigger: Trigger) -> tuple[str, str, dict[str, Any]]:
    config = trigger.config or {}
    state = trigger.provider_state or {}
    if trigger.kind == "microsoft.mail":
        return "v1.0/me/mailFolders('Inbox')/messages/delta", "mail:inbox", {}
    if trigger.kind == "microsoft.calendar":
        window = state.get("window")
        if not isinstance(window, dict):
            now = datetime.now(timezone.utc)
            window = {
                "start": (now - timedelta(days=30)).isoformat(),
                "end": (now + timedelta(days=365)).isoformat(),
            }
        return (
            "v1.0/me/calendarView/delta",
            "calendar:default",
            {
                "startDateTime": window["start"],
                "endDateTime": window["end"],
            },
        )
    if trigger.kind == "microsoft.file":
        site_id = config.get("site_id")
        if site_id:
            if not isinstance(site_id, str) or not _SAFE_GRAPH_ID.fullmatch(site_id):
                msg = "Invalid SharePoint site id."
                raise ValueError(msg)
            return f"v1.0/sites/{site_id}/drive/root/delta", f"drive:site:{site_id}", {}
        return "v1.0/me/drive/root/delta", "drive:me", {}
    msg = f"Unsupported Microsoft source kind: {trigger.kind}"
    raise ValueError(msg)


async def _graph_changes(client: SourceHTTP, trigger: Trigger) -> tuple[list[dict], dict, bool, bool]:
    state = dict(trigger.provider_state or {})
    path, resource, params = _graph_start(trigger)
    start_params = dict(params)
    cursor = state.get("delta_link")
    baseline = cursor is None and not state.get("baseline_complete")
    resync = False
    if trigger.kind == "microsoft.calendar" and isinstance(state.get("window"), dict):
        try:
            window_end = datetime.fromisoformat(str(state["window"]["end"]))
        except (KeyError, TypeError, ValueError):
            window_end = datetime.min.replace(tzinfo=timezone.utc)
        if window_end < datetime.now(timezone.utc) + timedelta(days=30):
            now = datetime.now(timezone.utc)
            params = {
                "startDateTime": (now - timedelta(days=30)).isoformat(),
                "endDateTime": (now + timedelta(days=365)).isoformat(),
            }
            start_params = dict(params)
            cursor = None
            baseline = False
    target = cursor or path
    items: list[dict] = []
    for _ in range(_MAX_PAGES):
        try:
            response = await client.request("GET", target, params=params if target == path else None)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.GONE or target == path:
                raise
            # Graph invalidated its opaque delta token. Re-enumerate the
            # current snapshot and compare with durable item versions.
            target, cursor, params = path, None, _graph_start(trigger)[2]
            resync = True
            items.clear()
            response = await client.request("GET", target, params=params)
        for item in response.get("value", []):
            if not isinstance(item, dict):
                continue
            normalized = _canonical(
                PROVIDER_MICROSOFT,
                resource,
                item,
                version=_version(item, "changeKey", "@odata.etag", "lastModifiedDateTime"),
            )
            if normalized:
                items.append(normalized)
        next_link = response.get("@odata.nextLink")
        if next_link:
            target = next_link
            params = {}
            continue
        delta = response.get("@odata.deltaLink")
        if not isinstance(delta, str) or not delta:
            msg = "Graph delta round returned no continuation cursor."
            raise ValueError(msg)
        update = {"delta_link": delta, "baseline_complete": True}
        old_window = state.get("window") if isinstance(state.get("window"), dict) else {}
        if trigger.kind == "microsoft.calendar" and start_params["endDateTime"] != old_window.get("end"):
            update["window"] = {"start": start_params["startDateTime"], "end": start_params["endDateTime"]}
        return items, update, baseline, resync
    msg = "Graph delta round exceeded the page limit."
    raise ValueError(msg)


async def _calendar_changes(client: SourceHTTP, trigger: Trigger) -> tuple[list[dict], dict, bool, bool]:
    state = dict(trigger.provider_state or {})
    calendar_id = str((trigger.config or {}).get("calendar_id") or "primary")
    path = f"calendar/v3/calendars/{quote(calendar_id, safe='')}/events"
    sync_token = state.get("sync_token")
    baseline = sync_token is None and not state.get("baseline_complete")
    items: list[dict] = []
    resync = False
    page_token: str | None = None
    for _ in range(_MAX_PAGES):
        params: dict[str, Any] = {"maxResults": 2500, "showDeleted": "true"}
        if sync_token:
            params["syncToken"] = sync_token
        if page_token:
            params["pageToken"] = page_token
        try:
            response = await client.request("GET", path, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.GONE or not sync_token:
                raise
            sync_token, page_token = None, None
            resync = True
            items.clear()
            response = await client.request("GET", path, params={"maxResults": 2500, "showDeleted": "true"})
        for item in response.get("items", []):
            if isinstance(item, dict):
                normalized = _canonical(
                    PROVIDER_GOOGLE,
                    f"calendar:{calendar_id}",
                    item,
                    version=_version(item, "etag", "updated"),
                )
                if normalized:
                    items.append(normalized)
        page_token = response.get("nextPageToken")
        if page_token:
            continue
        new_token = response.get("nextSyncToken")
        if not isinstance(new_token, str) or not new_token:
            msg = "Calendar sync round returned no sync token."
            raise ValueError(msg)
        return items, {"sync_token": new_token, "baseline_complete": True}, baseline, resync
    msg = "Calendar sync round exceeded the page limit."
    raise ValueError(msg)


async def _drive_snapshot(client: SourceHTTP) -> list[dict]:
    """Enumerate app-visible files after a rejected change token."""
    items: list[dict] = []
    page_token: str | None = None
    for _ in range(_MAX_PAGES):
        params: dict[str, Any] = {
            "pageSize": 1000,
            "q": "trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,version,parents,webViewLink)",
        }
        if page_token:
            params["pageToken"] = page_token
        response = await client.request("GET", "drive/v3/files", params=params)
        for file in response.get("files", []):
            if isinstance(file, dict):
                normalized = _canonical(
                    PROVIDER_GOOGLE, "drive:app_files", file, version=_version(file, "version", "modifiedTime")
                )
                if normalized:
                    items.append(normalized)
        page_token = response.get("nextPageToken")
        if not page_token:
            return items
    msg = "Drive full resync exceeded the page limit."
    raise ValueError(msg)


async def _drive_changes(client: SourceHTTP, trigger: Trigger) -> tuple[list[dict], dict, bool, bool]:
    state = dict(trigger.provider_state or {})
    token = state.get("page_token")
    if not token:
        response = await client.request("GET", "drive/v3/changes/startPageToken")
        initial = response.get("startPageToken")
        if not isinstance(initial, str):
            msg = "Drive did not return a start page token."
            raise ValueError(msg)
        return [], {"page_token": initial, "baseline_complete": True}, True, False
    items: list[dict] = []
    for _ in range(_MAX_PAGES):
        try:
            response = await client.request(
                "GET",
                "drive/v3/changes",
                params={"pageToken": token, "pageSize": 1000, "includeRemoved": "true", "fields": "*"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.GONE:
                raise
            reset = await client.request("GET", "drive/v3/changes/startPageToken")
            initial = reset.get("startPageToken")
            if not isinstance(initial, str):
                raise
            snapshot = await _drive_snapshot(client)
            return snapshot, {"page_token": initial, "baseline_complete": True}, False, True
        for change in response.get("changes", []):
            if not isinstance(change, dict):
                continue
            file = change.get("file") if isinstance(change.get("file"), dict) else {}
            item = {**file, "id": change.get("fileId") or file.get("id"), "removed": change.get("removed")}
            normalized = _canonical(
                PROVIDER_GOOGLE,
                "drive:app_files",
                item,
                version=_version(item, "version", "modifiedTime", "time"),
            )
            if normalized:
                items.append(normalized)
        next_token = response.get("nextPageToken")
        if next_token:
            token = next_token
            continue
        new_token = response.get("newStartPageToken")
        if not isinstance(new_token, str):
            msg = "Drive change round returned no start page token."
            raise TypeError(msg)
        return items, {"page_token": new_token, "baseline_complete": True}, False, False
    msg = "Drive change round exceeded the page limit."
    raise ValueError(msg)


async def _gmail_changes(client: SourceHTTP, trigger: Trigger) -> tuple[list[dict], dict, bool, bool]:
    state = dict(trigger.provider_state or {})
    history_id = state.get("history_id")
    if not history_id:
        profile = await client.request("GET", "gmail/v1/users/me/profile")
        return [], {"history_id": str(profile["historyId"]), "baseline_complete": True}, True, False
    items: list[dict] = []
    page_token: str | None = None
    for _ in range(_MAX_PAGES):
        params = {"startHistoryId": history_id, "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        try:
            response = await client.request("GET", "gmail/v1/users/me/history", params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != httpx.codes.NOT_FOUND:
                raise
            profile = await client.request("GET", "gmail/v1/users/me/profile")
            # Gmail no longer retains the history gap. Start at the current
            # watermark; enumerating the Inbox here would fire old messages.
            return [], {"history_id": str(profile["historyId"]), "baseline_complete": True}, True, False
        for history in response.get("history", []):
            if not isinstance(history, dict):
                continue
            for source_key in ("messagesAdded", "labelsAdded", "messagesDeleted", "labelsRemoved"):
                for entry in history.get(source_key, []):
                    message = entry.get("message") if isinstance(entry, dict) else None
                    message_id = message.get("id") if isinstance(message, dict) else None
                    if not isinstance(message_id, str) or not message_id:
                        continue
                    if source_key.startswith("labels") and "INBOX" not in (entry.get("labelIds") or []):
                        continue
                    if source_key in {"messagesDeleted", "labelsRemoved"}:
                        normalized = _canonical(
                            PROVIDER_GOOGLE,
                            "gmail:inbox",
                            {**message, "removed": True, "historyId": history.get("id")},
                            version="deleted",
                        )
                    else:
                        try:
                            full = await client.request(
                                "GET",
                                f"gmail/v1/users/me/messages/{quote(message_id, safe='')}",
                                params={"format": "metadata"},
                            )
                        except httpx.HTTPStatusError as exc:
                            if exc.response.status_code != httpx.codes.NOT_FOUND:
                                raise
                            continue
                        normalized = _canonical(
                            PROVIDER_GOOGLE,
                            "gmail:inbox",
                            full,
                            version=f"{history.get('id') or full.get('historyId')}:{source_key}",
                        )
                    if normalized:
                        items.append(normalized)
        page_token = response.get("nextPageToken")
        if page_token:
            continue
        return items, {"history_id": str(response["historyId"]), "baseline_complete": True}, False, False
    msg = "Gmail history round exceeded the page limit."
    raise ValueError(msg)


@dataclass(frozen=True)
class SourceRound:
    items: list[dict[str, Any]]
    cursor: dict[str, Any]
    previous_cursor: dict[str, Any]
    baseline: bool
    snapshot_resource: str | None
    connection_id: UUID | None
    mechanism_id: str | None


async def collect_source(trigger: Trigger, lease: CredentialLease) -> SourceRound:
    """Fetch a complete provider round without holding a database transaction."""
    previous = dict(trigger.provider_state or {})
    expected_connection_id = trigger.connection_id
    expected_mechanism_id = (trigger.config or {}).get("mechanism_id")
    if trigger.provider == PROVIDER_MICROSOFT:
        async with SourceHTTP(lease, origin=GRAPH_ORIGIN) as client:
            items, cursor, baseline, resync = await _graph_changes(client, trigger)
    elif trigger.kind == "google.calendar":
        async with SourceHTTP(lease, origin=GOOGLE_CALENDAR_ORIGIN) as client:
            items, cursor, baseline, resync = await _calendar_changes(client, trigger)
    elif trigger.kind == "google.drive":
        async with SourceHTTP(lease, origin=GOOGLE_DRIVE_ORIGIN) as client:
            items, cursor, baseline, resync = await _drive_changes(client, trigger)
    elif trigger.kind == "google.gmail":
        async with SourceHTTP(lease, origin=GOOGLE_GMAIL_ORIGIN) as client:
            items, cursor, baseline, resync = await _gmail_changes(client, trigger)
    else:
        msg = f"Unsupported source trigger kind: {trigger.kind}"
        raise ValueError(msg)
    return SourceRound(
        items=items,
        cursor=cursor,
        previous_cursor=previous,
        baseline=baseline,
        snapshot_resource=(items[0]["resource"] if items else _source_resource(trigger)) if resync else None,
        connection_id=expected_connection_id,
        mechanism_id=expected_mechanism_id,
    )


async def commit_source(session: AsyncSession, *, trigger_id: UUID, source_round: SourceRound) -> int:
    return await append_and_advance(
        session,
        trigger_id=trigger_id,
        items=source_round.items,
        cursor=source_round.cursor,
        previous_cursor=source_round.previous_cursor,
        baseline=source_round.baseline,
        expected_connection_id=source_round.connection_id,
        expected_mechanism_id=source_round.mechanism_id,
        snapshot_resource=source_round.snapshot_resource,
    )


async def poll_source(session: AsyncSession, trigger: Trigger, *, family: str = FAMILY_TRIGGER_LISTENER) -> int:
    """Read a source round and commit it with its cursor."""
    lease = await source_lease(session, trigger, family=family)
    source_round = await collect_source(trigger, lease)
    return await commit_source(session, trigger_id=trigger.id, source_round=source_round)


def _source_resource(trigger: Trigger) -> str:
    if trigger.provider == PROVIDER_MICROSOFT:
        return _graph_start(trigger)[1]
    if trigger.kind == "google.calendar":
        return f"calendar:{(trigger.config or {}).get('calendar_id') or 'primary'}"
    if trigger.kind == "google.drive":
        return "drive:app_files"
    return "gmail:inbox"
