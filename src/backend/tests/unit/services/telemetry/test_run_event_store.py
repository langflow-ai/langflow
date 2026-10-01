"""Unit tests for the run event store (enterprise metering seam).

Testing library and framework: pytest
"""

from datetime import datetime, timezone

import pytest
from langflow.services.telemetry import run_event_store
from langflow.services.telemetry.run_event_store import append_run_event, peek_all, pop_all
from langflow.services.telemetry.schema import RunPayload


@pytest.fixture(autouse=True)
def _drain_store():
    """Isolate each test from events other tests (or fixtures) appended."""
    pop_all()
    yield
    pop_all()


def _payload(run_id: str) -> RunPayload:
    return RunPayload(run_seconds=1, run_success=True, run_id=run_id)


def test_append_and_pop_roundtrip():
    p = _payload("r1")
    append_run_event(p)
    assert pop_all() == [p]


def test_pop_all_drains():
    append_run_event(_payload("r1"))
    append_run_event(_payload("r2"))
    assert len(pop_all()) == 2
    assert pop_all() == []


def test_pop_all_preserves_order():
    first, second = _payload("r1"), _payload("r2")
    append_run_event(first)
    append_run_event(second)
    assert pop_all() == [first, second]


def test_peek_all_is_nondestructive():
    p = _payload("r1")
    append_run_event(p)
    assert peek_all() == [p]
    assert peek_all() == [p]
    assert pop_all() == [p]


def test_bound_discards_oldest(monkeypatch):
    monkeypatch.setattr(run_event_store, "_MAX_EVENTS", 3)
    for i in range(5):
        append_run_event(_payload(f"r{i}"))
    kept = pop_all()
    assert [p.run_id for p in kept] == ["r2", "r3", "r4"]


def test_completion_time_is_captured_when_recorded(monkeypatch):
    payload = _payload("before-midnight")
    completed_at = datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc)

    class CompletionClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return completed_at.astimezone(tz)

    monkeypatch.setattr(run_event_store, "datetime", CompletionClock)
    append_run_event(payload)
    assert pop_all()[0].run_completed_at == completed_at


def test_existing_completion_time_survives_repeated_append():
    completed_at = datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc)
    payload = RunPayload(run_seconds=2, run_success=True, run_completed_at=completed_at)
    append_run_event(payload)
    append_run_event(payload)
    assert all(event.run_completed_at == completed_at for event in pop_all())


def test_completion_time_is_not_sent_in_outbound_telemetry():
    payload = _payload("internal-time")
    before = payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
    append_run_event(payload)
    recorded = pop_all()[0]
    assert recorded.run_completed_at is not None
    assert recorded.model_dump(by_alias=True, exclude_none=True, exclude_unset=True) == before


def test_completion_time_requires_a_timezone():
    naive_completion = datetime(2026, 9, 14)  # noqa: DTZ001 - deliberately invalid input
    with pytest.raises(ValueError, match="timezone"):
        RunPayload(run_seconds=1, run_success=True, run_completed_at=naive_completion)
