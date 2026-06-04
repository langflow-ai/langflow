"""The facade factory selects the scaled redis backend when configured."""

from __future__ import annotations

import pytest
from langflow.services.background_execution.factory import select_background_backend
from langflow.services.background_execution.redis_backend import RedisBackgroundQueue
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service


def test_factory_selects_scaled_backend_when_configured():
    class _Settings:
        background_backend_is_scaled = True

    backend = select_background_backend(_Settings(), client=object(), job_service=object())
    assert isinstance(backend, RedisBackgroundQueue)


def test_factory_returns_none_for_default_backend():
    class _Settings:
        background_backend_is_scaled = False

    # The default (in-process) backend is owned by the facade itself, so the
    # selector returns None: "no scaled backend, use the in-process path".
    backend = select_background_backend(_Settings(), client=object(), job_service=object())
    assert backend is None


@pytest.mark.usefixtures("client")
def test_facade_builds_scaled_backend_from_settings():
    settings_service = get_settings_service()
    settings = settings_service.settings
    original = settings.job_queue_type
    try:
        # Default (asyncio): no scaled backend behind the facade.
        settings.job_queue_type = "asyncio"
        default_facade = BackgroundExecutionService(settings_service=settings_service)
        assert default_facade._scaled is False

        # Scaled (redis): the facade builds the redis backend itself.
        settings.job_queue_type = "redis"
        scaled_facade = BackgroundExecutionService(settings_service=settings_service)
        assert scaled_facade._scaled is True
        assert isinstance(scaled_facade._backend, RedisBackgroundQueue)
    finally:
        settings.job_queue_type = original
