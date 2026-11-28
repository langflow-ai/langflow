"""Background-execution settings defaults and env override."""

from __future__ import annotations

import pytest
from lfx.services.settings.base import Settings
from pydantic import ValidationError


def test_background_max_concurrency_default():
    settings = Settings()
    assert settings.background_max_concurrency == 5


def test_background_job_timeout_default_is_none():
    settings = Settings()
    assert settings.background_job_timeout is None


def test_background_max_concurrency_env_override(monkeypatch):
    monkeypatch.setenv("LANGFLOW_BACKGROUND_MAX_CONCURRENCY", "12")
    settings = Settings()
    assert settings.background_max_concurrency == 12


def test_background_job_timeout_env_override(monkeypatch):
    monkeypatch.setenv("LANGFLOW_BACKGROUND_JOB_TIMEOUT", "600")
    settings = Settings()
    assert settings.background_job_timeout == 600


def test_background_shutdown_grace_default_cancels_at_once():
    settings = Settings()
    assert settings.background_shutdown_grace_s == 0


def test_background_shutdown_grace_env_override(monkeypatch):
    monkeypatch.setenv("LANGFLOW_BACKGROUND_SHUTDOWN_GRACE_S", "2.5")
    settings = Settings()
    assert settings.background_shutdown_grace_s == 2.5


def test_background_shutdown_grace_refuses_a_negative_value(monkeypatch):
    monkeypatch.setenv("LANGFLOW_BACKGROUND_SHUTDOWN_GRACE_S", "-1")
    with pytest.raises(ValidationError):
        Settings()
