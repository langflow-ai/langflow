"""Background mode end-to-end through the HTTP API over the default backend.

Real no-LLM flow in the migrated test DB; real facade; real executor + bus.
Asserts the WorkflowJobResponse contract on submit, terminal status on GET, and
that GET /events replays durable milestones from the durable ``job_events`` log.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture
async def bg_flow(created_api_key, json_memory_chatbot_no_llm):
    """A real no-LLM chatbot flow (ChatInput -> Prompt/Memory -> ChatOutput).

    Runs entirely offline so a background run reaches COMPLETED without any
    external API key.
    """
    raw = json.loads(json_memory_chatbot_no_llm)
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="bg-no-llm-flow",
            description="No-LLM flow for background-mode tests",
            data=raw.get("data", raw),
            user_id=created_api_key.user_id,
        )
        session.add(flow)
        await session.flush()
    yield str(flow_id)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


def _headers(api_key) -> dict:
    return {"x-api-key": api_key.api_key}


def _body(flow_id: str) -> dict:
    return {
        "flow_id": flow_id,
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "hi",
    }


async def test_background_submit_returns_job_response(client, created_api_key, bg_flow):
    resp = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["flow_id"] == bg_flow
    assert body["status"] == "queued"
    assert "job_id" in body


async def test_background_reaches_terminal_status(client, created_api_key, bg_flow):
    """The background run reaches COMPLETED durable status.

    Status is read from the durable ``Job`` row (the facade's source of truth).
    The ``GET /workflows`` COMPLETED branch reconstructs from ``vertex_build``
    rows keyed by job_id; wiring the background build to persist those is the
    Phase 3 endpoint concern, so here we assert the durable terminal status the
    facade owns.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]

    final = None
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMED_OUT,
        ):
            final = row.status
            break
        await asyncio.sleep(0.1)
    assert final == JobStatus.COMPLETED, f"job did not complete: last={final}"


async def test_background_status_returns_output(client, created_api_key, bg_flow):
    """A completed background run's GET status carries its terminal output.

    Background runs do not persist ``vertex_builds`` keyed by job_id, so the
    vertex-build reconstruction finds nothing. The runner instead captures the
    terminal ``output`` events into ``Job.result`` and the COMPLETED branch
    rebuilds the ``outputs`` map from them. Regression: the status previously
    returned a bare COMPLETED with an empty ``outputs`` and a null ``output``.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]

    row = None
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)
    assert row is not None, "job row missing"
    assert row.status == JobStatus.COMPLETED, "job never completed"

    status = await client.get("api/v2/workflows", params={"job_id": job_id}, headers=_headers(created_api_key))
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["status"] == "completed"
    # The terminal outputs are present (an empty dict before the fix).
    assert body["outputs"], f"completed background status carried no outputs: {body}"


async def test_background_status_from_job_table_with_vertex_builds_off(client, created_api_key, bg_flow, monkeypatch):
    """With vertex_build storage OFF, GET status must still carry the full output.

    Proves the headless-executor path: disable ``vertex_builds_storage_enabled`` so
    NO vertex_build rows are written, run a background job, then assert the GET
    status output is sourced from the durable ``Job.result`` blob (the fallback the
    COMPLETED branch takes when vertex-build reconstruction finds nothing).

    Three proofs: (1) zero vertex_build rows keyed by job_id, (2) ``Job.result``
    holds the captured outputs, (3) GET status returns a non-empty ``outputs`` map.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus
    from langflow.services.database.models.vertex_builds.crud import get_vertex_builds_by_job_id
    from lfx.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "vertex_builds_storage_enabled", False)
    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    assert submit.status_code == 200, submit.text
    job_id = submit.json()["job_id"]

    row = None
    for _ in range(200):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.TIMED_OUT,
        ):
            break
        await asyncio.sleep(0.1)
    assert row is not None, "job row was never created"
    assert row.status == JobStatus.COMPLETED, f"job did not complete: {row.status}"

    # Proof 1: storage OFF => no vertex_build rows persisted for this job_id.
    async with session_scope() as session:
        vbs = await get_vertex_builds_by_job_id(session, job_id)
    assert not vbs, f"vertex_builds were written despite storage OFF: {len(vbs)} rows"

    # Proof 2: the durable Job.result blob carries the captured terminal outputs.
    assert isinstance(row.result, dict), f"Job.result is not a dict: {row.result!r}"
    assert row.result.get("outputs"), f"Job.result carried no outputs: {row.result}"

    # Proof 3: GET status returns the full output, sourced from Job.result (reconstruct
    # finds nothing with storage off, so the COMPLETED branch falls back to Job.result).
    status = await client.get("api/v2/workflows", params={"job_id": job_id}, headers=_headers(created_api_key))
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["status"] == "completed"
    assert body["outputs"], f"GET status carried no outputs with vertex_builds OFF: {body}"
    # Proof 4: the Job.result path recovers session_id from the persisted submit
    # request in job.job_metadata["request"], so a background GET can continue
    # the same chat thread even with vertex-build storage off.
    assert body.get("session_id"), f"GET status lost session_id with vertex_builds OFF: {body}"


