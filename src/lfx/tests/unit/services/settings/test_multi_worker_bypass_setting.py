"""Tests for ``dangerously_allow_multi_worker_without_shared_queue``.

The setting is the operator-facing half of the multi-worker guard enforced in
``langflow.__main__.ensure_multi_worker_safe``: it must be off unless explicitly
turned on, readable from the environment under its full deliberately-scary name,
and it must NOT change how ``event_delivery`` is resolved. That last point is the
subtle one — the bypass only stops the process from refusing to boot; forcing
``direct`` delivery is still the right call because the in-memory queue is still
worker-local, flag or no flag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.services.settings.base import Settings

if TYPE_CHECKING:
    import pytest

BYPASS_ENV_VAR = "LANGFLOW_DANGEROUSLY_ALLOW_MULTI_WORKER_WITHOUT_SHARED_QUEUE"


def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LANGFLOW_WORKERS", "LANGFLOW_JOB_QUEUE_TYPE", "LANGFLOW_EVENT_DELIVERY", BYPASS_ENV_VAR):
        monkeypatch.delenv(name, raising=False)


def test_bypass_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nobody gets the bypass by accident."""
    _isolate_env(monkeypatch)

    assert Settings().dangerously_allow_multi_worker_without_shared_queue is False


def test_bypass_reads_its_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented env var is what actually flips the setting."""
    _isolate_env(monkeypatch)
    monkeypatch.setenv(BYPASS_ENV_VAR, "true")

    assert Settings().dangerously_allow_multi_worker_without_shared_queue is True


def test_bypass_does_not_change_event_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bypass must not re-enable cross-worker polling/streaming delivery.

    The queue is still worker-local under the flag, so ``set_event_delivery``
    keeps forcing ``direct``; letting the flag leak into that validator would
    hand clients a delivery mode that fails ~half the time.
    """
    _isolate_env(monkeypatch)
    monkeypatch.setenv("LANGFLOW_WORKERS", "4")
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "asyncio")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "polling")
    monkeypatch.setenv(BYPASS_ENV_VAR, "true")

    settings = Settings()

    assert settings.dangerously_allow_multi_worker_without_shared_queue is True
    assert settings.event_delivery == "direct"
