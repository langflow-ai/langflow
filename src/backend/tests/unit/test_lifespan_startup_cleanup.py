"""Regression test for issue #13634 (Bug 2): the masking ``UnboundLocalError``.

When startup fails before bundle loading assigns ``temp_dirs``, the shutdown
``finally`` block in ``lifespan`` iterates ``temp_dirs`` during temp-file cleanup.
Previously ``temp_dirs`` was only bound inside the ``try``, so an early failure
(such as an unresolvable ``LANGFLOW_DATABASE_URL``) caused the cleanup to raise
``UnboundLocalError: cannot access local variable 'temp_dirs'`` -- a second,
confusing error logged on top of the real one.

Binding ``temp_dirs = []`` before the ``try`` fixes this. This test drives the
real ``lifespan`` context manager with a failing ``initialize_services`` and
asserts the cleanup path no longer raises.

Issue: https://github.com/langflow-ai/langflow/issues/13634
"""

from unittest.mock import AsyncMock

import langflow.main as main_module
import pytest


async def test_startup_failure_does_not_mask_error_with_unbound_temp_dirs(monkeypatch):
    lifespan = main_module.get_lifespan()

    sentinel = RuntimeError("Error creating DB and tables")

    async def _failing_initialize_services(*_args, **_kwargs):
        raise sentinel

    telemetry_calls: list[tuple[str, str]] = []

    async def _record_telemetry(exc, context):
        telemetry_calls.append((context, type(exc).__name__))

    # Force an early startup failure (before bundle loading binds temp_dirs).
    monkeypatch.setattr(main_module, "initialize_services", _failing_initialize_services)
    # Capture both the primary failure and any secondary cleanup failure.
    monkeypatch.setattr(main_module, "log_exception_to_telemetry", _record_telemetry)
    # Replace destructive/heavy shutdown calls so the finally block runs in
    # isolation without tearing down services shared by the wider test session.
    monkeypatch.setattr(main_module, "teardown_services", AsyncMock())
    monkeypatch.setattr(main_module, "cleanup_mcp_sessions", AsyncMock())

    with pytest.raises(RuntimeError, match="Error creating DB and tables") as exc_info:
        async with lifespan(object()):
            pass

    # The real startup error propagates unchanged...
    assert exc_info.value is sentinel

    # ...and the shutdown cleanup itself did not raise. A crash inside the
    # ``finally`` block is reported via ``log_exception_to_telemetry`` under the
    # "lifespan_cleanup" context, so its absence proves temp_dirs was bound.
    cleanup_failures = [context for context, _ in telemetry_calls if context == "lifespan_cleanup"]
    assert cleanup_failures == [], f"shutdown cleanup raised during startup failure: {telemetry_calls}"
    assert ("lifespan_cleanup", "UnboundLocalError") not in telemetry_calls
