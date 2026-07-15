"""Contract tests for the v2 workflow endpoints on the BackgroundExecutionService.

Phase 2 already routed the background POST / events / stop branches through the
facade. These tests close the Phase 3 endpoint-layer gaps and pin the wire
contract so the cutover stays backward compatible:

* ``links.events`` is part of the ``WorkflowJobResponse`` shape (additive).
* an optional ``idempotency_key`` dedupes background submits (returns the same
  job_id rather than queuing duplicate work).
* a re-enqueued QUEUED job (restart-surviving) replays its ORIGINAL inputs,
  because the submit request is persisted on the job row.
* ``GET`` status surfaces the durable ``Job.error`` additively without changing
  the top-level ``WorkflowJobResponse`` / ``WorkflowExecutionResponse`` shape.

Real client + real flows, no mocking of our own code.
"""

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope


async def _wait_terminal(job_id: str) -> "object":
    """Poll the durable Job row until it reaches a terminal state.

    Condition-based (not a fixed sleep): returns the final status enum.
    """
    from langflow.services.database.models.jobs.model import Job, JobStatus

    terminal = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMED_OUT}
    for _ in range(200):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in terminal:
            return row.status
        await asyncio.sleep(0.05)
    pytest.fail(f"job {job_id} did not reach a terminal state")
    return None


def _body(flow_id, *, message: str = "hello", mode: str = "background", protocol: str = "langflow") -> dict:
    return {
        "flow_id": str(flow_id),
        "input_value": message,
        "mode": mode,
        "stream_protocol": protocol,
        "session_id": "thread-1",
    }


@pytest.fixture
async def chatbot_flow(created_api_key, json_memory_chatbot_no_llm):
    """Create a real no-LLM chatbot flow owned by the API-key user."""
    raw = json.loads(json_memory_chatbot_no_llm)
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="Facade Chatbot Flow",
            description="No-LLM chatbot flow for facade endpoint tests",
            data=raw.get("data", raw),
            user_id=created_api_key.user_id,
        )
        session.add(flow)
        await session.flush()
    yield flow_id
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


