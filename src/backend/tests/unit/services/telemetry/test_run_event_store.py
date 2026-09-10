"""Unit tests for the run event store (enterprise metering seam).

Testing library and framework: pytest
"""

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
