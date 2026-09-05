"""Opt-in live suite: the five Google actions against a real Workspace account.

Marked ``api_key_required``, which CI deselects (``-m "not api_key_required"`` in
.github/workflows/cross-bundle-test.yml), and it also self-skips when the
environment is not configured — so it never runs by accident.

How it runs
-----------
The suite drives the components through the *headless* path:
``EnvConnectionResolver`` reads ``LF_CONNECTION__GOOGLE__LIVE`` and the graph
principal is ``headless_operator``, which is the only principal the env resolver
accepts for an env-owned credential. That is deliberate: on this branch nothing
in langflow-base stamps an execution principal yet (INT-6 owns that), so an
in-server run would fail closed with ``connection-not-authorized`` regardless of
the credential. INT-6 landing is what makes the same components runnable from the
canvas, ``/api/v1/run`` and deployments; INT-14 re-runs this list in-server.

Setup
-----
The env resolver refuses long-lived secrets in its wire format, so it only ever
holds a short-lived access token (roughly one hour). Mint one from a stored
refresh token:

    export GOOGLE_LIVE_CLIENT_ID=...
    export GOOGLE_LIVE_CLIENT_SECRET=...
    export GOOGLE_LIVE_REFRESH_TOKEN=...
    export LANGFLOW_GOOGLE_LIVE_RECIPIENT=you@example.com    # send-to-self target

``_mint_access_token`` below performs that exchange once per session and exports
``LF_CONNECTION__GOOGLE__LIVE``. Alternatively export that variable yourself:

    export LF_CONNECTION__GOOGLE__LIVE='{"access_token":"ya29...."}'

The Google project needs the five wave-1 scopes on its consent screen. A project
in *Testing* publishing status issues refresh tokens that expire after 7 days, so
a maintained project in *In production* status is what keeps this suite runnable.
"""

from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

import pytest
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_google.components.google import (
    GmailSendComponent,
    GoogleCalendarCreateComponent,
    GoogleCalendarListComponent,
    GoogleDriveFetchComponent,
    GoogleDriveListComponent,
)

pytestmark = pytest.mark.api_key_required

LIVE_ENV_KEY = "LF_CONNECTION__GOOGLE__LIVE"
CONNECTION_HANDLE = "google/live"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - endpoint URL, not a credential
HTTP_OK = 200


def _mint_access_token() -> str | None:
    """Exchange a stored refresh token for an access token, or return None."""
    client_id = os.environ.get("GOOGLE_LIVE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_LIVE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_LIVE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        return None
    import httpx

    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    if response.status_code != HTTP_OK:
        pytest.skip(f"Google refused the refresh-token exchange: {response.status_code}")
    return response.json()["access_token"]


@pytest.fixture(scope="session", autouse=True)
def live_credential() -> None:
    """Make sure LF_CONNECTION__GOOGLE__LIVE holds a usable access token."""
    if os.environ.get(LIVE_ENV_KEY):
        return
    token = _mint_access_token()
    if token is None:
        pytest.skip(
            f"Set {LIVE_ENV_KEY}, or GOOGLE_LIVE_CLIENT_ID/GOOGLE_LIVE_CLIENT_SECRET/"
            "GOOGLE_LIVE_REFRESH_TOKEN, to run the live Google suite."
        )
    os.environ[LIVE_ENV_KEY] = json.dumps({"access_token": token})


@pytest.fixture
def headless(monkeypatch: pytest.MonkeyPatch):
    """Wire a component for the headless env-resolver path."""
    from lfx.services.connection.env_resolver import EnvConnectionResolver

    resolver = EnvConnectionResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)

    def configure(component):
        component.connection = CONNECTION_HANDLE
        component.set_vertex(
            SimpleNamespace(
                graph=SimpleNamespace(
                    execution_principal=ExecutionPrincipal(kind="headless_operator"),
                    flow_id=None,
                    run_id=None,
                )
            )
        )
        return component

    return configure


def _recipient() -> str:
    recipient = os.environ.get("LANGFLOW_GOOGLE_LIVE_RECIPIENT")
    if not recipient:
        pytest.skip("Set LANGFLOW_GOOGLE_LIVE_RECIPIENT to a mailbox this account may send to.")
    return recipient


def _calendar_id() -> str:
    return os.environ.get("LANGFLOW_GOOGLE_LIVE_CALENDAR_ID", "primary")


async def test_live_gmail_send(headless) -> None:
    component = headless(
        GmailSendComponent(
            to=[_recipient()],
            cc=[],
            bcc=[],
            subject=f"Langflow live suite {int(time.time())}",
            body="Sent by the lfx-google live suite.",
            body_is_html=False,
            attachments=[],
            thread_id="",
        )
    )

    result = await component.send_message()

    assert result.data["id"]
    assert "SENT" in result.data.get("labelIds", [])


async def test_live_drive_list(headless) -> None:
    component = headless(
        GoogleDriveListComponent(
            query="",
            page_size=10,
            page_token="",
            order_by="",
            include_shared_drives=False,
            fields="",
        )
    )

    result = await component.list_page()

    # An empty list is a valid result under drive.file: it means the account has
    # not created or opened any file with this app.
    assert isinstance(result.data["files"], list)
    assert result.data["incomplete_search"] is False


async def test_live_drive_fetch(headless) -> None:
    listing = headless(
        GoogleDriveListComponent(
            query="", page_size=10, page_token="", order_by="", include_shared_drives=False, fields=""
        )
    )
    files = (await listing.list_page()).data["files"]
    app_files = [entry for entry in files if not entry["mimeType"].startswith("application/vnd.google-apps.")]
    if not app_files:
        pytest.skip("The live account has no app-visible binary file to fetch; create one first.")

    component = headless(
        GoogleDriveFetchComponent(
            file_id=app_files[0]["id"],
            export_mime_type="",
            acknowledge_abuse=False,
            supports_all_drives=False,
        )
    )

    result = await component.fetch_file()

    assert result.data["id"] == app_files[0]["id"]
    assert result.data["content_encoding"] in {"utf-8", "base64"}


async def test_live_calendar_list(headless) -> None:
    component = headless(
        GoogleCalendarListComponent(
            calendar_id=_calendar_id(),
            time_min="",
            time_max="",
            query="",
            max_results=10,
            single_events=True,
            order_by="startTime",
            page_token="",
        )
    )

    result = await component.list_page()

    assert isinstance(result.data["events"], list)
    assert result.data["time_zone"]


async def test_live_calendar_create_then_delete(headless) -> None:
    """Create a real event, then clean it up so the suite is repeatable."""
    component = headless(
        GoogleCalendarCreateComponent(
            calendar_id=_calendar_id(),
            summary=f"Langflow live suite {int(time.time())}",
            start_time="2030-01-01T10:00:00Z",
            end_time="2030-01-01T11:00:00Z",
            description="Created by the lfx-google live suite.",
            location="",
            attendees=[],
            send_updates="none",
            recurrence=[],
            conference_data_version=0,
        )
    )

    result = await component.create_event()
    event_id = result.data["id"]
    assert result.data["status"] == "confirmed"

    from lfx_google.components.google._workspace_client import workspace_action

    async with workspace_action(
        component, capability="google.calendar.create", api="calendar", version="v3"
    ) as service:
        await service.execute(lambda client: client.events().delete(calendarId=_calendar_id(), eventId=event_id))
