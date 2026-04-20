"""Unit tests for the gunicorn post_fork hook + TelemetryService None-guards."""

from __future__ import annotations

import asyncio
import os
import tempfile

import httpx
import pytest
from langflow.server import _langflow_post_fork
from langflow.services.telemetry.service import TelemetryService


@pytest.fixture
def telemetry_service():
    """Construct a real TelemetryService with a real SettingsService.

    Uses a temporary config directory so AuthSettings validation passes
    without touching the real filesystem.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ.setdefault("LANGFLOW_CONFIG_DIR", tmpdir)
        from lfx.services.settings.auth import AuthSettings
        from lfx.services.settings.base import Settings
        from lfx.services.settings.service import SettingsService

        settings = Settings()
        auth_settings = AuthSettings()
        settings_service = SettingsService(settings=settings, auth_settings=auth_settings)

        service = TelemetryService(settings_service=settings_service)
        # Force do_not_track off: we are exercising the client-reconstruction
        # path, not the do-not-track short-circuit.
        service.do_not_track = False
        yield service
        # Cleanup: if start was called, stop it to release resources.
        if service.running:
            asyncio.run(service.stop())


def test_post_fork_resets_telemetry_client(monkeypatch, telemetry_service):
    """_langflow_post_fork must set TelemetryService.client to None.

    + RESEARCH.md 'Fork Hazard Audit -> 4. Redis / httpx connection pools'.
    """
    import langflow.services.deps as deps_module

    monkeypatch.setattr(deps_module, "get_telemetry_service", lambda: telemetry_service)

    assert telemetry_service.client is not None
    assert isinstance(telemetry_service.client, httpx.AsyncClient)

    _langflow_post_fork(None, None)

    assert telemetry_service.client is None


def test_start_reconstructs_client_when_none(telemetry_service):
    """TelemetryService.start() must reconstruct self.client when it is None.

    Simulates the worker-side sequence: master constructs service, post_fork
    resets client to None, lifespan calls start() which must bring the client
    back.
    """
    telemetry_service.client = None

    async def _run():
        telemetry_service.start()
        # Allow start's create_task calls to schedule.
        await asyncio.sleep(0)
        assert telemetry_service.client is not None
        assert isinstance(telemetry_service.client, httpx.AsyncClient)
        await telemetry_service.stop()

    asyncio.run(_run())
