"""Background-execution settings defaults and env override."""

from __future__ import annotations

from lfx.services.settings.base import Settings


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
