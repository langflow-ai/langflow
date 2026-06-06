"""V2 Workflow endpoint tests covering the native ``WorkflowRunRequest`` body.

The v2 ``POST /workflows`` endpoint accepts a Langflow-native body shape and
dispatches the stream protocol from ``stream_protocol`` (``langflow`` default,
``agui`` opt-in). Tests in this module pin the ``agui`` protocol so the
AG-UI-shaped assertions still apply end-to-end.

Execution mode (``mode`` field):
    - ``sync`` (default): run inline, return the aggregated WorkflowExecutionResponse.
    - ``background``: queue a job, return a WorkflowJobResponse.
    - ``stream``: SSE in the chosen ``stream_protocol``.
"""

import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope


def _agui_body(flow_id, *, message: str = "hello", mode: str = "sync", tweaks: dict | None = None) -> dict:
    """Build a ``WorkflowRunRequest`` JSON body pinned to the ``agui`` protocol.

    Pinning the protocol keeps the AG-UI assertions in this module valid after
    the cutover from the ``RunAgentInput`` body shape.
    """
    body: dict = {
        "flow_id": str(flow_id),
        "input_value": message,
        "mode": mode,
        "stream_protocol": "agui",
        "session_id": "thread-1",
    }
    if tweaks:
        body["tweaks"] = tweaks
    return body


@pytest.fixture
async def empty_flow(created_api_key):
    """Create a real empty flow owned by the API-key user; clean it up after."""
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="AG-UI Test Flow",
            description="Empty flow for AG-UI endpoint tests",
            data={"nodes": [], "edges": []},
            user_id=created_api_key.user_id,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
    yield flow_id
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


@pytest.fixture
async def chatbot_flow(created_api_key, json_memory_chatbot_no_llm):
    """Create a real no-LLM chatbot flow (ChatInput -> Prompt/Memory -> ChatOutput)."""
    raw = json.loads(json_memory_chatbot_no_llm)
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="AG-UI Chatbot Flow",
            description="No-LLM chatbot flow for AG-UI endpoint tests",
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


