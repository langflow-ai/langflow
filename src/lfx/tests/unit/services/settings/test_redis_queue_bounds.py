"""Validation tests for the Redis job-queue timing settings.

These settings drive cross-worker cancel, the cancel-marker race fix, and the
polling watchdog. Bad env values would silently re-open the races those
features were added to close, so Pydantic must reject them at config load.
"""

import pytest
from lfx.services.settings.base import Settings
from pydantic import ValidationError


def test_redis_queue_startup_grace_s_rejects_negative(monkeypatch):
    """Negative grace would make remote consumers treat a not-yet-created stream as EOF."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_STARTUP_GRACE_S", "-1")
    with pytest.raises(ValidationError):
        Settings()


def test_redis_queue_startup_grace_s_accepts_zero(monkeypatch):
    """Zero is a valid (very strict) setting and must not be rejected."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_STARTUP_GRACE_S", "0")
    settings = Settings()
    assert settings.redis_queue_startup_grace_s == 0


def test_redis_queue_cancel_marker_ttl_rejects_zero(monkeypatch):
    """A zero TTL would make the marker key invalid and reopen the publish-before-subscribe race."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_CANCEL_MARKER_TTL", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_redis_queue_cancel_marker_ttl_rejects_negative(monkeypatch):
    """Negative TTLs are invalid in Redis."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_CANCEL_MARKER_TTL", "-1")
    with pytest.raises(ValidationError):
        Settings()


def test_redis_queue_polling_watchdog_interval_s_rejects_zero(monkeypatch):
    """Zero interval would spin the scan loop with no progress."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_POLLING_WATCHDOG_INTERVAL_S", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_redis_queue_polling_stale_threshold_s_rejects_negative(monkeypatch):
    """Negative threshold is meaningless; 0 is the documented disable switch."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_POLLING_STALE_THRESHOLD_S", "-1")
    with pytest.raises(ValidationError):
        Settings()


def test_redis_queue_polling_stale_threshold_s_accepts_zero(monkeypatch):
    """0 explicitly disables the watchdog and must remain a valid setting."""
    monkeypatch.setenv("LANGFLOW_REDIS_QUEUE_POLLING_STALE_THRESHOLD_S", "0")
    settings = Settings()
    assert settings.redis_queue_polling_stale_threshold_s == 0
