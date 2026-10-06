"""The migration write pause.

Nothing turns the pause on yet except the record file, so these tests write it the way
the migration API does: a temp file renamed into place. The app, the database, the
background service and the second worker process are real.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from langflow.api.utils import migration_pause
from langflow.api.utils.migration_pause import MigrationPauseMiddleware, is_paused
from langflow.initial_setup.setup import sync_flows_from_fs
from langflow.main import create_app
from langflow.services.background_execution.executor import InProcessExecutor
from langflow.services.data_subjects.requests import create_end_user_request
from langflow.services.data_subjects.worker import LEASE_NAME, DataSubjectEraseWorker, data_subject_erase_worker
from langflow.services.database.models.auth import AuthzAuditLog
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
    DataSubjectType,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent, TriggerLease
from langflow.services.database.models.trigger.schemas import TriggerEventState, TriggerState
from langflow.services.deps import (
    get_background_execution_service,
    get_job_service,
    get_settings_service,
    session_scope,
)
from langflow.services.task.audit_cleanup import AuditLogCleanupWorker
from langflow.services.telemetry_writer.service import TelemetryWriterService
from langflow.services.triggers.constants import DISPATCHER_LEASE_NAME, SCHEDULER_LEASE_NAME
from langflow.services.triggers.dispatcher import TriggerDispatcher
from lfx.services.settings.feature_flags import FEATURE_FLAGS
from sqlmodel import select

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from pathlib import Path
    from uuid import UUID

RECORD = {"target": {}, "steps": {}, "accepted_findings": []}
PAUSED = {**RECORD, "pause": {"frozen_at": "2026-10-05T12:00:00+00:00", "frozen_by": "admin"}}
REFUSAL = {"detail": "This instance is being migrated."}
NEW_FLOW = {"name": "saved around a pause", "data": {}}
# One process asks a second one, which keeps its own copy of what the record said.
WORKER = """
import sys
from langflow.api.utils.migration_pause import is_paused
for _ in sys.stdin:
    print(f"paused={is_paused()}", flush=True)
"""


@pytest.fixture(autouse=True)
def migration_enabled(request, monkeypatch: pytest.MonkeyPatch):
    """Turn the feature on before the app is built, because the middleware is registered then.

    A test keeps the feature off by parametrizing this fixture with False.
    """
    monkeypatch.setattr(FEATURE_FLAGS, "instance_migration", getattr(request, "param", True))


@pytest.fixture
def config_dir(client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: ARG001
    """The record is read from CONFIG_DIR, so keep it out of the real one."""
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def background_service(client, monkeypatch: pytest.MonkeyPatch):  # noqa: ARG001
    """The app's background service, given a scripted run where a graph build would go."""
    service = get_background_execution_service()
    monkeypatch.setattr(service, "_frame_source_factory", lambda **_kwargs: _scripted_run)
    return service


async def _scripted_run(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
    for event in ("build_start", "end"):
        yield json.dumps({"event": event, "data": {}}).encode(), event


def _write_record(config_dir: Path, record: dict) -> None:
    path = config_dir / "migrations" / "migration.json"
    path.parent.mkdir(exist_ok=True)
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(record))
    partial.replace(path)


async def _eventually(condition: Callable[[], Awaitable[bool]]) -> bool:
    for _ in range(100):
        if await condition():
            return True
        await asyncio.sleep(0.05)
    return False


async def _acts_only_after_the_pause(config_dir: Path, acted: Callable[[], Awaitable[bool]]) -> None:
    await asyncio.sleep(0.5)
    assert not await acted()

    _write_record(config_dir, RECORD)

    assert await _eventually(acted)


async def _job_status(job_id) -> JobStatus:
    return (await get_job_service().get_job_by_job_id(job_id)).status


async def _completed(job_id) -> bool:
    return await _job_status(job_id) == JobStatus.COMPLETED


async def _open_websocket(client, path: str) -> list[dict]:
    """Drive the app as a raw ASGI websocket client and return what it answered the handshake with."""
    received = iter([{"type": "websocket.connect"}])
    sent: list[dict] = []

    async def receive():
        return next(received, {"type": "websocket.disconnect", "code": 1001})

    async def send(message):
        sent.append(message)

    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
        "subprotocols": [],
        "extensions": {"websocket.http.response": {}},
    }
    await client._transport.app(scope, receive, send)
    return sent


