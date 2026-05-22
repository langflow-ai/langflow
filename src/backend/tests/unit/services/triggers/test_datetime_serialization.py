"""Tests for UTC normalization at the triggers HTTP boundary.

SQLite drops the tzinfo of ``DateTime(timezone=True)`` columns on
read, so naive datetimes can leak into the API layer. Both the
manual aggregator serializer (``_iso``) and the SQLModel
``TriggerJobRead`` must coerce them to UTC-aware ISO strings so the
browser does not interpret them in its local timezone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from langflow.api.v1.triggers import _iso
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.model import TriggerJobRead


def test_iso_emits_utc_offset_for_aware_datetime():
    value = datetime(2026, 5, 22, 0, 44, 0, tzinfo=timezone.utc)
    assert _iso(value) == "2026-05-22T00:44:00+00:00"


def test_iso_treats_naive_datetime_as_utc():
    value = datetime(2026, 5, 22, 0, 44, 0)  # noqa: DTZ001 — simulates SQLite read
    assert _iso(value) == "2026-05-22T00:44:00+00:00"


def test_iso_returns_none_for_missing_value():
    assert _iso(None) is None


def _job_read(**overrides) -> TriggerJobRead:
    base = {
        "id": uuid4(),
        "flow_id": uuid4(),
        "component_id": "CronTrigger-x",
        "status": JobStatus.COMPLETED,
        "scheduled_at": datetime(2026, 5, 22, 0, 44, 0),  # noqa: DTZ001
        "started_at": None,
        "finished_at": None,
        "attempt": 1,
        "max_attempts": 3,
        "error": None,
        "run_job_id": None,
        "created_at": datetime(2026, 5, 22, 0, 43, 0),  # noqa: DTZ001
    }
    base.update(overrides)
    return TriggerJobRead(**base)


def test_trigger_job_read_serializes_naive_datetime_as_utc():
    dumped = _job_read().model_dump(mode="json")
    assert dumped["scheduled_at"] == "2026-05-22T00:44:00+00:00"
    assert dumped["created_at"] == "2026-05-22T00:43:00+00:00"
    assert dumped["started_at"] is None
    assert dumped["finished_at"] is None


def test_trigger_job_read_preserves_aware_datetime():
    aware = datetime(2026, 5, 22, 3, 44, 0, tzinfo=timezone.utc)
    dumped = _job_read(scheduled_at=aware).model_dump(mode="json")
    assert dumped["scheduled_at"] == "2026-05-22T03:44:00+00:00"
