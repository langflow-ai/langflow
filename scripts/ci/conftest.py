"""Provide deterministic clocks for tests of committed discovery-gate evidence."""

from datetime import UTC, date, datetime, tzinfo

import pytest


@pytest.fixture
def capability_reference_date(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> date:
    """Evaluate historical fixtures at a stable date without changing the production clock."""
    reference_date = getattr(request, "param", date(2026, 9, 30))

    class ReferenceDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            """Return the requested evidence date in the caller's timezone."""
            instant = datetime.combine(reference_date, datetime.min.time(), tzinfo=UTC)
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    monkeypatch.setattr("check_capability_matrices.datetime", ReferenceDateTime)
    monkeypatch.setattr("event_transport_matrix.datetime", ReferenceDateTime)
    return reference_date
