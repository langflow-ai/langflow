"""Tests for the multi-worker fallback in Settings.set_event_delivery.

A deployment that sets ``workers > 1`` without configuring a Redis-backed
job queue cannot deliver ``polling`` or ``streaming`` events across workers
(events live in the in-process queue of whichever worker started the
build).  The validator silently flips event_delivery to ``direct`` in that
case — but the log message must spell out the requested mode, the forced
fallback, and how to keep the original mode (LANGFLOW_JOB_QUEUE_TYPE=redis)
so a user diagnosing missing events can fix it without spelunking source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.settings.base import Settings

if TYPE_CHECKING:
    import pytest


def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all env vars the validator inspects so tests are deterministic."""
    for name in ("LANGFLOW_WORKERS", "LANGFLOW_JOB_QUEUE_TYPE", "LANGFLOW_EVENT_DELIVERY"):
        monkeypatch.delenv(name, raising=False)


def _capture_warnings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Capture warnings the settings validator emits.

    Settings uses ``lfx.log.logger.logger`` (a structlog BoundLogger that may
    be filtered at the configured log level).  ``set_event_delivery`` lives in
    the ``RuntimeSettings`` mixin, so replace the module-level ``logger`` symbol
    in ``lfx.services.settings.groups.runtime`` with a tiny stand-in that records
    ``warning`` calls so the test inspects exactly the messages the validator
    emits, regardless of structlog's filter level.
    """
    captured: list[str] = []

    class _Recorder:
        def warning(self, msg: str, *args: object, **_kwargs: object) -> None:
            captured.append(msg % args if args else msg)

        def __getattr__(self, _name: str):  # pragma: no cover - swallow other levels
            return lambda *_a, **_k: None

    import lfx.services.settings.groups.runtime as settings_runtime

    monkeypatch.setattr(settings_runtime, "logger", _Recorder())
    return captured


def test_multi_worker_without_redis_forces_direct_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """With workers=2 and the in-memory job queue, polling is rewritten to direct."""
    _isolate_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_WORKERS", "2")
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "asyncio")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "polling")

    warnings = _capture_warnings(monkeypatch)
    settings = Settings()

    assert settings.event_delivery == "direct"
    combined = " ".join(warnings)
    # The warning must name BOTH the requested mode and the env var users need
    # to set to keep that mode — without these, the operator has no way to
    # connect a missing-events symptom to the root cause.
    assert "polling" in combined
    assert "LANGFLOW_JOB_QUEUE_TYPE" in combined


def test_multi_worker_with_redis_keeps_requested_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """With workers=2 and job_queue_type=redis, the requested delivery is preserved."""
    _isolate_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_WORKERS", "2")
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "redis")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "streaming")

    settings = Settings()

    assert settings.event_delivery == "streaming"


def test_single_worker_keeps_requested_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """The override only applies when workers > 1 — single-worker setups are left alone."""
    _isolate_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_WORKERS", "1")
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "asyncio")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "polling")

    settings = Settings()

    assert settings.event_delivery == "polling"


def test_multi_worker_no_warning_when_already_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the operator already set event_delivery=direct, no warning fires.

    The warning exists to flag a silent override; if the configured value is
    already the forced fallback, there is nothing to flag.
    """
    _isolate_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_WORKERS", "2")
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "asyncio")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "direct")

    warnings = _capture_warnings(monkeypatch)
    settings = Settings()

    assert settings.event_delivery == "direct"
    combined = " ".join(warnings)
    assert "LANGFLOW_JOB_QUEUE_TYPE" not in combined
