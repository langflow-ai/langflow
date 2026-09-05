"""Opt-in read-only suite against a real Microsoft Graph tenant.

Deselected in CI by the ``api_key_required`` marker and skipped entirely unless
a token is supplied. To run it, export a delegated access token that carries
``Mail.Read``, ``Calendars.Read`` and ``Files.Read``::

    export LF_CONNECTION__MICROSOFT__LIVE='{"access_token":"<token>",
        "scopes":["Mail.Read","Calendars.Read","Files.Read"]}'
    uv run pytest src/bundles/microsoft/tests/test_live_graph.py -m api_key_required

Only read actions run here. Nothing sends mail, posts to Teams, or writes a
calendar event.

The assertions pin the *shape* Graph returns, not tenant contents: a live
tenant may legitimately hold zero messages, zero events and an empty drive, so
each test asserts that whatever comes back is a list of Data rows carrying the
driveItem/message/event identity fields the downstream components read.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from lfx.integrations.models import ConnectionRef
from lfx.schema.data import Data
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_microsoft import OutlookCalendarListComponent, OutlookSearchComponent, SharePointListComponent
from microsoft_testkit import stub_graph

LIVE_ENV_KEY = ConnectionRef(provider="microsoft", name="live").env_key()

pytestmark = [
    pytest.mark.api_key_required,
    pytest.mark.skipif(
        not os.getenv(LIVE_ENV_KEY),
        reason=f"set {LIVE_ENV_KEY} to a delegated Graph credential to run the live suite",
    ),
]


def _assert_graph_rows(rows, required_keys: set[str]) -> None:
    """Assert the rows are Data with Graph identity fields, tolerating an empty tenant."""
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, Data)
        assert isinstance(row.data, dict)
        assert required_keys <= set(row.data), f"missing {required_keys - set(row.data)}"


def _live(component_class, **inputs):
    """Build a component that talks to the real Graph endpoint."""
    component = component_class(connection="microsoft/live", **inputs)
    component._vertex = SimpleNamespace(graph=stub_graph(ExecutionPrincipal(kind="headless_operator")))
    return component


async def test_live_outlook_search_returns_messages() -> None:
    component = _live(OutlookSearchComponent, top=1)
    rows = await component.search_messages()
    _assert_graph_rows(rows, {"id", "subject"})


async def test_live_calendar_list_returns_a_window() -> None:
    now = datetime.now(timezone.utc)
    component = _live(
        OutlookCalendarListComponent,
        start_time=now.isoformat(timespec="seconds"),
        end_time=(now + timedelta(days=1)).isoformat(timespec="seconds"),
        top=1,
    )
    rows = await component.list_events()
    _assert_graph_rows(rows, {"id", "start", "end"})


async def test_live_onedrive_root_listing() -> None:
    component = _live(SharePointListComponent, top=1)
    rows = await component.list_items()
    _assert_graph_rows(rows, {"id", "name"})