class TestAGUIRequestContract:
    """The endpoint accepts the AG-UI RunAgentInput body shape."""

    async def test_sync_mode_with_real_flow_returns_200(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """A RunAgentInput body with mode=sync runs the flow inline and returns 200."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(empty_flow, mode="sync"),
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["flow_id"] == str(empty_flow)
        assert "job_id" in result
        assert isinstance(result["outputs"], dict)

    async def test_unknown_flow_returns_404(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """A body whose flow_id does not exist returns 404."""
        missing = "550e8400-e29b-41d4-a716-446655440000"
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(missing, mode="sync"),
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "FLOW_NOT_FOUND"

    async def test_missing_flow_id_returns_422(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """A body without ``flow_id`` fails Pydantic validation up front."""
        response = await client.post(
            "api/v2/workflows",
            json={"input_value": "hi", "mode": "sync"},
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 422

    async def test_requires_authentication(
        self,
        client: AsyncClient,
        empty_flow,
    ):
        """An AG-UI request with no API key and no session token is rejected."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(empty_flow, mode="sync"),
        )

        assert response.status_code == 403

    async def test_accepts_session_token_auth(
        self,
        client: AsyncClient,
        logged_in_headers,
    ):
        """The endpoint accepts a session token, not only an API key."""
        missing = "550e8400-e29b-41d4-a716-446655440000"
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(missing, mode="sync"),
            headers=logged_in_headers,
        )

        # Auth passes via the session token; 404 only because the flow does not exist.
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "FLOW_NOT_FOUND"

    async def test_rejects_non_agui_body(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """The old flat {flow_id, background, stream, inputs} body is no longer valid."""
        response = await client.post(
            "api/v2/workflows",
            json={"flow_id": str(uuid4()), "background": False, "stream": False, "inputs": None},
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 422


class TestAGUIModeDispatch:
    """``mode`` field selects the execution path."""

    async def test_background_mode_returns_job_response(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """mode=background queues a job and returns a job id."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(empty_flow, mode="background"),
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["flow_id"] == str(empty_flow)
        assert result["job_id"]
        assert result["status"] in {"queued", "in_progress", "completed"}

    async def test_sync_mode_is_default(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """Omitting mode defaults to sync (curl-DX: one POST returns one JSON)."""
        body = _agui_body(empty_flow)
        body.pop("mode")
        response = await client.post(
            "api/v2/workflows",
            json=body,
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        result = response.json()
        assert result["status"] == "completed"


class TestAGUIStreaming:
    """mode=stream returns an AG-UI server-sent event stream."""

    async def test_stream_emits_run_lifecycle_events(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """A streamed run brackets its events with RUN_STARTED and RUN_FINISHED."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(empty_flow, mode="stream"),
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "RUN_STARTED" in body
        assert "RUN_FINISHED" in body

    async def test_stream_unknown_flow_returns_404(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """A stream-mode request for a missing flow fails before streaming starts."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body("550e8400-e29b-41d4-a716-446655440000", mode="stream"),
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "FLOW_NOT_FOUND"

    async def test_stream_real_flow_runs_without_error(
        self,
        client: AsyncClient,
        created_api_key,
        json_memory_chatbot_no_llm,
    ):
        """Streaming a real no-LLM chatbot flow runs the graph end-to-end with no RUN_ERROR."""
        raw = json.loads(json_memory_chatbot_no_llm)
        flow_data = raw.get("data", raw)
        flow_id = uuid4()
        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="AG-UI Memory Chatbot Flow",
                data=flow_data,
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()

        try:
            response = await client.post(
                "api/v2/workflows",
                json=_agui_body(flow_id, message="hello from agui", mode="stream"),
                headers={"x-api-key": created_api_key.api_key},
            )

            assert response.status_code == 200
            body = response.text
            assert "RUN_STARTED" in body
            assert "RUN_FINISHED" in body
            assert "RUN_ERROR" not in body
            # The ChatOutput component's message reached the stream as AG-UI
            # text-message events, proving the real event pipeline works.
            assert "TEXT_MESSAGE_START" in body
            assert "TEXT_MESSAGE_CONTENT" in body
            # Per-vertex events flow through the translator (v1 build-vertex
            # loop emits end_vertex per node) so the canvas can color nodes.
            assert "STEP_FINISHED" in body
            assert "STATE_DELTA" in body
        finally:
            async with session_scope() as session:
                flow = await session.get(Flow, flow_id)
                if flow:
                    await session.delete(flow)


class TestAGUISyncExecution:
    """mode=sync runs the flow inline and folds outputs into the response."""

    async def test_sync_real_flow_returns_completed_with_outputs(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A sync run of a real chatbot flow completes with the terminal outputs."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hello from agui", mode="sync"),
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "completed"
        assert result["errors"] == []
        assert isinstance(result["outputs"], dict)
        # The chatbot flow produced at least one terminal output.
        assert result["outputs"]


class TestOutputIdsSelection:
    """Request-side ``output_ids`` steers ``output.text`` and is validated pre-run."""

    async def test_unknown_output_id_rejected_before_running(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A typo'd output id is rejected with 422 and the available ids, no run."""
        body = _agui_body(chatbot_flow, message="hi", mode="sync")
        body["output_ids"] = ["NotARealOutput-zzz"]

        response = await client.post(
            "api/v2/workflows",
            json=body,
            headers={"x-api-key": created_api_key.api_key},
        )

        # 422 (a request rejection), NOT a 200-with-failed component error.
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "NotARealOutput-zzz" in str(detail)
        assert detail["available"]  # the flow's real output ids

    async def test_selecting_the_real_output_yields_single(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Naming the flow's text output makes ``output.reason`` deterministically single."""
        headers = {"x-api-key": created_api_key.api_key}

        # Discover the flow's text output id from an unselected run.
        first = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="sync"),
            headers=headers,
        )
        assert first.status_code == 200
        outputs = first.json()["outputs"]
        text_id = next(cid for cid, out in outputs.items() if out["type"] in {"message", "text"})

        body = _agui_body(chatbot_flow, message="hi again", mode="sync")
        body["output_ids"] = [text_id]
        second = await client.post("api/v2/workflows", json=body, headers=headers)

        assert second.status_code == 200
        result = second.json()
        assert result["output"]["reason"] == "single"
        assert result["output"]["source"] == text_id
        assert result["output"]["text"] is not None
        # Selection steers the answer; the full outputs map is still present.
        assert text_id in result["outputs"]


class TestLangflowStreamOutputParity:
    """The ``langflow`` stream emits per-output ``output`` events that share sync's PARSER.

    One handler reads ``component_id``/``type``/``status``/``display_name``/``content`` off
    both the sync ``outputs`` map and the stream ``output`` events: same fields, same
    component SET (terminals), same type/display_name/status. ``content`` is each mode's
    own serialization — the framework serializes a Message differently in the per-vertex
    ``VertexBuildResponse`` (stream) than in the final ``RunResponse`` (sync), so this
    asserts structural parity, not byte-identical content.
    """

    async def test_stream_output_events_share_sync_shape(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        headers = {"x-api-key": created_api_key.api_key}

        sync = await client.post(
            "api/v2/workflows",
            json={"flow_id": str(chatbot_flow), "input_value": "hi", "mode": "sync", "session_id": "sync-1"},
            headers=headers,
        )
        assert sync.status_code == 200
        sync_outputs = sync.json()["outputs"]
        assert sync_outputs

        # Stream run with the DEFAULT protocol (langflow, not agui).
        stream = await client.post(
            "api/v2/workflows",
            json={"flow_id": str(chatbot_flow), "input_value": "hi", "mode": "stream", "session_id": "stream-1"},
            headers=headers,
        )
        assert stream.status_code == 200

        output_events: dict[str, dict] = {}
        for raw in stream.text.splitlines():
            line = raw.strip()
            if not line.startswith("data:"):
                continue
            payload = json.loads(line[len("data:") :].strip())
            if payload.get("event") == "output":
                data = payload["data"]
                output_events[data["component_id"]] = data

        # The langflow stream emitted a normalized output event for the SAME set sync reports.
        assert output_events
        assert set(output_events) == set(sync_outputs)
        for component_id, streamed in output_events.items():
            synced = sync_outputs[component_id]
            # Same parser: identical field set and identical identity/type/lifecycle fields.
            assert set(streamed) == set(synced) | {"component_id"}
            assert streamed["type"] == synced["type"]
            assert streamed["display_name"] == synced["display_name"]
            assert streamed["status"] == synced["status"]


class TestAGUICancellation:
    """A run can be stopped by job id, and a streaming client can disconnect."""

    async def test_background_run_can_be_stopped(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """POST /workflows/stop cancels a background run by its job id."""
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        stop = await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=headers)

        assert stop.status_code == 200
        assert "cancelled" in stop.json()["message"].lower()

    async def test_streaming_client_can_disconnect_early(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Closing the SSE stream after the first event does not error the server."""
        headers = {"x-api-key": created_api_key.api_key}
        seen: list[str] = []
        async with client.stream(
            "POST",
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="stream"),
            headers=headers,
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    seen.append(line)
                    break  # disconnect mid-stream

        # The stream delivered at least one event before the client disconnected.
        assert seen


class TestAGUIBackgroundReattach:
    """A background run buffers its AG-UI events so a client can re-attach."""

    async def test_background_run_events_can_be_reattached(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """After starting a background run, GET /workflows/{job_id}/events replays its stream."""
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        response = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "RUN_STARTED" in body
        assert "RUN_FINISHED" in body

    async def test_reattach_replays_after_last_event_id(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Re-attaching with a Last-Event-ID header skips already-delivered events."""
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        job_id = start.json()["job_id"]

        response = await client.get(
            f"api/v2/workflows/{job_id}/events",
            headers={**headers, "Last-Event-ID": "0"},
        )

        assert response.status_code == 200
        body = response.text
        # Event 0 is RUN_STARTED; with Last-Event-ID=0 it must not be replayed.
        # Split per line so CRLF endings don't sneak the event through the
        # substring check.
        event_ids = [line.removeprefix("id:").strip() for line in body.splitlines() if line.startswith("id:")]
        assert "0" not in event_ids
        assert "RUN_FINISHED" in body

    async def test_reattach_unknown_job_returns_404(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Re-attaching to a job id with no background run returns 404."""
        response = await client.get(
            "api/v2/workflows/550e8400-e29b-41d4-a716-446655440000/events",
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 404

    async def test_reattach_forbidden_for_other_user(
        self,
        client: AsyncClient,
        created_api_key,
        created_user_two_api_key,
        chatbot_flow,
    ):
        """A background run's event stream is not readable by another user."""
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers={"x-api-key": created_api_key.api_key},
        )
        job_id = start.json()["job_id"]

        response = await client.get(
            f"api/v2/workflows/{job_id}/events",
            headers={"x-api-key": created_user_two_api_key.api_key},
        )

        assert response.status_code == 404


class TestAGUIBackgroundJobStatus:
    """Background job status comes from the translator's terminal event.

    A substring scan over serialized SSE frames would false-positive on any
    payload that happened to contain the literal byte sequence ``"RUN_ERROR"``.
    """

    async def test_message_text_containing_run_error_literal_does_not_fail_job(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A user message JSON-encoded as ``"RUN_ERROR"`` must not fail the job.

        That string is exactly what the translator emits for ``RunErrorEvent``,
        so a byte-substring detector would false-positive on it.
        """
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            # The chat input is the bare literal ``RUN_ERROR``; once JSON-encoded
            # into the side-channel CustomEvent it appears as ``"RUN_ERROR"``.
            json=_agui_body(chatbot_flow, message="RUN_ERROR", mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        # Drain the SSE buffer; the background task finalizes job status in finally.
        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        assert "RUN_FINISHED" in events.text

        # ``update_job_status`` runs after the events stream returns; poll the
        # Job row directly so this test exercises the status-finalization path
        # without depending on vertex-build reconstruction.
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        final_status = None
        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                final_status = row.status if row is not None else None
            if final_status is not None and final_status.value in ("completed", "failed"):
                break
            await _asyncio.sleep(0.1)
        assert final_status is not None, "job row was never created"
        assert final_status.value == "completed", (
            f"Background job was marked {final_status.value!r}; the message text contained "
            "the literal 'RUN_ERROR' so the byte-substring detector would false-positive"
        )

    async def test_message_with_json_shaped_run_error_payload_does_not_fail_job(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A chat message that mimics a serialized AG-UI RunErrorEvent must not fail the job.

        Even when the user's text echoes the exact JSON the translator would emit
        for a real RUN_ERROR (``{"type":"RUN_ERROR", ...}``), the structural detector
        keys off the translator's event type, not bytes inside a CustomEvent payload.
        """
        headers = {"x-api-key": created_api_key.api_key}
        echo = '{"type":"RUN_ERROR","message":"fake","timestamp":1}'
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message=echo, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        assert "RUN_FINISHED" in events.text
        # The user's text appears inside a CustomEvent (side-channel) whose type
        # attribute is CUSTOM. The substring scan would false-positive on
        # ``"type":"RUN_ERROR"`` inside that payload; the structural check ignores it.

        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        final_status = None
        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                final_status = row.status if row is not None else None
            if final_status is not None and final_status.value in ("completed", "failed"):
                break
            await _asyncio.sleep(0.1)
        assert final_status is not None, "job row was never created"
        assert final_status.value == "completed", (
            f"Background job was marked {final_status.value!r}; the message echoed a "
            "serialized RUN_ERROR payload, which a substring scan would have flagged"
        )

    async def test_genuine_flow_failure_marks_job_as_failed(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A run that actually errors must still be marked FAILED by the structural detector.

        The fix replaced a byte-substring scan with a check on the translator's
        event type. Confirm a real RunErrorEvent (type=RUN_ERROR) still flips
        the job to FAILED -- otherwise the fix would have a hole that hides
        every error.

        We force a failure by overriding the flow's data with an edge that
        references a vertex id with no matching node. The graph build raises
        ``Vertex a not found``; drive() catches it, dispatches an ``error``
        side-channel event, and the translator emits a real RunErrorEvent.
        """
        headers = {"x-api-key": created_api_key.api_key}
        body = _agui_body(chatbot_flow, message="hi", mode="background")
        body["data"] = {
            "nodes": [],
            "edges": [{"source": "a", "target": "b"}],
        }

        start = await client.post("api/v2/workflows", json=body, headers=headers)
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        # The stream contains a real RUN_ERROR event from the translator.
        assert "RUN_ERROR" in events.text, (
            "Expected a real RunErrorEvent in the stream; if absent, the test "
            "did not actually force a failure and the FAILED assertion below is meaningless"
        )

        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        final_status = None
        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                final_status = row.status if row is not None else None
            if final_status is not None and final_status.value in ("completed", "failed"):
                break
            await _asyncio.sleep(0.1)
        assert final_status is not None, "job row was never created"
        assert final_status.value == "failed", (
            f"Background job was marked {final_status.value!r}; a real RunErrorEvent "
            "was emitted so the structural detector should have flipped it to FAILED. "
            "If this fails, the fix has a hole: real errors are no longer detected."
        )

    async def test_side_channel_error_event_marks_job_as_failed(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A side-channel ``error`` event must still flip the job to FAILED.

        The translator handles ``error`` by emitting [CustomEvent, RunErrorEvent].
        The CustomEvent wrapper has type=CUSTOM (must not trip the detector);
        the RunErrorEvent has type=RUN_ERROR (must trip it). Net effect: FAILED.
        This is the same fault path used by drive()'s exception handler, exercised
        here through the bogus start_component_id.
        """
        # Reuse the same failure-trigger as the previous test; this asserts the
        # combined dispatch order (CustomEvent first, then RunErrorEvent) yields
        # FAILED, proving the wrapper's CUSTOM type is correctly ignored.
        headers = {"x-api-key": created_api_key.api_key}
        body = _agui_body(chatbot_flow, message="hi", mode="background")
        body["data"] = {
            "nodes": [],
            "edges": [{"source": "a", "target": "b"}],
        }

        start = await client.post("api/v2/workflows", json=body, headers=headers)
        job_id = start.json()["job_id"]
        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200

        # The stream carries both the CustomEvent wrapper (type=CUSTOM, name=langflow.event,
        # value contains event_type="error") AND the RunErrorEvent (type=RUN_ERROR).
        body_text = events.text
        assert "RUN_ERROR" in body_text
        assert '"event_type":"error"' in body_text or '"event_type": "error"' in body_text, (
            "Expected the side-channel error wrapper to appear as a CustomEvent"
        )

        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        final_status = None
        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                final_status = row.status if row is not None else None
            if final_status is not None and final_status.value in ("completed", "failed"):
                break
            await _asyncio.sleep(0.1)
        assert final_status is not None
        assert final_status.value == "failed"


class TestAGUISyncStillWorksAfterTupleYieldRefactor:
    """The tuple-yield refactor changed _agui_event_frames' return type.

    The sync path no longer goes through _buffer_background_run; it goes through
    _execute_streaming_workflow's _frames_only wrapper. Confirm an end-to-end
    sync run still produces a normal completion.
    """

    async def test_sync_mode_still_completes_after_refactor(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A sync run end-to-end should return 200 with status=completed."""
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi from sync", mode="sync"),
            headers={"x-api-key": created_api_key.api_key},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "completed"
        assert result["errors"] == []

    async def test_stream_mode_still_unwraps_tuples_to_bytes(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """The streaming consumer's _frames_only wrapper must unpack (frame, type) to bytes.

        If the wrapper accidentally yielded the tuple, EventSourceResponse would
        choke on the non-bytes value. Run a real flow and confirm we get clean
        SSE frames terminated by RUN_FINISHED.
        """
        response = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi from stream", mode="stream"),
            headers={"x-api-key": created_api_key.api_key},
        )
        assert response.status_code == 200
        body = response.text
        assert "RUN_STARTED" in body
        assert "RUN_FINISHED" in body
        # Every SSE frame should be `data: ...` lines, not Python tuple repr.
        assert "data: " in body
        assert "(b'" not in body, "Tuple leaked into the SSE stream"


class TestAGUIBackgroundTasksLifecycle:
    """Tasks the v1 build path queues via ``BackgroundTasks`` must fire.

    ``generate_flow_events`` registers telemetry, tracing teardown, and other
    callbacks on the ``BackgroundTasks`` instance it is handed. In FastAPI's
    request lifecycle those run after the response is sent. The background-mode
    code path has no response carrying that container, so the buffer task must
    drain the queue explicitly or every queued callback is silently dropped.
    """

    async def test_background_run_drains_queued_background_tasks(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """After a background run ends, the BackgroundTasks queue must be invoked."""
        from langflow.api.v2 import workflow as _workflow_module
        from starlette.background import BackgroundTasks as _Real

        instances: list[_Real] = []

        class RecordingBackgroundTasks(_Real):
            """Observe ``__call__`` so we can verify the queue was drained."""

            def __init__(self) -> None:
                super().__init__()
                self.called = False
                instances.append(self)

            async def __call__(self, *args, **kwargs):
                self.called = True
                return await super().__call__(*args, **kwargs)

        monkeypatch.setattr(_workflow_module, "BackgroundTasks", RecordingBackgroundTasks)

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        # Drain the SSE buffer so _buffer_background_run reaches its finally block.
        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        assert "RUN_FINISHED" in events.text

        # Wait for the buffer task to finalize.
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                if row is not None and row.status.value in ("completed", "failed"):
                    break
            await _asyncio.sleep(0.1)

        assert instances, "No RecordingBackgroundTasks instance was constructed"
        bg = instances[0]
        assert bg.tasks, (
            "generate_flow_events queued no background tasks for the chatbot flow; "
            "this test is vacuous without at least one queued callback"
        )
        assert bg.called, (
            "fresh BackgroundTasks queue was never drained; telemetry, tracing teardown, "
            "and every other callback queued by the v1 build path is silently dropped"
        )


class TestMemoryBaseHookBackgroundMode:
    """The memory-base ``on_flow_output`` hook must fire after a background run.

    Sync mode wires the hook directly inside ``execute_workflow_sync`` and the
    v1 build pipeline wires it after ``end_all_traces`` in ``api/build.py``.
    The v2 background mode buffers frames in ``_buffer_background_run`` and
    must dispatch the same hook in its ``finally`` block on successful
    completion. Without it, MemoryBase auto-capture silently misses every
    background run.
    """

    async def test_background_run_fires_memory_base_hook_on_success(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Background run schedules ``on_flow_output``.

        ``flow_id``, ``session_id``, and ``job_id`` must reach the hook.
        """
        from langflow.api.v2 import workflow as _workflow_module

        captured: list[dict] = []

        class _RecordingMemoryBaseService:
            async def on_flow_output(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            _workflow_module,
            "get_memory_base_service",
            lambda: _RecordingMemoryBaseService(),
        )

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        assert "RUN_FINISHED" in events.text

        # Wait for the buffer task to finalize the job row.
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                if row is not None and row.status.value in ("completed", "failed"):
                    break
            await _asyncio.sleep(0.1)

        # The hook is fired via ``fire_and_forget_task`` so allow the loop a
        # tick to drain the scheduled coroutine.
        for _ in range(20):
            if captured:
                break
            await _asyncio.sleep(0.05)

        assert captured, (
            "Memory-base on_flow_output was not called after a successful "
            "background run. The hook is silently dropped for every "
            "background-mode workflow run."
        )
        assert len(captured) == 1
        call = captured[0]
        assert call["flow_id"] == chatbot_flow
        assert call["session_id"] == "thread-1"  # matches _agui_body session_id
        assert call["job_id"] == _UUID(job_id)


class TestBackgroundFinalizationGuards:
    """Cancellation state + cleanup guarantees for the background path.

    ``_buffer_background_run`` and ``execute_workflow_background`` must
    preserve cancellation state and clean up after scheduling failures.
    """

    async def test_finalize_does_not_overwrite_cancelled_status(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A stopped run settles on CANCELLED and is not overwritten by completion.

        ``stop_workflow`` writes a durable STOP signal (via the facade) and flips
        the row to CANCELLED. The in-flight runner's terminal finalization
        observes that signal and reconciles to CANCELLED rather than writing
        COMPLETED/FAILED over it. CANCELLED is the final, stable state, so we poll
        for it directly (an intermediate COMPLETED/FAILED may flicker before the
        STOP-driven reconcile lands).
        """
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job
        from langflow.services.database.models.jobs.model import JobStatus as _JobStatus

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]
        job_uuid = _UUID(job_id)

        stop = await client.post(
            "api/v2/workflows/stop",
            json={"job_id": job_id},
            headers=headers,
        )
        assert stop.status_code == 200

        # Poll until the row settles on CANCELLED (the final stable state).
        last = None
        for _ in range(80):
            async with session_scope() as session:
                row = await session.get(_Job, job_uuid)
            last = row.status if row is not None else None
            if last == _JobStatus.CANCELLED:
                break
            await _asyncio.sleep(0.1)
        assert last == _JobStatus.CANCELLED, f"stop intent was overwritten: settled on {last}"


class TestBackgroundModeStreamProtocol:
    """Background mode must honor ``stream_protocol`` end-to-end.

    Pre-step-5 the background buffer hardcoded the ``agui`` adapter, so any
    caller-requested protocol was silently ignored. These tests pin both the
    happy paths (``langflow``, ``agui``) and the unknown-protocol contract
    (422 with ``available`` in the body) for ``mode=background`` and
    ``mode=stream``.
    """

    async def test_background_mode_with_langflow_protocol_buffers_langflow_frames(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """mode=background + stream_protocol=langflow buffers raw EventManager payloads.

        The langflow adapter is a passthrough: each frame is
        ``{"event": "<type>", "data": {...}}``. AG-UI specifics
        (RUN_STARTED, RUN_FINISHED, TEXT_MESSAGE_START) must NOT appear.
        """
        headers = {"x-api-key": created_api_key.api_key}
        body: dict = {
            "flow_id": str(chatbot_flow),
            "input_value": "hello",
            "mode": "background",
            "stream_protocol": "langflow",
            "session_id": "thread-1",
        }
        start = await client.post("api/v2/workflows", json=body, headers=headers)
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        text = events.text
        # Langflow passthrough shape: `{"event": "...", "data": {...}}`.
        assert '"event":' in text
        assert '"data":' in text
        # AG-UI lifecycle types must be absent: the wire is langflow, not agui.
        assert "RUN_STARTED" not in text
        assert "RUN_FINISHED" not in text
        assert "TEXT_MESSAGE_START" not in text

    async def test_background_mode_with_unknown_protocol_returns_422(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """mode=background + an unregistered protocol returns 422 with the available list."""
        body: dict = {
            "flow_id": str(empty_flow),
            "input_value": "hi",
            "mode": "background",
            "stream_protocol": "definitely-not-a-real-protocol",
        }
        response = await client.post(
            "api/v2/workflows",
            json=body,
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "UNKNOWN_STREAM_PROTOCOL"
        assert "available" in detail
        # The two built-in adapters must always be listed.
        assert "agui" in detail["available"]
        assert "langflow" in detail["available"]

    async def test_streaming_mode_with_unknown_protocol_returns_422(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """mode=stream + an unregistered protocol returns 422 with the available list.

        Pinned alongside the background test so both branches share the same
        422 contract; refactoring the helper must not break either branch.
        """
        body: dict = {
            "flow_id": str(empty_flow),
            "input_value": "hi",
            "mode": "stream",
            "stream_protocol": "definitely-not-a-real-protocol",
        }
        response = await client.post(
            "api/v2/workflows",
            json=body,
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "UNKNOWN_STREAM_PROTOCOL"
        assert "available" in detail
        assert "agui" in detail["available"]
        assert "langflow" in detail["available"]

    async def test_sync_mode_with_unknown_protocol_returns_422(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """mode=sync + an unregistered protocol must also return 422.

        ``stream_protocol`` is part of the request contract regardless of mode:
        an invalid value in any mode should fail with the same 422 body.
        """
        body: dict = {
            "flow_id": str(empty_flow),
            "input_value": "hi",
            "mode": "sync",
            "stream_protocol": "definitely-not-a-real-protocol",
        }
        response = await client.post(
            "api/v2/workflows",
            json=body,
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "UNKNOWN_STREAM_PROTOCOL"
        assert "available" in detail
        assert "agui" in detail["available"]
        assert "langflow" in detail["available"]

    async def test_background_mode_with_agui_protocol_still_buffers_agui_frames(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """Regression: mode=background + stream_protocol=agui keeps the AG-UI shape.

        The pre-step-5 path was always AG-UI; this test pins that path stays
        valid after the buffer becomes adapter-aware.
        """
        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        text = events.text
        assert "RUN_STARTED" in text
        assert "RUN_FINISHED" in text


class TestStopWorkflowEndToEnd:
    """The ``POST /workflows/stop`` HTTP flow stops a background run.

    The background path now runs through ``BackgroundExecutionService``: stop
    writes a durable STOP signal and cancels the in-flight executor task. This
    test exercises the HTTP contract end-to-end (200 + the run terminalizes).
    The deterministic CANCELLED outcome of a stop is proven without an
    HTTP-level race in
    ``services/background_execution/test_service.py::test_stop_cancels_job`` and
    ``background_execution/test_facade_real_services.py::test_stop_signal_cancels_run``
    (sqlite + postgres), so this test deliberately does not assert the exact
    terminal label under the unsynchronized fast-flow vs stop race.
    """

    async def test_stop_returns_200_and_run_terminalizes(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job, JobStatus

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        stop = await client.post(
            "api/v2/workflows/stop",
            json={"job_id": job_id},
            headers=headers,
        )
        assert stop.status_code == 200

        terminal = {JobStatus.CANCELLED, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.TIMED_OUT}
        final = None
        for _ in range(60):
            async with session_scope() as session:
                row = await session.get(Job, _UUID(job_id))
            if row is not None and row.status in terminal:
                final = row.status
                break
            await _asyncio.sleep(0.1)
        assert final in terminal, f"run did not terminalize after stop: got {final}"
