"""LE-3302 F-02 / F-03: a v1 /run job row's status and its heartbeat under load.

A v1 ``POST /api/v1/run/{flow_id}`` executes IN the API process. Its ``job`` row is only a
tracking handle (memory-base ``on_flow_output`` + status/stop isolation), not work for a
``langflow worker`` to pick up.

F-02: ``simple_run_flow`` created that row with ``create_job``'s default ``QUEUED`` status
and let ``execute_with_status`` flip it to IN_PROGRESS later. In the window between, a scaled
worker's reconcile path lists QUEUED WORKFLOW rows (``queued_workflow_job_ids``) and
lease-claims the ones whose create-time heartbeat has gone stale (``claim_queued_lease``),
then reconstructs an EMPTY request (the v1 row stores none) and re-runs the flow with ``""``:
the caller gets HTTP 500 and its input never runs, or the job runs twice. Fix: create the row
already IN_PROGRESS (``status=JobStatus.IN_PROGRESS``). An IN_PROGRESS row is never in the
QUEUED-claim path, so no worker can take it. ``mark_in_progress`` stays default True so
``begin_live_job``'s terminal-status guard still runs.

F-03: under DB connection-pool exhaustion the in-process keep-alive couldn't get a connection
to refresh the heartbeat, so a live run's lease went stale and ``sweep_orphans`` reaped it
``worker_lost`` though it completed and returned 200. Fix: the heartbeat (``JobService._beat``)
runs on a dedicated small pool (``DatabaseService.session_scope_for_heartbeat``) isolated from
the application pool, so a saturated request pool no longer starves it.

Drives the REAL job-service claim/reap primitives against real SQLite AND real Postgres. No
mocks: ``queued_workflow_job_ids`` + ``claim_queued_lease`` are the exact primitives the worker
reconcile uses (background_execution/service.py:938-945), ``sweep_orphans`` is the exact
watchdog reaper, and the F-03 test exhausts a real pool.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langflow.services.database.models.jobs.model import JobStatus, JobType

# Short lease like Rafael's run #899 (LANGFLOW_BACKGROUND_LEASE_TTL_S=2): the window a
# slow API leaves open. The bug is timing-sensitive, so the test ages the heartbeat past
# the lease deterministically instead of racing a real wall-clock delay.
LEASE_TTL_S = 2.0


async def _expire_lease(service, job_id):
    """Age the row's heartbeat well past the lease — the API was slow to start the run."""
    stale = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    await service.update_job_metadata(job_id, {"owner": "api", "heartbeat_at": stale})


@pytest.mark.real_services
async def test_pre_fix_queued_v1_row_is_claimed_by_a_worker(real_services_job_service):
    """REPRO F-02: the old QUEUED v1 row is listed and lease-claimed by a worker."""
    service = real_services_job_service
    job_id = uuid4()
    # Exactly how simple_run_flow created the row BEFORE the fix: QUEUED (create_job's
    # default), inserted already heartbeated.
    await service.create_job(
        job_id=job_id,
        flow_id=uuid4(),
        user_id=uuid4(),
        job_type=JobType.WORKFLOW,
        heartbeat=True,
    )
    await _expire_lease(service, job_id)

    # The scaled worker's reconcile path (background_execution/service.py:938-945).
    assert job_id in await service.queued_workflow_job_ids()
    claimed = await service.claim_queued_lease(
        job_id,
        owner="worker-1",
        lease_ttl_s=LEASE_TTL_S,
        heartbeat_at=datetime.now(timezone.utc).isoformat(),
    )
    # BUG: a worker takes a run the API owns -> it reruns the flow with an empty request.
    assert claimed is True


@pytest.mark.real_services
async def test_fixed_in_progress_v1_row_is_invisible_to_a_worker(real_services_job_service):
    """FIX F-02: the IN_PROGRESS row is never in the QUEUED-claim path, even stale."""
    service = real_services_job_service
    job_id = uuid4()
    # Exactly how simple_run_flow creates the row AFTER the fix.
    await service.create_job(
        job_id=job_id,
        flow_id=uuid4(),
        user_id=uuid4(),
        job_type=JobType.WORKFLOW,
        status=JobStatus.IN_PROGRESS,
        heartbeat=True,
    )
    await _expire_lease(service, job_id)

    # Even with the lease expired, there is no QUEUED row for a worker to see or claim.
    assert job_id not in await service.queued_workflow_job_ids()
    claimed = await service.claim_queued_lease(
        job_id,
        owner="worker-1",
        lease_ttl_s=LEASE_TTL_S,
        heartbeat_at=datetime.now(timezone.utc).isoformat(),
    )
    assert claimed is False


