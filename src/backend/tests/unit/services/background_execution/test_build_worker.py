"""build_worker wires the DB backend + WorkerJobRunner from live services."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from zipfile import ZipFile

import httpx
import pytest
from langflow.services.background_execution.db_backend import DBBackgroundQueue
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.worker import WorkerJobRunner, build_worker
from langflow.services.deps import get_job_service, get_settings_service
from lfx.interface import components

pytestmark = pytest.mark.usefixtures("client")


async def test_build_worker_returns_backend_runner_and_teardown():
    backend, runner, teardown = await build_worker(owner="worker:test")
    try:
        assert isinstance(backend, DBBackgroundQueue)
        assert isinstance(runner, WorkerJobRunner)
        assert callable(teardown)
        # The backend claims off the live job service (the shared database is
        # the queue), and the runner's bus is process-local — durable milestones
        # in job_events are the cross-replica transport.
        assert backend._job_service is get_job_service()
        assert isinstance(runner._live_bus, InMemoryLiveBus)
        assert backend._owner == "worker:test"
    finally:
        await teardown()


@pytest.mark.parametrize("startup_fails", [False, True])
async def test_worker_loads_bundle_components_and_releases_its_paths(monkeypatch, startup_fails):
    from langflow.initial_setup import setup

    settings_service = get_settings_service()
    settings = settings_service.settings
    previous_paths = list(settings.components_path)
    monkeypatch.setattr(settings, "bundle_urls", ["https://example.test/components.zip"])
    archive = BytesIO()
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("bundle/", "")
        bundle.writestr("bundle/components/custom.py", "# component fixture")
        bundle.writestr("bundle/flows/unused.json", "{}")
    client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=archive.getvalue()))
    monkeypatch.setattr(setup.httpx, "AsyncClient", lambda **kwargs: client(transport=transport, **kwargs))
    lookup_owner = AsyncMock()
    import_flow = AsyncMock()
    monkeypatch.setattr(setup, "_get_flow_import_superuser", lookup_owner)
    monkeypatch.setattr(setup, "upsert_flow_from_file", import_flow)
    loaded = []
    failure_message = "registry failed"

    async def load_registry(service, _telemetry):
        assert service is settings_service
        component_dir = Path(settings.components_path[-1])
        assert (component_dir / "custom.py").is_file()
        loaded.append(component_dir)
        if startup_fails:
            raise RuntimeError(failure_message)

    monkeypatch.setattr(components, "get_and_cache_all_types_dict", load_registry)
    if startup_fails:
        with pytest.raises(RuntimeError, match=failure_message):
            await build_worker()
    else:
        _, _, teardown = await build_worker()
        try:
            assert loaded[0].is_dir()
        finally:
            await teardown()
    assert settings.components_path == previous_paths
    assert not loaded[0].exists()
    lookup_owner.assert_not_awaited()
    import_flow.assert_not_awaited()