async def test_background_agui_populates_job_result_outputs(client, created_api_key, bg_flow):
    """An agui-protocol background run now fills ``Job.result.outputs`` too.

    Regression guard for the off-wire capture (WORKFLOW_OUTPUT_CAPTURE_EVENT): the
    agui adapter emits no wire ``output`` event, so the runner used to leave
    ``Job.result`` result-less and a GET status carried an empty ``outputs``. The
    frame source now synthesizes a protocol-neutral capture frame from the raw
    ``end_vertex``, which the runner records into ``Job.result`` without touching
    ``job_events`` or the live bus. Proves: (1) ``Job.result`` carries outputs for
    an agui run, (2) GET status returns a non-empty ``outputs`` map.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    body = {**_body(bg_flow), "stream_protocol": "agui"}
    submit = await client.post("api/v2/workflows", json=body, headers=_headers(created_api_key))
    assert submit.status_code == 200, submit.text
    job_id = submit.json()["job_id"]

    row = None
    for _ in range(200):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMED_OUT):
            break
        await asyncio.sleep(0.1)
    assert row is not None, "agui job row was never created"
    assert row.status == JobStatus.COMPLETED, f"agui job did not complete: {row.status}"

    # Proof 1: the durable Job.result blob carries the captured terminal outputs
    # even though agui emitted no wire ``output`` event.
    assert isinstance(row.result, dict), f"Job.result is not a dict: {row.result!r}"
    assert row.result.get("outputs"), f"agui Job.result carried no outputs: {row.result}"

    # Proof 2: GET status returns the full output, sourced from Job.result.
    status = await client.get("api/v2/workflows", params={"job_id": job_id}, headers=_headers(created_api_key))
    assert status.status_code == 200, status.text
    status_body = status.json()
    assert status_body["status"] == "completed"
    assert status_body["outputs"], f"agui GET status carried no outputs: {status_body}"


async def test_stop_does_not_overwrite_completed_job(client, created_api_key, bg_flow):
    """A late ``/stop`` on an already-COMPLETED job must NOT flip it to CANCELLED.

    The stop handler used to call ``update_job_status(CANCELLED)`` unconditionally,
    so stopping a finished run overwrote COMPLETED (and stranded the result blob).
    Submit, wait for COMPLETED, capture the result, then POST /stop and assert the
    durable row stays COMPLETED with its result intact.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]

    completed_result = None
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status == JobStatus.COMPLETED:
            completed_result = row.result
            break
        await asyncio.sleep(0.1)
    assert completed_result is not None or row.status == JobStatus.COMPLETED, "job never completed"

    # Late stop on the finished job.
    stop = await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=_headers(created_api_key))
    assert stop.status_code == 200, stop.text

    async with session_scope() as session:
        row = await session.get(Job, UUID(job_id))
    assert row.status == JobStatus.COMPLETED, f"late stop overwrote terminal status: {row.status}"
    assert row.result == completed_result, "late stop clobbered the completed result"