@pytest.mark.real_services
async def test_sweep_still_reaps_a_genuinely_dead_run(real_services_job_service):
    """Unchanged, correct behavior: a run whose heartbeat really stopped is still reaped.

    The F-03 fix keeps a LIVE run's heartbeat alive under load; it must not stop the sweep
    from failing a GENUINELY dead run (a crashed process never refreshes its heartbeat).
    """
    service = real_services_job_service
    job_id = uuid4()
    await service.create_job(
        job_id=job_id,
        flow_id=uuid4(),
        user_id=uuid4(),
        job_type=JobType.WORKFLOW,
        status=JobStatus.IN_PROGRESS,
        heartbeat=True,
    )
    # The process died: nothing refreshes the heartbeat, so it ages past the lease.
    await _expire_lease(service, job_id)

    swept = await service.sweep_orphans(lease_ttl_s=LEASE_TTL_S)

    assert job_id in swept
    job = await service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.FAILED
    assert (job.error or {}).get("type") == "worker_lost"


@pytest.mark.real_services
async def test_f03_heartbeat_survives_main_pool_exhaustion(real_services_job_service, real_services_db_url):
    """FIX F-03: a heartbeat lands even when the whole application pool is checked out.

    Postgres only: the bug is application-pool exhaustion, and in-memory SQLite falls back to
    the shared session by design. Builds a DatabaseService whose MAIN pool is a single
    connection, holds that one connection, then beats: the dedicated heartbeat pool
    (session_scope_for_heartbeat) must still refresh the row. Before the fix, _beat ran on the
    held main pool and the beat would time out (silently, under _beat's suppress), leaving the
    heartbeat stale for the sweep to reap.
    """
    if not real_services_db_url.startswith("postgresql"):
        pytest.skip("application-pool exhaustion is a Postgres concern; SQLite falls back")

    from langflow.services.database.factory import DatabaseServiceFactory
    from langflow.services.deps import get_settings_service
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    job_service = real_services_job_service
    manager = get_service_manager()
    settings = get_settings_service().settings
    original_db_service = manager.services.get(ServiceType.DATABASE_SERVICE)
    original_pool = settings.db_connection_settings
    tiny = None
    try:
        # One main connection, no overflow: holding it exhausts the application pool entirely.
        settings.db_connection_settings = {**original_pool, "pool_size": 1, "max_overflow": 0}
        tiny = DatabaseServiceFactory().create(get_settings_service())
        manager.services[ServiceType.DATABASE_SERVICE] = tiny  # _beat resolves this via get_db_service()

        job_id = uuid4()
        await job_service.create_job(
            job_id=job_id, flow_id=uuid4(), user_id=uuid4(), job_type=JobType.WORKFLOW, status=JobStatus.IN_PROGRESS
        )
        before = (await job_service.get_job_by_job_id(job_id)).job_metadata or {}

        async with tiny.engine.connect():  # hold the only main-pool connection for the whole beat
            beat_ok = await job_service._beat(job_id)

        assert beat_ok is True
        after = (await job_service.get_job_by_job_id(job_id)).job_metadata or {}
        assert after.get("heartbeat_at")  # the beat landed despite the exhausted main pool
        assert after.get("heartbeat_at") != before.get("heartbeat_at")  # it is a fresh stamp
    finally:
        settings.db_connection_settings = original_pool
        if tiny is not None:
            with contextlib.suppress(Exception):
                await tiny.teardown()
        if original_db_service is not None:
            manager.services[ServiceType.DATABASE_SERVICE] = original_db_service


