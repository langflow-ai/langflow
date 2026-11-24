"""Pre-pause terminal outputs survive a HITL resume (Claim 1 fix).

A run that produces a terminal output on one branch, then pauses for human input
on another, must NOT lose that output. On suspend the runner stashes the pre-pause
captures in ``job_metadata``; on resume it pre-seeds the (otherwise fresh) capture
list from that stash, so the completed-run ``Job.result`` carries both the pre- and
post-pause outputs. A resumed pass that re-emits a branch overwrites the stale entry
rather than duplicating it (dedup by ``component_id``, resumed pass wins).
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import HUMAN_INPUT_REQUIRED_EVENT, JobRunner
from langflow.services.database.models.jobs.model import JobStatus, SignalType
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
from lfx.workflow.adapters.langflow import WORKFLOW_OUTPUT_CAPTURE_EVENT


def _capture_frame(component_id: str, content: str) -> tuple[bytes, str]:
    """A terminal-output capture frame (off-wire OutputEvent carrying a component id)."""
    payload = {"data": {"component_id": component_id, "type": "message", "content": content}}
    return (json.dumps(payload).encode(), WORKFLOW_OUTPUT_CAPTURE_EVENT)


def _pause_frame(payload: dict) -> tuple[bytes, str]:
    return (json.dumps(payload).encode(), HUMAN_INPUT_REQUIRED_EVENT)


def _end_frame() -> tuple[bytes, str]:
    return (json.dumps({"event": "end", "data": {}}).encode(), "end")


def _adapter(job_id):
    return get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))


def _durable_store(job_service):
    from langflow.services.checkpoint.store import JobScopedCheckpointStore

    return JobScopedCheckpointStore(job_service)


def _branch_a_then_pause(payload: dict):
    """Branch A emits a terminal output, then the run pauses for human input."""

    async def _source(**_kwargs):
        yield _capture_frame("comp-A", "branch A output")
        yield _pause_frame(payload)

    return _source


async def _noop_hook(_checkpoint, _decision):
    return None


async def _suspend_with_branch_a(job_service, job_id, *, request_id="req-1"):
    payload = {"reason": "human_input_required", "request_id": request_id, "options": ["approve"]}
    runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=_adapter(job_id),
        frame_source=_branch_a_then_pause(payload),
    )
    await runner.run(job_id=job_id, source_kwargs={})


async def _arm_resume(job_service, job_id, *, request_id="req-1"):
    store = _durable_store(job_service)
    await store.save(
        GraphCheckpoint(
            run_id=str(job_id),
            job_id=str(job_id),
            flow_id="flow-1",
            session_id="sess-1",
            flow_payload={"nodes": [], "edges": []},
            vertices_to_run={"comp-B"},
        )
    )
    await job_service.write_signal(
        job_id, SignalType.RESUME, {"decision": {"choice": "approve"}, "request_id": request_id}
    )
    return store


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_suspend_stashes_pre_pause_outputs(real_services_job_service) -> None:
    """The suspend path records the pre-pause terminal outputs in job_metadata."""
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    await _suspend_with_branch_a(job_service, job_id)

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.SUSPENDED
    assert job.result is None  # not finalized
    stash = (job.job_metadata or {}).get("pre_pause_outputs")
    assert stash is not None
    assert [e["component_id"] for e in stash] == ["comp-A"]


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_pre_pause_output_survives_into_completed_result(real_services_job_service) -> None:
    """After resume completes, Job.result carries BOTH the pre-pause and post-pause outputs."""
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    await _suspend_with_branch_a(job_service, job_id)
    store = await _arm_resume(job_service, job_id)

    def _branch_b_then_end():
        async def _source(**_kwargs):
            yield _capture_frame("comp-B", "branch B output")
            yield _end_frame()

        return _source

    resume_runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=_adapter(job_id),
        frame_source=_branch_b_then_end(),
        resume_hook=_noop_hook,
        checkpoint_store=store,
    )
    await resume_runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    assert job.status == JobStatus.COMPLETED
    outputs = job.result["outputs"]
    # Branch A preserved and ahead of branch B (first-seen position, no loss).
    assert [o["component_id"] for o in outputs] == ["comp-A", "comp-B"]


@pytest.mark.real_services
@pytest.mark.no_blockbuster
async def test_resumed_reemit_overwrites_stale_entry_without_duplicate(real_services_job_service) -> None:
    """A vertex re-emitted after resume overwrites its pre-pause value — no duplicate row."""
    job_service = real_services_job_service
    job_id, flow_id = uuid4(), uuid4()
    await job_service.create_job(job_id=job_id, flow_id=flow_id, user_id=uuid4())

    await _suspend_with_branch_a(job_service, job_id)
    store = await _arm_resume(job_service, job_id)

    def _reemit_a_then_b():
        async def _source(**_kwargs):
            yield _capture_frame("comp-A", "branch A RE-EMITTED")
            yield _capture_frame("comp-B", "branch B output")
            yield _end_frame()

        return _source

    resume_runner = JobRunner(
        job_service=job_service,
        live_bus=InMemoryLiveBus(),
        adapter=_adapter(job_id),
        frame_source=_reemit_a_then_b(),
        resume_hook=_noop_hook,
        checkpoint_store=store,
    )
    await resume_runner.run(job_id=job_id, source_kwargs={})

    job = await job_service.get_job_by_job_id(job_id)
    outputs = job.result["outputs"]
    assert [o["component_id"] for o in outputs] == ["comp-A", "comp-B"]  # no duplicate comp-A
    comp_a = next(o for o in outputs if o["component_id"] == "comp-A")
    assert comp_a["content"] == "branch A RE-EMITTED"  # resumed pass wins