async def test_a_change_is_refused_while_paused_and_passes_once_the_pause_ends(client, logged_in_headers, config_dir):
    _write_record(config_dir, PAUSED)

    browser = {**logged_in_headers, "Origin": "http://another.origin"}
    refused = await client.post("api/v1/flows/", json=NEW_FLOW, headers=browser)

    assert refused.status_code == 503
    assert refused.json() == REFUSAL
    # A page served from another origin can read the refusal.
    assert "access-control-allow-origin" in refused.headers

    _write_record(config_dir, RECORD)

    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)).status_code == 201


async def test_a_read_passes_while_paused(client, logged_in_headers, config_dir):
    _write_record(config_dir, PAUSED)

    assert (await client.get("api/v1/flows/", headers=logged_in_headers)).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "api/v1/migration",
        "api/v1/migration/checks",
        "api/v1/login",
        "api/v1/refresh",
        "api/v1/logout",
        "api/v1/auto_login",
    ],
)
async def test_the_migration_and_session_routes_reach_the_app_while_paused(client, config_dir, path):
    _write_record(config_dir, PAUSED)

    response = await client.post(path)

    # The app answers for itself (no such route, wrong method, no credentials), never with the refusal.
    assert response.status_code != 503


async def test_a_path_that_only_resembles_an_allowed_one_is_refused(client, config_dir):
    _write_record(config_dir, PAUSED)

    assert (await client.post("api/v1/migrations")).status_code == 503
    assert (await client.post("api/v1/login/as-someone")).status_code == 503


async def test_the_allow_list_holds_behind_a_root_path(client, config_dir):
    _write_record(config_dir, PAUSED)
    transport = ASGITransport(app=client._transport.app, root_path="/langflow")

    async with AsyncClient(transport=transport, base_url="http://testserver/") as proxied:
        assert (await proxied.post("langflow/api/v1/login")).status_code != 503
        assert (await proxied.post("langflow/api/v1/flows/", json=NEW_FLOW)).status_code == 503


async def test_a_websocket_is_refused_while_paused(client, config_dir):
    voice = f"/api/v1/voice/ws/flow_as_tool/{uuid4()}"
    _write_record(config_dir, PAUSED)

    refused = await _open_websocket(client, voice)

    assert [message["type"] for message in refused] == ["websocket.http.response.start", "websocket.http.response.body"]
    assert refused[0]["status"] == 503
    assert json.loads(refused[1]["body"]) == REFUSAL

    _write_record(config_dir, RECORD)

    assert (await _open_websocket(client, voice))[0]["type"] == "websocket.accept"


@pytest.mark.usefixtures("background_service")
async def test_a_change_is_refused_at_the_moment_a_pause_checks_that_none_is_going(
    client, logged_in_headers, config_dir
):
    fcntl = pytest.importorskip("fcntl", reason="workers share the lock through flock")
    _write_record(config_dir, RECORD)
    lock = os.open(config_dir / "migrations" / "pause.lock", os.O_RDWR | os.O_CREAT)
    try:
        # What a pause holds for an instant, in whichever worker it runs, to learn that no change is going.
        fcntl.flock(lock, fcntl.LOCK_EX)
        refused = await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)
    finally:
        os.close(lock)

    assert refused.status_code == 503
    assert refused.json() == REFUSAL
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)).status_code == 201


async def test_a_change_takes_its_place_before_it_asks_about_the_pause(
    client, logged_in_headers, config_dir, monkeypatch
):
    fcntl = pytest.importorskip("fcntl", reason="workers share the lock through flock")
    _write_record(config_dir, RECORD)
    place_held_when_asked = []
    ask = migration_pause.is_paused

    def ask_and_look() -> bool:
        # What a pause would find at this very moment, from whichever worker it runs in.
        lock = os.open(config_dir / "migrations" / "pause.lock", os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            place_held_when_asked.append(True)
        else:
            place_held_when_asked.append(False)
        finally:
            os.close(lock)
        return ask()

    monkeypatch.setattr(migration_pause, "is_paused", ask_and_look)

    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)).status_code == 201
    # Asked the other way round, a pause written between the two would count nothing and stop nothing.
    assert place_held_when_asked == [True]