@pytest.mark.real_services
@pytest.mark.parametrize("outcome", ["completed", "failed", "cancelled"])
async def test_f03_heartbeat_survives_terminal_write_pool_exhaustion(real_services_job_service, monkeypatch, outcome):
    """A worker must not reap a run waiting for its terminal write's connection."""
    import langflow.services.jobs.service as jobs_module
    import lfx.services.deps as lfx_deps
    from langflow.services.database.factory import DatabaseServiceFactory
    from langflow.services.deps import get_db_service, get_settings_service
    from langflow.services.jobs.service import JobService

    settings_service = get_settings_service()
    settings = settings_service.settings
    worker_db = get_db_service()
    monkeypatch.setattr(
        settings,
        "db_connection_settings",
        {**settings.db_connection_settings, "pool_size": 1, "max_overflow": 0, "pool_timeout": 10},
    )
    monkeypatch.setattr(settings, "background_heartbeat_interval_s", 0.1)
    api_db = DatabaseServiceFactory().create(settings_service)
    task_db = ContextVar("terminal_write_test_db", default=api_db)
    # Each simulated process keeps its own application pool against the same database.
    monkeypatch.setattr(lfx_deps, "get_db_service", task_db.get)
    monkeypatch.setattr(jobs_module, "get_db_service", task_db.get)
    service = real_services_job_service
    worker = JobService()
    job_id = uuid4()
    entered = asyncio.Event()
    finish = asyncio.Event()
    terminal_write = asyncio.Event()
    terminalize = service.terminalize_live_job

    async def observe_terminal_write(*args, **kwargs):
        terminal_write.set()
        return await terminalize(*args, **kwargs)

    monkeypatch.setattr(service, "terminalize_live_job", observe_terminal_write)

    async def run_flow():
        entered.set()
        await finish.wait()
        if outcome == "failed":
            message = "flow failed"
            raise ValueError(message)
        if outcome == "cancelled":
            message = "LANGFLOW_USER_CANCELLED"
            raise asyncio.CancelledError(message)
        return "flow result"

    run = None
    try:
        await service.create_job(
            job_id=job_id, flow_id=uuid4(), job_type=JobType.WORKFLOW, status=JobStatus.IN_PROGRESS, heartbeat=True
        )
        run = asyncio.create_task(service.execute_with_status(job_id, run_flow, keep_alive=True))
        await asyncio.wait_for(entered.wait(), timeout=5)
        async with api_db.engine.connect():
            finish.set()
            await asyncio.wait_for(terminal_write.wait(), timeout=5)
            assert not run.done()
            token = task_db.set(worker_db)
            try:
                # The held connection outlasts the lease while dedicated heartbeats continue.
                await asyncio.sleep(0.8)
                swept = await worker.sweep_orphans(lease_ttl_s=0.5)
                assert job_id not in swept
            finally:
                task_db.reset(token)

        if outcome == "failed":
            with pytest.raises(ValueError, match="flow failed"):
                await asyncio.wait_for(run, timeout=5)
        elif outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError, match="LANGFLOW_USER_CANCELLED"):
                await asyncio.wait_for(run, timeout=5)
        else:
            assert await asyncio.wait_for(run, timeout=5) == "flow result"

        job = await service.get_job_by_job_id(job_id)
        assert job.status == JobStatus(outcome)
        assert job.finished_timestamp is not None
        assert (job.error or {}).get("type") != "worker_lost"
        assert job_id not in service._keep_alives
    finally:
        finish.set()
        if run is not None:
            await asyncio.gather(run, return_exceptions=True)
        await service.stop_keep_alive(job_id)
        await api_db.teardown()


async def test_simple_run_flow_creates_the_row_in_progress(monkeypatch):
    """SOURCE proof: ``simple_run_flow`` creates the v1 row IN_PROGRESS, not QUEUED.

    This is the one test that goes RED on unpatched source — before the fix ``create_job``
    is called with no ``status`` (defaulting QUEUED) and ``execute_with_status`` with no
    ``mark_in_progress``. The real-DB tests above prove what that status change buys; this
    proves ``simple_run_flow`` actually makes the change. Follows the warm-graph seam-test
    idiom (test_warm_graph_execution.py): a mocked job service captures the call arguments.
    """
    from langflow.api import warm_graph
    from langflow.api.v1 import endpoints
    from langflow.api.v1.schemas import SimplifiedAPIRequest
    from langflow.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "custom_component_admin_only", False)

    graph = SimpleNamespace(vertices=[], run_id=None)
    graph.set_run_id = lambda run_id: setattr(graph, "run_id", str(run_id))

    async def fake_warm_deepcopy(flow_id, **_kwargs):  # noqa: ARG001
        return graph

    job_service = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(return_value=([], "effective-session")),
    )
    monkeypatch.setattr(warm_graph, "warm_deepcopy", fake_warm_deepcopy)
    monkeypatch.setattr(endpoints, "get_job_service", lambda: job_service)
    monkeypatch.setattr(endpoints, "get_task_service", lambda: SimpleNamespace(fire_and_forget_task=AsyncMock()))
    monkeypatch.setattr(endpoints, "get_memory_base_service", lambda: SimpleNamespace(on_flow_output=AsyncMock()))
    # Force the warm path; the cold path would need a real graph build.
    monkeypatch.setattr(endpoints, "process_tweaks", Mock(side_effect=AssertionError("cold path used")))

    user_id = uuid4()
    await endpoints.simple_run_flow(
        flow=SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            name="warm",
            data={"nodes": [], "edges": []},
            updated_at=datetime(2026, 8, 5, 12, tzinfo=timezone.utc),
        ),
        input_request=SimplifiedAPIRequest(session_id="v1-session"),
        stream=False,
        api_key_user=SimpleNamespace(id=user_id, is_superuser=False),
    )

    # The row is born IN_PROGRESS, so the scaled worker's QUEUED-claim path never sees it.
    assert job_service.create_job.await_args.kwargs.get("status") == JobStatus.IN_PROGRESS
    # mark_in_progress stays default True: begin_live_job's terminal-status guard must still run,
    # so a watchdog that already failed the row makes execute_with_status raise instead of
    # returning a result over a FAILED row (keeps the F-02 fix off the F-03 seam; CodeRabbit C1).
    assert job_service.execute_with_status.await_args.kwargs.get("mark_in_progress", True) is True
