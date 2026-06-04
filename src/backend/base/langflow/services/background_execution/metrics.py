"""Best-effort metric emission for background execution. Never raises into the runner."""

from __future__ import annotations

from lfx.log.logger import logger

from langflow.services.deps import get_telemetry_service


def current_backend() -> str:
    """Best-effort: 'scaled' when the redis job queue is active, else 'default'. Never raises."""
    try:
        from langflow.services.deps import get_settings_service

        return "scaled" if get_settings_service().settings.background_backend_is_scaled else "default"
    except Exception:  # noqa: BLE001
        return "default"


def _emit(fn_name: str, name: str, labels: dict, value: float | None = None) -> None:
    try:
        ot = get_telemetry_service().ot
        fn = getattr(ot, fn_name)
        if value is None:
            fn(name, labels)
        else:
            fn(name, value, labels)
    except Exception as exc:  # noqa: BLE001 - observability must never break execution
        logger.debug(f"bg metric emit skipped ({name}): {exc}")


def emit_job_started(*, backend: str) -> None:
    _emit("increment_counter", "langflow_bg_jobs_started_total", {"backend": backend})


def emit_job_completed(*, backend: str) -> None:
    _emit("increment_counter", "langflow_bg_jobs_completed_total", {"backend": backend})


def emit_job_failed(*, reason: str, backend: str) -> None:
    _emit("increment_counter", "langflow_bg_jobs_failed_total", {"reason": reason, "backend": backend})


def emit_orphan_reconciled(*, backend: str) -> None:
    _emit("increment_counter", "langflow_bg_orphans_reconciled_total", {"backend": backend})


def emit_job_duration(*, seconds: float, outcome: str, backend: str) -> None:
    _emit(
        "observe_histogram",
        "langflow_bg_job_duration_seconds",
        {"outcome": outcome, "backend": backend},
        value=seconds,
    )