async def test_a_lock_that_cannot_be_taken_stops_no_change(client, logged_in_headers, config_dir):
    pytest.importorskip("fcntl", reason="workers share the lock through flock")
    # A CONFIG_DIR this process cannot use for the lock, here because a folder sits where the lock goes.
    (config_dir / "migrations" / "pause.lock").mkdir(parents=True)

    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)).status_code == 201

    _write_record(config_dir, PAUSED)

    # The pause itself still holds: it is read from the record.
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)).status_code == 503


async def test_a_schedule_that_comes_due_during_the_pause_fires_after_it_ends(active_user, config_dir):
    async with session_scope() as session:
        flow = Flow(name="scheduled", user_id=active_user.id, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        trigger = Trigger(
            flow_id=flow.id,
            user_id=active_user.id,
            name="every minute",
            kind="schedule",
            config={"cron": "* * * * *", "timezone": "UTC"},
            state=TriggerState.ACTIVE.value,
            next_fire_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        session.add(trigger)
        # Other background workers share the lease table and may already hold a lease before the pause.
        session.add(
            TriggerLease(
                name="unrelated-background-worker",
                owner="pause-test-worker",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            )
        )

    async def rows(model) -> list:
        async with session_scope() as session:
            return list((await session.exec(select(model))).all())

    dispatcher = TriggerDispatcher(owner="pause-test")
    _write_record(config_dir, PAUSED)

    assert await dispatcher.tick() == 0
    assert await dispatcher.source_tick() == 0
    # Neither loop wrote an event or acquired a trigger lease. Unrelated workers share this table.
    assert await rows(TriggerEvent) == []
    assert {lease.name for lease in await rows(TriggerLease)}.isdisjoint(
        {SCHEDULER_LEASE_NAME, DISPATCHER_LEASE_NAME, "trigger-source-maintenance"}
    )

    _write_record(config_dir, RECORD)

    assert await dispatcher.tick() == 1
    [event] = await rows(TriggerEvent)
    assert event.state == TriggerEventState.DISPATCHED.value
    assert await _eventually(lambda: _completed(event.job_id))


async def test_a_queued_job_stays_queued_while_paused_and_starts_after(active_user, config_dir, background_service):
    _write_record(config_dir, PAUSED)

    job_id = await background_service.submit(flow_id=uuid4(), request={"stream_protocol": "langflow"}, user=active_user)
    await asyncio.sleep(0.5)

    assert await _job_status(job_id) == JobStatus.QUEUED

    _write_record(config_dir, RECORD)

    assert await _eventually(lambda: _completed(job_id))


async def test_a_job_the_pause_holds_survives_a_stop_and_runs_after_the_next_start(config_dir):
    _write_record(config_dir, PAUSED)
    executor = InProcessExecutor(max_concurrency=1)
    ran = asyncio.Event()

    async def job() -> None:
        ran.set()

    async def taken() -> bool:
        return executor._queue.empty()

    await executor.start()
    await executor.submit("held", job)
    # The worker has the job in hand and is waiting out the pause.
    assert await _eventually(taken)
    await executor.stop()
    _write_record(config_dir, RECORD)

    await executor.start()
    try:
        await asyncio.wait_for(ran.wait(), timeout=5)
    finally:
        await executor.stop()


def test_a_second_worker_process_sees_the_pause_when_the_record_changes(tmp_path: Path):
    env = {**os.environ, "LANGFLOW_CONFIG_DIR": str(tmp_path), "LANGFLOW_FEATURE_INSTANCE_MIGRATION": "true"}
    command = [sys.executable, "-c", WORKER]

    with subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as worker:  # noqa: S603

        def ask() -> str:
            worker.stdin.write("\n")
            worker.stdin.flush()
            # Imports may print before the first answer.
            return next((line.strip() for line in worker.stdout if line.startswith("paused=")), "the worker exited")

        assert ask() == "paused=False"
        _write_record(tmp_path, PAUSED)
        assert ask() == "paused=True"
        _write_record(tmp_path, RECORD)
        assert ask() == "paused=False"


async def test_a_damaged_record_does_not_lift_the_pause(config_dir):
    _write_record(config_dir, PAUSED)
    assert is_paused()

    (config_dir / "migrations" / "migration.json").write_text('{"pause": ')

    assert is_paused()


@pytest.mark.parametrize("migration_enabled", [False], indirect=True)
async def test_a_record_that_says_paused_changes_nothing_while_the_feature_is_off(
    client, logged_in_headers, config_dir
):
    _write_record(config_dir, PAUSED)

    assert not is_paused()
    assert MigrationPauseMiddleware not in [middleware.cls for middleware in create_app().user_middleware]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=logged_in_headers)).status_code == 201
    # Nor does a change take the lock a pause waits on: this instance pays nothing.
    assert not (config_dir / "migrations" / "pause.lock").exists()


