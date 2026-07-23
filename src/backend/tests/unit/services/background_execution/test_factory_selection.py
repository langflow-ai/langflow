"""The facade factory selects the scaled DB backend when configured."""

from __future__ import annotations

import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.background_execution.factory import select_background_backend
from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.deps import get_settings_service


class _ScaledSettings:
    background_backend_is_scaled = True
    background_lease_ttl_s = 45.0
    background_poll_interval_s = 0.5


class _DefaultSettings:
    background_backend_is_scaled = False


def test_factory_selects_scaled_backend_when_configured():
    backend = select_background_backend(_ScaledSettings(), job_service=object(), owner="worker:test")
    assert isinstance(backend, DBBackgroundQueue)
    assert backend._owner == "worker:test"


def test_factory_returns_none_for_default_backend():
    # The default (in-process) backend is owned by the facade itself, so the
    # selector returns None: "no scaled backend, use the in-process path".
    backend = select_background_backend(_DefaultSettings(), job_service=object())
    assert backend is None


@pytest.mark.usefixtures("client")
def test_facade_builds_scaled_backend_from_settings():
    settings_service = get_settings_service()
    settings = settings_service.settings
    original = settings.background_backend
    try:
        # Default: no scaled backend behind the facade.
        settings.background_backend = "default"
        default_facade = BackgroundExecutionService(settings_service=settings_service)
        assert default_facade._scaled is False

        # Scaled: the facade builds the DB backend itself.
        settings.background_backend = "scaled"
        scaled_facade = BackgroundExecutionService(settings_service=settings_service)
        assert scaled_facade._scaled is True
        assert isinstance(scaled_facade._backend, DBBackgroundQueue)
    finally:
        settings.background_backend = original
