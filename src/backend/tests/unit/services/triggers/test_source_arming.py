"""Source connections accept the scopes their provider APIs allow."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.triggers.source_arming import SourceArming, check_ready


@pytest.mark.parametrize(
    ("kind", "scope"),
    [
        ("microsoft.calendar", "Calendars.ReadWrite"),
        ("microsoft.calendar", "https://graph.microsoft.com/Calendars.ReadWrite"),
        ("google.calendar", "https://www.googleapis.com/auth/calendar.events"),
    ],
)
async def test_calendar_write_scope_allows_read_source(kind: str, scope: str) -> None:
    connection = SimpleNamespace(status="ready", allow_non_interactive=True, granted_scopes=[scope])

    class Session:
        async def get(self, _model, _connection_id):
            return connection

    await check_ready(Session(), kind=kind, arming=SourceArming(connection_id=uuid4(), mechanism_id="poll"))


async def test_unrelated_scope_does_not_allow_calendar_source() -> None:
    connection = SimpleNamespace(status="ready", allow_non_interactive=True, granted_scopes=["Mail.ReadWrite"])

    class Session:
        async def get(self, _model, _connection_id):
            return connection

    with pytest.raises(ValueError, match=r"missing required scopes: Calendars\.Read"):
        await check_ready(
            Session(), kind="microsoft.calendar", arming=SourceArming(connection_id=uuid4(), mechanism_id="poll")
        )