async def test_the_flow_sync_from_disk_waits_out_the_pause(active_user, config_dir, monkeypatch):
    # The app under test runs this loop too, every ten seconds. It is stopped here: one of its passes
    # between the flow below and the pause would sync the flow before the pause was on.
    theirs = [task for task in asyncio.all_tasks() if getattr(task.get_coro(), "__name__", "") == "sync_flows_from_fs"]
    for task in theirs:
        task.cancel()
    await asyncio.gather(*theirs, return_exceptions=True)
    flow_file = config_dir / "flow.json"
    flow_file.write_text(json.dumps({"name": "renamed on disk"}))
    async with session_scope() as session:
        flow = Flow(name="named in the database", user_id=active_user.id, data={}, fs_path=str(flow_file))
        session.add(flow)
        await session.flush()
        flow_id = flow.id

    async def synced() -> bool:
        async with session_scope() as session:
            return (await session.get(Flow, flow_id)).name == "renamed on disk"

    monkeypatch.setattr(get_settings_service().settings, "fs_flows_polling_interval", 50)
    _write_record(config_dir, PAUSED)
    sync = asyncio.create_task(sync_flows_from_fs())
    try:
        await _acts_only_after_the_pause(config_dir, synced)
    finally:
        sync.cancel()
        await asyncio.gather(sync, return_exceptions=True)


async def test_the_audit_log_cleanup_waits_out_the_pause(config_dir, monkeypatch):
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_AUDIT_ENABLED", True)
    async with session_scope() as session:
        expired = AuthzAuditLog(
            user_id=uuid4(),
            action="flow:read",
            resource_type="flow",
            resource_id=uuid4(),
            result="allow",
            details={},
            timestamp=datetime.now(timezone.utc) - timedelta(days=3650),
        )
        session.add(expired)
        await session.flush()
        row_id = expired.id

    async def pruned() -> bool:
        async with session_scope() as session:
            return await session.get(AuthzAuditLog, row_id) is None

    _write_record(config_dir, PAUSED)
    worker = AuditLogCleanupWorker(interval=0.05)
    await worker.start()
    try:
        await _acts_only_after_the_pause(config_dir, pruned)
    finally:
        await worker.stop()


async def _approved_erase(decided: datetime) -> UUID:
    """An erase request that an admin approved, for a user this instance holds nothing of."""
    async with session_scope() as session:
        approved = DataSubjectRequest(
            subject_type=DataSubjectType.BUILDER.value,
            subject_user_id=uuid4(),
            source=DataSubjectRequestSource.ADMIN.value,
            status=DataSubjectRequestStatus.APPROVED.value,
            due_at=decided + timedelta(days=30),
            decided_at=decided,
        )
        session.add(approved)
        await session.flush()
        return approved.id


async def _erase_status(request_id: UUID) -> str:
    async with session_scope() as session:
        return (await session.get(DataSubjectRequest, request_id)).status


async def test_an_approved_erase_waits_out_the_pause(config_dir, monkeypatch):
    monkeypatch.setattr("langflow.services.data_subjects.engine.LATE_WRITE_SETTLE_SECONDS", 0)
    # One worker runs at a time, and the app's own worker holds the lease that says which.
    await data_subject_erase_worker.stop()
    request_id = await _approved_erase(datetime.now(timezone.utc))

    async def taken_up() -> bool:
        return await _erase_status(request_id) != DataSubjectRequestStatus.APPROVED.value

    _write_record(config_dir, PAUSED)
    worker = DataSubjectEraseWorker(interval=0.05)
    await worker.start()
    try:
        await _acts_only_after_the_pause(config_dir, taken_up)
    finally:
        await worker.stop()


