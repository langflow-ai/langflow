"""LE-1695 acceptance (seam-independent): a paused run survives a process restart.

Drives the REAL pause/resume machinery (``graph.process`` + ``GraphPausedException`` +
``resume_from_checkpoint``) against the durable SQLite stores. The "restart" is a fresh
store instance on the same file — everything in memory is discarded, exactly like a new
process — and the run must resume to completion without re-executing built vertices.
"""

from __future__ import annotations

import pytest
from lfx.components.flow_controls.human_input import HumanInput
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph.exceptions import GraphPausedException
from lfx.graph.graph.base import Graph
from lfx.schema.schema import INPUT_FIELD_NAME
from lfx.services.durable.models import JobStatus
from lfx.services.durable.sqlite_checkpoints import SqliteCheckpointStore
from lfx.services.durable.sqlite_store import SqliteDurableJobStore

JOB_ID = "job-restart-1"


def _node(component) -> dict:
    frontend = component.to_frontend_node()
    return {"id": frontend["id"], "data": frontend["data"]}


def _edge(source: str, target: str, handle: str, field: str = "input_value") -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{handle}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": handle, "output_types": ["Message"]},
            "targetHandle": {"fieldName": field, "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


def _pausing_graph() -> Graph:
    payload = {
        "nodes": [
            _node(ChatInput(_id="chat_input")),
            _node(HumanInput(_id="hitl1")),
            _node(ChatOutput(_id="co_approve")),
            _node(ChatOutput(_id="co_reject")),
        ],
        "edges": [
            _edge("chat_input", "hitl1", "message", field="prompt"),
            _edge("hitl1", "co_approve", "branch_approve"),
            _edge("hitl1", "co_reject", "branch_reject"),
        ],
    }
    graph = Graph.from_payload(payload, flow_id="durable-restart")
    graph.prepare()
    return graph


@pytest.mark.asyncio
async def test_suspended_run_resumes_to_completion_after_restart(tmp_path):
    db_path = tmp_path / "durable.db"
    jobs = SqliteDurableJobStore(db_path)
    checkpoints = SqliteCheckpointStore(db_path)

    graph = _pausing_graph()
    graph.job_id = JOB_ID
    graph.checkpointing_enabled = True
    graph.checkpoint_store = checkpoints
    graph._set_inputs([], {INPUT_FIELD_NAME: "hello"}, "chat")
    await jobs.create_job(job_id=JOB_ID, flow_id="durable-restart", user_id="u1")
    await jobs.update_status(JOB_ID, JobStatus.IN_PROGRESS)

    with pytest.raises(GraphPausedException) as pause:
        await graph.process(fallback_to_env_vars=False)
    await jobs.update_status(JOB_ID, JobStatus.SUSPENDED)
    request_id = (pause.value.data or {}).get("request_id")
    run_id = str(graph.run_id)

    # ---- "process restart": all live objects are gone; only the SQLite file remains ----
    del graph, jobs, checkpoints
    jobs_after = SqliteDurableJobStore(db_path)
    checkpoints_after = SqliteCheckpointStore(db_path)

    assert (await jobs_after.get_job(JOB_ID)).status == JobStatus.SUSPENDED
    assert await jobs_after.claim_suspended_for_resume(JOB_ID) is True

    checkpoint = await checkpoints_after.load_by_run_id(run_id)
    assert checkpoint is not None
    resumed = Graph.resume_from_checkpoint(checkpoint, checkpoint_store=checkpoints_after)
    resumed.checkpointing_enabled = True
    resumed.checkpoint_store = checkpoints_after
    resumed.human_input_decisions = {request_id: {"action_id": "approve", "values": {}}}
    for vertex in resumed.vertices:
        if f"{vertex.id}:{resumed.run_id}" == request_id:
            vertex.built = False

    await resumed.process(fallback_to_env_vars=False)
    await jobs_after.set_result(JOB_ID, {"status": "completed"})

    assert (await jobs_after.get_job(JOB_ID)).status == JobStatus.COMPLETED
    assert resumed.get_vertex("co_approve").built is True
    assert resumed.get_vertex("co_reject").built is False
    # Built-before-the-pause vertices were restored, not re-executed.
    assert resumed.get_vertex("chat_input").built is True
