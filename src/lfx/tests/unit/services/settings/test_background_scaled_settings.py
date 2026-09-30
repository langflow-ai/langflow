"""Scaled-backend settings: test-redis URL + backend selection follows job_queue_type."""

from __future__ import annotations

from lfx.services.settings.base import Settings


def test_test_redis_url_defaults_none():
    settings = Settings()
    assert settings.test_redis_url is None


def test_test_redis_url_reads_env(monkeypatch):
    monkeypatch.setenv("LANGFLOW_TEST_REDIS_URL", "redis://localhost:6379/15")
    settings = Settings()
    assert settings.test_redis_url == "redis://localhost:6379/15"


def test_scaled_backend_follows_job_queue_type(monkeypatch):
    # redis job_queue_type => scaled background backend is selected.
    # Settings reads job_queue_type from the env (CustomSource drops init kwargs),
    # so drive the selection through LANGFLOW_JOB_QUEUE_TYPE the way deploys do.
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "redis")
    assert Settings().background_backend_is_scaled is True

    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "asyncio")
    assert Settings().background_backend_is_scaled is False
