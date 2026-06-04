"""Tests for the best-effort background-execution metric emit helpers.

Two guarantees are exercised:

1. The swallow path: when the telemetry service is unavailable (a real runtime
   condition before the service manager is initialized), every ``emit_*`` helper
   must return without raising. The ``monkeypatch`` here only simulates the
   service being absent; it does not mock telemetry behavior under test.
2. The happy path: with the real telemetry service available, emitting reaches
   the real OpenTelemetry instrument without raising, and the registry accepts
   the labels we send (``validate_labels`` does not raise).
"""

from langflow.services.background_execution import metrics as bgm
from langflow.services.deps import get_telemetry_service


def test_emit_swallows_when_telemetry_missing(monkeypatch):
    """Every emit_* must swallow when the telemetry service cannot be resolved."""

    def _raise():
        msg = "no service"
        raise RuntimeError(msg)

    monkeypatch.setattr(bgm, "get_telemetry_service", _raise)

    # None of these may propagate the RuntimeError.
    bgm.emit_job_started(backend="default")
    bgm.emit_job_completed(backend="default")
    bgm.emit_job_failed(reason="error", backend="default")
    bgm.emit_orphan_reconciled(backend="default")
    bgm.emit_job_duration(seconds=1.0, outcome="completed", backend="default")


def test_emit_reaches_real_instrument():
    """With the real telemetry service, emitting does not raise and labels validate."""
    bgm.emit_job_started(backend="default")
    bgm.emit_job_completed(backend="default")
    bgm.emit_job_failed(reason="error", backend="default")
    bgm.emit_orphan_reconciled(backend="default")
    bgm.emit_job_duration(seconds=1.0, outcome="completed", backend="default")

    # The labels each helper sends must be accepted by the real registry.
    ot = get_telemetry_service().ot
    ot.validate_labels("langflow_bg_jobs_started_total", {"backend": "default"})
    ot.validate_labels("langflow_bg_jobs_completed_total", {"backend": "default"})
    ot.validate_labels("langflow_bg_jobs_failed_total", {"reason": "error", "backend": "default"})
    ot.validate_labels("langflow_bg_orphans_reconciled_total", {"backend": "default"})
    ot.validate_labels("langflow_bg_job_duration_seconds", {"outcome": "completed", "backend": "default"})