async def test_an_erase_pass_that_the_pause_overtakes_starts_no_other_erase(config_dir, monkeypatch):
    # Each erase waits this long for late writes, which is when the pause begins here.
    monkeypatch.setattr("langflow.services.data_subjects.engine.LATE_WRITE_SETTLE_SECONDS", 1)
    await data_subject_erase_worker.stop()
    decided = datetime.now(timezone.utc)
    first = await _approved_erase(decided - timedelta(minutes=1))
    second = await _approved_erase(decided)

    async def first_is_under_way() -> bool:
        return await _erase_status(first) == DataSubjectRequestStatus.ERASING.value

    one_pass = asyncio.create_task(DataSubjectEraseWorker().run_once())
    assert await _eventually(first_is_under_way)
    _write_record(config_dir, PAUSED)

    # The erase that was under way ends. The one behind it in the same pass keeps its status for after the pause.
    assert await one_pass == 1
    assert await _erase_status(first) == DataSubjectRequestStatus.DONE.value
    assert await _erase_status(second) == DataSubjectRequestStatus.APPROVED.value


async def test_a_paused_erase_pass_neither_approves_overdue_requests_nor_takes_the_lease(config_dir, monkeypatch):
    monkeypatch.setattr(FEATURE_FLAGS, "data_subject_requests", True)
    monkeypatch.setattr(get_settings_service().settings, "data_subject_auto_erase_on_expiry", True)
    await data_subject_erase_worker.stop()
    async with session_scope() as session:
        if (lease := await session.get(TriggerLease, LEASE_NAME)) is not None:
            await session.delete(lease)
        request, _ = await create_end_user_request(
            session,
            end_user_id=f"overdue-{uuid4()}",
            scope_flow_ids=None,
            requested_by=None,
            source=DataSubjectRequestSource.ADMIN,
        )
        request.due_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.add(request)
        request_id = request.id

    async def lease_owner() -> str | None:
        async with session_scope() as session:
            lease = await session.get(TriggerLease, LEASE_NAME)
            return lease.owner if lease is not None else None

    _write_record(config_dir, PAUSED)
    worker = DataSubjectEraseWorker()
    assert await worker.run_once() == 0
    # Approving would stop the end user and audit it, and the pass would also renew the lease.
    assert await _erase_status(request_id) == DataSubjectRequestStatus.REQUESTED.value
    assert await lease_owner() is None

    _write_record(config_dir, RECORD)
    await worker.run_once()
    assert await _erase_status(request_id) != DataSubjectRequestStatus.REQUESTED.value
    assert await lease_owner() == worker._owner


async def test_the_telemetry_writer_neither_flushes_nor_prunes_while_paused(active_user, config_dir, monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "telemetry_writer_enabled", True)
    monkeypatch.setattr(settings, "telemetry_writer_outbox_dir", str(config_dir / "outbox"))
    monkeypatch.setattr(settings, "telemetry_writer_flush_interval_s", 0.05)
    monkeypatch.setattr(settings, "max_transactions_to_keep", 1)
    async with session_scope() as session:
        flow = Flow(name="traced", user_id=active_user.id, data={})
        session.add(flow)
        await session.flush()
        flow_id = flow.id

    async def stored() -> int:
        async with session_scope() as session:
            return len((await session.exec(select(TransactionTable).where(TransactionTable.flow_id == flow_id))).all())

    async def flushed() -> bool:
        return await stored() == 2

    writer = TelemetryWriterService(get_settings_service())
    await writer.start()
    try:
        _write_record(config_dir, PAUSED)
        for vertex in ("first", "second"):
            row = TransactionTable(vertex_id=vertex, inputs={}, outputs={}, status="success", flow_id=flow_id)
            assert writer.enqueue_transaction(row.model_dump(mode="python"))
        await _acts_only_after_the_pause(config_dir, flushed)

        # One row is now past the limit. The sweep leaves it alone for as long as a pause lasts.
        _write_record(config_dir, PAUSED)
        await writer._run_retention_pass()
        assert await stored() == 2

        _write_record(config_dir, RECORD)
        await writer._run_retention_pass()
        assert await stored() == 1
    finally:
        await writer.teardown()
