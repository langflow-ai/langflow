"""Unit tests for the stable telemetry extension-point re-exports.

Verifies that enterprise consumers can import pop_all and append_run_event
from the stable langflow.services.telemetry package path and that the
functions are the same objects as those in the internal module.
"""

from langflow.services import telemetry as telemetry_pkg
from langflow.services.telemetry import append_run_event, pop_all
from langflow.services.telemetry import run_event_store as _store


def test_pop_all_reexported_from_package():
    assert pop_all is _store.pop_all


def test_append_run_event_reexported_from_package():
    assert append_run_event is _store.append_run_event


def test_reexports_present_in_all():
    assert "pop_all" in telemetry_pkg.__all__
    assert "append_run_event" in telemetry_pkg.__all__


def test_append_then_pop_roundtrip():
    """Functional smoke-test through the re-exported symbols."""
    # drain any leftover state from other tests
    pop_all()

    from langflow.services.telemetry.schema import RunPayload

    payload = RunPayload(
        run_seconds=1,
        run_success=True,
    )
    append_run_event(payload)
    drained = pop_all()

    assert len(drained) == 1
    assert drained[0] is payload
    # store is empty after pop
    assert pop_all() == []