async def test_background_events_replay_durable(client, created_api_key, bg_flow):
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]
    # Wait for completion so the durable log is fully written.
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.1)

    # Reattach from the beginning; durable milestones must replay.
    async with client.stream("GET", f"api/v2/workflows/{job_id}/events", headers=_headers(created_api_key)) as resp:
        assert resp.status_code == 200
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk
            if b'"event": "end"' in body or b"end_vertex" in body:
                break
    assert b"build_start" in body or b"end_vertex" in body


async def test_finalize_job_status_never_overwrites_suspended():
    """A suspended (HITL) job must survive the AGUI finalize path unchanged.

    HITL suspend runs on the durable substrate, which skips finalization while
    ``paused``, so a SUSPENDED job should never reach ``_finalize_job_status``.
    This is the defense-in-depth guard: if one ever did, finalizing it to
    COMPLETED/FAILED would clobber the resumable state and silently break resume.
    A real suspend cannot exercise this AGUI path, so the guard is mocked.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from langflow.api.v2 import workflow_background as wb
    from lfx.schema.workflow import JobStatus

    job_uuid = uuid4()
    suspended_job = SimpleNamespace(status=JobStatus.SUSPENDED)
    fake_service = SimpleNamespace(
        get_job_by_job_id=AsyncMock(return_value=suspended_job),
        update_job_status=AsyncMock(),
    )
    with patch.object(wb, "get_job_service", return_value=fake_service):
        await wb._finalize_job_status(job_uuid, JobStatus.COMPLETED)

    fake_service.update_job_status.assert_not_awaited()


async def test_finalize_job_status_still_writes_terminal_for_running_job():
    """The guard must NOT block normal finalization of a live run."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch
    from uuid import uuid4

    from langflow.api.v2 import workflow_background as wb
    from lfx.schema.workflow import JobStatus

    running_job = SimpleNamespace(status=JobStatus.IN_PROGRESS)
    fake_service = SimpleNamespace(
        get_job_by_job_id=AsyncMock(return_value=running_job),
        update_job_status=AsyncMock(),
    )
    with patch.object(wb, "get_job_service", return_value=fake_service):
        await wb._finalize_job_status(uuid4(), JobStatus.COMPLETED)

    fake_service.update_job_status.assert_awaited_once()


def _enable_sync_persistence(monkeypatch) -> None:
    """Turn on the opt-in sync-result cache (``sync_result_storage_enabled`` is off by default)."""
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "sync_result_storage_enabled", True)


