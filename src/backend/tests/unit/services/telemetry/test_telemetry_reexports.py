"""Unit tests for the stable telemetry extension-point re-exports.

Verifies that enterprise consumers can import pop_all and append_run_event
from the stable langflow.services.telemetry package path and that the
functions are the same objects as those in the internal module.

These tests are the CI gate for the public API contract described in
run_event_store.py.  A rename, removal, or signature change in that
module will cause one of the assertions below to fail before any
enterprise consumer is broken.
"""

import inspect

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


# ---------------------------------------------------------------------------
# Public API contract — signature shape
# These break if a future refactor renames, removes, or changes the arity of
# the two stable extension-point functions.
# ---------------------------------------------------------------------------


def test_pop_all_takes_no_parameters():
    """pop_all() must remain a zero-argument callable (enterprise callers pass none)."""
    sig = inspect.signature(pop_all)
    assert list(sig.parameters.values()) == []


def test_append_run_event_accepts_single_payload_param():
    """append_run_event(payload) must keep exactly one required positional parameter."""
    sig = inspect.signature(append_run_event)
    assert list(sig.parameters) == ["payload"]
    payload_param = sig.parameters["payload"]
    assert payload_param.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert payload_param.default is inspect.Parameter.empty


def test_stable_import_path_resolves():
    """The documented import path must resolve without ImportError.

    This is a belt-and-suspenders guard: the import at the top of this
    module already exercises it, but an explicit assertion makes the
    intent clear to future maintainers.
    """
    import importlib

    mod = importlib.import_module("langflow.services.telemetry")
    assert callable(getattr(mod, "pop_all", None)), "pop_all missing from langflow.services.telemetry"
    assert callable(getattr(mod, "append_run_event", None)), "append_run_event missing from langflow.services.telemetry"


# ---------------------------------------------------------------------------
# Functional smoke-test
# ---------------------------------------------------------------------------


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
    assert drained[0].model_dump() == payload.model_dump()
    # store is empty after pop
    assert pop_all() == []
