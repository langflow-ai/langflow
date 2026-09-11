"""Scaled-backend settings: explicit background_backend selection, decoupled from job_queue_type."""

from __future__ import annotations

from lfx.services.settings.base import Settings


def test_background_backend_defaults_to_default():
    settings = Settings()
    assert settings.background_backend == "default"
    assert settings.background_backend_is_scaled is False


def test_scaled_backend_follows_background_backend(monkeypatch):
    # Settings reads from the env (CustomSource drops init kwargs), so drive the
    # selection through LANGFLOW_BACKGROUND_BACKEND the way deploys do.
    monkeypatch.setenv("LANGFLOW_BACKGROUND_BACKEND", "scaled")
    assert Settings().background_backend_is_scaled is True

    monkeypatch.setenv("LANGFLOW_BACKGROUND_BACKEND", "default")
    assert Settings().background_backend_is_scaled is False


def test_scaled_selection_is_independent_of_job_queue_type(monkeypatch):
    # A redis v1 job queue no longer implies the scaled background backend: the
    # database is the queue, redis presence is irrelevant to it.
    monkeypatch.setenv("LANGFLOW_JOB_QUEUE_TYPE", "redis")
    assert Settings().background_backend_is_scaled is False


def test_background_poll_interval_default(monkeypatch):
    assert Settings().background_poll_interval_s == 0.5
    monkeypatch.setenv("LANGFLOW_BACKGROUND_POLL_INTERVAL_S", "0.1")
    assert Settings().background_poll_interval_s == 0.1