async def test_sync_run_persists_job_result_when_enabled(client, created_api_key, bg_flow, monkeypatch):
    """With the flag ON, a sync run caches BOTH its outputs and session for GET status.

    Sync already creates a Job row (to support HITL suspend + run_id-keyed builds);
    with ``sync_result_storage_enabled`` the completed run also writes Job.result
    (list-of-OutputEvent shape) and the session to job_metadata, so a later GET
    status rebuilds the SAME response the caller got inline — outputs AND session_id.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job

    _enable_sync_persistence(monkeypatch)

    body = {"flow_id": bg_flow, "mode": "sync", "input_value": "hi", "session_id": "ab-session-marker"}
    resp = await client.post("api/v2/workflows", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed", data
    assert data["outputs"], f"sync response carried no outputs: {data}"
    assert data["session_id"] == "ab-session-marker"  # inline response is the source of truth
    job_id = data["job_id"]

    # Job.result + session persisted on the job row.
    async with session_scope() as session:
        row = await session.get(Job, UUID(job_id))
    assert row is not None
    assert isinstance(row.result, dict), f"Job.result not a dict: {row.result!r}"
    assert row.result.get("outputs"), f"Job.result has no outputs: {row.result!r}"
    assert (row.job_metadata or {}).get("request", {}).get("session_id") == "ab-session-marker"

    # GET status returns the SAME outputs AND session_id — not the flow id (regression guard).
    status = await client.get("api/v2/workflows", params={"job_id": job_id}, headers=_headers(created_api_key))
    assert status.status_code == 200, status.text
    sbody = status.json()
    assert sbody["status"] == "completed"
    assert sbody["outputs"], f"GET status carried no outputs for sync job: {sbody}"
    assert sbody["session_id"] == "ab-session-marker", (
        f"GET status must report the submitted session, not the flow id: {sbody['session_id']}"
    )


async def test_sync_run_does_not_persist_result_by_default(client, created_api_key, bg_flow):
    """With the flag OFF (default), a sync run leaves Job.result unwritten.

    The caller already holds outputs + session inline, so the default path adds no
    per-request result write. GET status still works via vertex-build reconstruction,
    which resolves the REAL session (the pre-#14353 path) — never the flow id.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job

    body = {"flow_id": bg_flow, "mode": "sync", "input_value": "hi", "session_id": "ab-session-marker"}
    resp = await client.post("api/v2/workflows", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["session_id"] == "ab-session-marker"
    job_id = data["job_id"]

    # Default off: no result blob cached.
    async with session_scope() as session:
        row = await session.get(Job, UUID(job_id))
    assert row is not None
    assert not (isinstance(row.result, dict) and row.result.get("outputs")), (
        f"sync result should not be cached when the flag is off: {row.result!r}"
    )

    # GET status still resolves the real session via vertex-build reconstruction.
    status = await client.get("api/v2/workflows", params={"job_id": job_id}, headers=_headers(created_api_key))
    assert status.status_code == 200, status.text
    sbody = status.json()
    assert sbody["session_id"] == "ab-session-marker", (
        f"reconstruction must report the submitted session, not the flow id: {sbody['session_id']}"
    )


async def test_sync_run_survives_result_persist_db_error(client, created_api_key, bg_flow, monkeypatch):
    """A DB failure while caching the sync result must NOT fail the successful run.

    ``_persist_sync_result`` runs only AFTER the workflow has executed and the
    inline response is built, so every error it can raise is a persistence
    failure, never a workflow failure. A ``set_result`` DB error (here a SQLite
    ``OperationalError`` — not in the old ``(RuntimeError, ValueError, OSError)``
    tuple) used to escape and be misreported by the terminal ``except Exception``
    as a FAILED run. Assert the run still returns 200 ``completed`` with outputs,
    that ``Job.result`` was left unwritten (persistence genuinely failed), and that
    GET status still reports the REAL session — never a flow-id degradation. The
    request blob is written BEFORE the result, so a result-write failure can never
    leave a cached result paired with a degraded session (the invariant).
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job
    from langflow.services.jobs.service import JobService
    from sqlalchemy.exc import OperationalError

    _enable_sync_persistence(monkeypatch)

    async def _raise_locked(self, *args, **kwargs):  # noqa: ARG001
        statement = "UPDATE jobs SET result=?"
        raise OperationalError(statement, {}, Exception("database is locked"))

    monkeypatch.setattr(JobService, "set_result", _raise_locked)

    body = {"flow_id": bg_flow, "mode": "sync", "input_value": "hi", "session_id": "ab-session-marker"}
    resp = await client.post("api/v2/workflows", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # The run succeeded despite the cache write blowing up.
    assert data["status"] == "completed", f"persistence error leaked into run status: {data}"
    assert data["outputs"], f"successful sync run returned no outputs: {data}"

    # Persistence really did fail — Job.result stays unwritten, GET status then
    # falls back to vertex-build reconstruction (graceful degradation).
    async with session_scope() as session:
        row = await session.get(Job, UUID(data["job_id"]))
    assert row is not None
    assert not (isinstance(row.result, dict) and row.result.get("outputs")), (
        f"Job.result should be unwritten after a set_result failure: {row.result!r}"
    )

    # Invariant: a result-write failure never yields a degraded-session GET.
    status = await client.get("api/v2/workflows", params={"job_id": data["job_id"]}, headers=_headers(created_api_key))
    assert status.status_code == 200, status.text
    assert status.json()["session_id"] == "ab-session-marker", (
        f"result-persist failure must not degrade GET session to the flow id: {status.json()['session_id']}"
    )