class TestBackgroundSubmitContract:
    """mode=background returns the unchanged WorkflowJobResponse wire shape."""

    async def test_background_returns_job_response_shape(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """POST mode=background returns a WorkflowJobResponse with the same fields."""
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflows",
            json=_body(chatbot_flow, mode="background"),
            headers=headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["object"] == "job"
        assert result["flow_id"] == str(chatbot_flow)
        assert result["status"] == "queued"
        assert result.get("job_id")
        # Unchanged links: status + stop.
        assert result["links"]["status"] == f"/api/v2/workflows?job_id={result['job_id']}"
        assert result["links"]["stop"] == "/api/v2/workflows/stop"
        # New additive link: re-attach events URL must point at the job.
        assert result["links"]["events"] == f"/api/v2/workflows/{result['job_id']}/events"


class TestStatusDurableResultError:
    """GET status reads durable result/error written by the runner, additively."""

    async def test_completed_background_run_status_returns_completed(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A finished background run reports completed via GET status (not a 500).

        The background path does not persist vertex_build rows keyed by job_id,
        so the status endpoint must fall back to the durable Job.result rather
        than 500 on an empty vertex-build reconstruction.
        """
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        from langflow.services.database.models.jobs.model import JobStatus

        assert await _wait_terminal(job_id) == JobStatus.COMPLETED

        status_resp = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

        assert status_resp.status_code == 200, status_resp.text
        result = status_resp.json()
        assert result["status"] == "completed"
        assert result["flow_id"] == str(chatbot_flow)

    async def test_failed_background_run_status_carries_durable_error(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """A failed run surfaces the durable error JSON additively in the detail.

        The top-level ``error`` string stays unchanged; the stored error blob the
        runner persisted rides under ``error_detail`` so the wire contract is
        additive-only.
        """
        headers = {"x-api-key": created_api_key.api_key}
        # A flow whose data is corrupt fails during the background run; the runner
        # persists the durable error which status echoes additively.
        bad_flow = uuid4()
        async with session_scope() as session:
            flow = Flow(
                id=bad_flow,
                name="Facade Bad Flow",
                description="Corrupt flow that fails at build time",
                data={"nodes": [{"id": "broken"}], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()

        try:
            start = await client.post(
                "api/v2/workflows",
                json=_body(bad_flow, mode="background"),
                headers=headers,
            )
            assert start.status_code == 200
            job_id = start.json()["job_id"]

            from langflow.services.database.models.jobs.model import JobStatus

            assert await _wait_terminal(job_id) == JobStatus.FAILED

            status_resp = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert status_resp.status_code == 500
            detail = status_resp.json()["detail"]
            assert detail["code"] == "JOB_FAILED"
            assert detail["job_id"] == job_id
            # Unchanged top-level error string + additive durable error blob.
            assert detail["error"] == "Job failed"
            assert detail["error_detail"] is not None
        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, bad_flow)
                if flow:
                    await session.delete(flow)


class TestIdempotentSubmit:
    """An optional idempotency_key dedupes background submits via dedupe_key."""

    async def test_repeated_idempotency_key_returns_same_job(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Two background submits with the same idempotency_key share one job_id."""
        headers = {"x-api-key": created_api_key.api_key}
        key = f"idem-{uuid4()}"
        body = _body(chatbot_flow, mode="background")
        body["idempotency_key"] = key

        first = await client.post("api/v2/workflows", json=body, headers=headers)
        second = await client.post("api/v2/workflows", json=body, headers=headers)

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["job_id"] == second.json()["job_id"]

    async def test_no_idempotency_key_creates_distinct_jobs(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Without an idempotency_key, repeated submits create distinct jobs."""
        headers = {"x-api-key": created_api_key.api_key}
        body = _body(chatbot_flow, mode="background")

        first = await client.post("api/v2/workflows", json=body, headers=headers)
        second = await client.post("api/v2/workflows", json=body, headers=headers)

        assert first.json()["job_id"] != second.json()["job_id"]


class TestNoBreakingChange:
    """Pin the wire contract so the facade additions stay backward compatible."""

    async def test_job_response_field_set_is_unchanged(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """The WorkflowJobResponse top-level keys are exactly the documented set.

        Additions live under ``links`` (the new ``events`` URL); no top-level key
        was added, removed, or renamed, so existing background clients keep
        parsing the same shape.
        """
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflows",
            json=_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert response.status_code == 200
        result = response.json()
        assert set(result.keys()) == {
            "job_id",
            "flow_id",
            "object",
            "created_timestamp",
            "status",
            "links",
            "errors",
            "globals",
        }
        # links is additive-only: status + stop preserved, events added.
        assert set(result["links"].keys()) == {"status", "events", "stop"}

    async def test_submit_events_link_serves_the_stream_with_sse_ids(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """The links.events URL replays the run as an SSE stream carrying id: lines.

        Pins the Last-Event-ID resume contract: each durable frame carries a
        monotonic ``id:`` line so a dropped client resumes from where it left off.
        """
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        events_link = start.json()["links"]["events"].lstrip("/")

        response = await client.get(events_link, headers=headers)

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        event_ids = [int(line.removeprefix("id:").strip()) for line in body.splitlines() if line.startswith("id:")]
        # Monotonic, gap-free ids so a dropped client can resume by id.
        assert event_ids, "expected SSE frames to carry id: lines"
        assert event_ids == list(range(event_ids[0], event_ids[0] + len(event_ids)))

    async def test_last_event_id_at_end_replays_nothing(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Re-attaching past the last durable seq replays no further durable events.

        The durable resume cursor is the ``job_events.seq`` (1-based). After the
        run completes, re-attaching with a Last-Event-ID at/beyond the highest
        durable seq must yield an empty durable replay — the resume contract that
        lets a caller who has seen everything reconnect without a flood.
        """
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        job_id = start.json()["job_id"]

        from langflow.services.database.models.jobs.model import JobStatus

        assert await _wait_terminal(job_id) == JobStatus.COMPLETED

        # Highest durable seq actually written for this run.
        from langflow.services.deps import get_job_service

        rows = await get_job_service().read_events(UUID(job_id), after_seq=0)
        assert rows, "expected the completed run to have durable events"
        last_seq = max(r.seq for r in rows)

        response = await client.get(
            f"api/v2/workflows/{job_id}/events",
            headers={**headers, "Last-Event-ID": str(last_seq)},
        )

        assert response.status_code == 200
        # Nothing after the last durable seq: the run is closed and fully seen.
        replayed = [line for line in response.text.splitlines() if line.startswith("data:")]
        assert replayed == []


class TestDeadMachineryRemoved:
    """The process-local background buffer machinery is gone after the cutover.

    ``execute_workflow_background`` is intentionally kept: it is now a thin
    facade-delegating wrapper (builds the request dict, threads idempotency_key),
    not the old in-memory run loop, so it is NOT in this list.
    """

    def test_in_memory_background_machinery_is_deleted(self):
        """The old _BackgroundRun buffer and its helpers no longer exist."""
        from langflow.api.v2 import workflow as wf

        for name in (
            "_BackgroundRun",
            "_BACKGROUND_RUNS",
            "_register_background_run",
            "_clear_background_run",
            "_buffer_background_run",
            "_finalize_job_status",
            "_MAX_BACKGROUND_RUNS",
            "_MAX_FRAMES_PER_BACKGROUND_RUN",
        ):
            assert not hasattr(wf, name), f"{name} should have been deleted in the facade cutover"
