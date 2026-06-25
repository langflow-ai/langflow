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

import asyncio
import contextlib
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
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


def _sse_payloads(frames: list[bytes]) -> list[dict]:
    return [
        json.loads(line.removeprefix("data:").strip())
        for frame in frames
        for line in frame.decode("utf-8").splitlines()
        if line.startswith("data:")
    ]


def _sse_payload_type(payload: dict) -> str | None:
    return payload.get("type") or payload.get("event")


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

    async def test_sync_mode_rejects_live_canvas_only_fields(
        self,
        client: AsyncClient,
        created_api_key,
        empty_flow,
    ):
        """Sync runs must reject fields that only stream/background executes."""
        body = _agui_body(empty_flow, mode="sync")
        body.update(
            {
                "data": {"nodes": [], "edges": []},
                "files": ["tmp/upload.txt"],
                "start_component_id": "input-1",
                "stop_component_id": "output-1",
            }
        )

        response = await client.post(
            "api/v2/workflows",
            json=body,
            headers={"x-api-key": created_api_key.api_key},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "SYNC_MODE_UNSUPPORTED_FIELDS"
        assert detail["fields"] == ["data", "files", "start_component_id", "stop_component_id"]


class TestV2WorkflowAdmission:
    """Route-level admission checks before workflow execution dispatch."""

    def test_non_owner_data_override_is_hidden_as_404(self):
        """Execute-only sharees must not inject alternate graph data into shared flows."""
        from langflow.api.v2 import workflow as workflow_module
        from lfx.schema.workflow import WorkflowRunRequest
        from lfx.workflow.converters import parse_workflow_run_request

        flow_id = uuid4()
        flow = SimpleNamespace(
            id=flow_id,
            user_id=uuid4(),
            workspace_id=None,
            folder_id=None,
            data={"nodes": [], "edges": []},
            name="shared",
        )
        # A non-owner caller passing a data override hits the gate the production
        # router runs via host.stream_response -> build_stream_response.
        parsed = parse_workflow_run_request(
            WorkflowRunRequest(
                flow_id=str(flow_id),
                input_value="hi",
                mode="stream",
                data={"nodes": [], "edges": []},
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            workflow_module.build_stream_response(
                parsed,
                flow,
                SimpleNamespace(id=uuid4()),
                stream_protocol="langflow",
                background_tasks=SimpleNamespace(),
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "FLOW_NOT_FOUND"

    async def test_execute_permission_denial_is_hidden_as_404(self, monkeypatch: pytest.MonkeyPatch):
        """A denied share-aware fetch must not leak flow existence as a raw 403."""
        from langflow.api.v2 import workflow as workflow_module
        from lfx.workflow.actions import WorkflowAction

        flow_id = uuid4()
        flow = SimpleNamespace(
            id=flow_id,
            user_id=uuid4(),
            workspace_id=None,
            folder_id=None,
            data={"nodes": [], "edges": []},
            name="private",
        )

        async def _deny(*_args, **_kwargs):
            raise HTTPException(status_code=403, detail="denied")

        monkeypatch.setattr(workflow_module, "ensure_flow_permission", _deny)

        # authorize_flow_action is what host.authorize runs on the production path.
        with pytest.raises(HTTPException) as exc_info:
            await workflow_module.authorize_flow_action(SimpleNamespace(id=uuid4()), flow, WorkflowAction.EXECUTE)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "FLOW_NOT_FOUND"

    async def test_denial_echoes_requested_identifier_not_resolved_uuid(self, monkeypatch: pytest.MonkeyPatch):
        """A denial on a flow referenced by endpoint name must not leak the resolved UUID."""
        from langflow.api.v2 import workflow as workflow_module
        from lfx.workflow.actions import WorkflowAction

        resolved_uuid = uuid4()
        flow = SimpleNamespace(id=resolved_uuid, user_id=uuid4(), workspace_id=None, folder_id=None)

        async def _deny(*_args, **_kwargs):
            raise HTTPException(status_code=403, detail="denied")

        monkeypatch.setattr(workflow_module, "ensure_flow_permission", _deny)

        with pytest.raises(HTTPException) as exc_info:
            await workflow_module.authorize_flow_action(
                SimpleNamespace(id=uuid4()), flow, WorkflowAction.EXECUTE, requested_id="my-endpoint"
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "FLOW_NOT_FOUND"
        assert exc_info.value.detail["flow_id"] == "my-endpoint"
        assert str(resolved_uuid) not in str(exc_info.value.detail)

    def test_private_route_applies_component_policy_gate(self, monkeypatch: pytest.MonkeyPatch):
        """The authenticated v2 route must run server-side component policy validation."""
        from langflow.api.v2 import workflow as workflow_module
        from langflow.api.v2 import workflow_validation as wf_val
        from lfx.schema.workflow import WorkflowRunRequest
        from lfx.utils.flow_validation import CustomComponentValidationError
        from lfx.workflow.converters import parse_workflow_run_request

        flow_id = uuid4()
        flow = SimpleNamespace(
            id=flow_id,
            user_id=uuid4(),
            workspace_id=None,
            folder_id=None,
            data={"nodes": [], "edges": []},
            name="private",
        )

        def _reject(_flow_data):
            message = "custom components are disabled"
            raise CustomComponentValidationError(message)

        monkeypatch.setattr(wf_val, "validate_flow_for_current_settings", _reject)
        parsed = parse_workflow_run_request(WorkflowRunRequest(flow_id=str(flow_id), input_value="hi", mode="stream"))

        with pytest.raises(HTTPException) as exc_info:
            workflow_module.build_stream_response(
                parsed,
                flow,
                SimpleNamespace(id=flow.user_id),
                stream_protocol="langflow",
                background_tasks=SimpleNamespace(),
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "custom components are disabled"


class TestAGUIStreaming:
    """mode=stream returns an AG-UI server-sent event stream."""

    async def test_stream_event_queue_ignores_late_sentinel_after_overflow(self):
        """A normal completion sentinel must not race ahead of the overflow error."""
        from langflow.api.v2 import workflow_execution as wf_exec

        queue = wf_exec._WorkflowEventQueue(maxsize=1)
        try:
            payload = json.dumps({"event": "token", "data": {"chunk": "0"}}).encode()
            queue.put_nowait(("token-0", payload, time.time()))
            queue.put_nowait(("token-1", payload, time.time()))

            await asyncio.wait_for(queue.put((None, None, time.time())), timeout=0.1)
        finally:
            await queue.aclose()

    async def test_stream_event_handoff_overflow_emits_error(self, monkeypatch: pytest.MonkeyPatch):
        """EventManager put_nowait must not silently drop frames when the stream buffer fills."""
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.adapters import StreamEvent
        from lfx.workflow.converters import ParsedWorkflowRun

        seen_maxsize: list[int] = []

        async def fake_generate_flow_events(**kwargs):
            event_queue = kwargs["event_manager"].queue
            seen_maxsize.append(event_queue.maxsize)
            for index in range(event_queue.maxsize + 1):
                payload = json.dumps({"event": "token", "data": {"chunk": str(index)}}).encode()
                event_queue.put_nowait((f"token-{index}", payload, time.time()))
            await event_queue.put((None, None, time.time()))

        class FakeAdapter:
            name = "langflow"

            def initial_events(self):
                return []

            def final_events(self):
                return []

            def translate(self, event_type, _event_data):
                return [StreamEvent(type=event_type, data_json="{}")]

        monkeypatch.setattr(wf_exec, "_EVENT_QUEUE_MAX_SIZE", 2)
        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)

        event_types = [
            event_type
            async for _frame, event_type in wf_exec._stream_event_frames(
                adapter=FakeAdapter(),
                flow_id=uuid4(),
                flow_name="flow",
                background_tasks=SimpleNamespace(add_task=lambda *_args, **_kwargs: None),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
                current_user=SimpleNamespace(id=uuid4()),
            )
        ]

        assert seen_maxsize == [2]
        assert event_types == ["token", "token", "error"]

    @pytest.mark.parametrize(("stream_protocol", "terminal_type"), [("agui", "RUN_ERROR"), ("langflow", "error")])
    async def test_stream_enforces_execution_timeout(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stream_protocol: str,
        terminal_type: str,
    ):
        """A run that exceeds the wall-clock ceiling ends in a sanitized terminal error, not a hang."""
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
        from lfx.workflow.converters import ParsedWorkflowRun

        async def hanging_generate_flow_events(**_kwargs):
            await asyncio.sleep(5)

        # Tiny ceiling + a producer that never returns: the timeout must fire.
        monkeypatch.setattr(wf_exec, "_resolve_execution_timeout", lambda: 0.05)
        monkeypatch.setattr(wf_exec, "generate_flow_events", hanging_generate_flow_events)

        adapter = get_stream_adapter(stream_protocol, StreamAdapterContext(run_id="run", thread_id="thread"))

        collected: list[tuple[bytes, str]] = [
            (frame, event_type)
            async for frame, event_type in wf_exec._stream_event_frames(
                adapter=adapter,
                flow_id=uuid4(),
                flow_name="flow",
                background_tasks=SimpleNamespace(add_task=lambda *_args, **_kwargs: None),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode="stream"),
                current_user=SimpleNamespace(id=uuid4()),
            )
        ]

        event_types = [event_type for _frame, event_type in collected]
        body = b"".join(frame for frame, _event_type in collected).decode()
        # Exactly one terminal error, carrying the sanitized message (no internal detail).
        assert event_types.count(terminal_type) == 1
        assert "Workflow execution timed out." in body

    @pytest.mark.parametrize(("stream_protocol", "terminal_type"), [("agui", "RUN_ERROR"), ("langflow", "error")])
    async def test_stream_error_path_emits_one_terminal_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stream_protocol: str,
        terminal_type: str,
    ):
        """A producer that reports on_error then raises must not triple-emit terminal errors."""
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
        from lfx.workflow.converters import ParsedWorkflowRun

        async def fake_generate_flow_events(**kwargs):
            kwargs["event_manager"].on_error(data={"error": "inner"})
            message = "outer"
            raise RuntimeError(message)

        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)

        adapter = get_stream_adapter(
            stream_protocol,
            StreamAdapterContext(run_id="run-1", thread_id="thread-1"),
        )
        event_types = [
            event_type
            async for _frame, event_type in wf_exec._stream_event_frames(
                adapter=adapter,
                flow_id=uuid4(),
                flow_name="flow",
                background_tasks=SimpleNamespace(add_task=lambda *_args, **_kwargs: None),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
                current_user=SimpleNamespace(id=uuid4()),
            )
        ]

        assert event_types.count(terminal_type) == 1
        assert event_types[-1] == terminal_type

    @pytest.mark.parametrize(("stream_protocol", "terminal_type"), [("agui", "RUN_ERROR"), ("langflow", "error")])
    async def test_stream_error_path_uses_fallback_when_producer_raises_before_on_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        stream_protocol: str,
        terminal_type: str,
    ):
        """A producer that raises before on_error still emits one terminal error."""
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter
        from lfx.workflow.converters import ParsedWorkflowRun

        async def fake_generate_flow_events(**_kwargs):
            message = "early boom"
            raise RuntimeError(message)

        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)

        adapter = get_stream_adapter(
            stream_protocol,
            StreamAdapterContext(run_id="run-1", thread_id="thread-1"),
        )
        frames = [
            frame
            async for frame, _event_type in wf_exec._stream_event_frames(
                adapter=adapter,
                flow_id=uuid4(),
                flow_name="flow",
                background_tasks=SimpleNamespace(add_task=lambda *_args, **_kwargs: None),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
                current_user=SimpleNamespace(id=uuid4()),
            )
        ]

        payloads = _sse_payloads(frames)
        payload_types = [_sse_payload_type(payload) for payload in payloads]
        assert payload_types.count(terminal_type) == 1
        assert payload_types[-1] == terminal_type
        assert "early boom" in json.dumps(payloads[-1])

    async def test_agui_stream_emits_end_side_channel_for_build_duration(self, monkeypatch: pytest.MonkeyPatch):
        """The AG-UI stream must preserve v1 end payloads for chat build-duration persistence."""
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.converters import ParsedWorkflowRun

        async def fake_generate_flow_events(**kwargs):
            event_queue = kwargs["event_manager"].queue
            payload = json.dumps({"event": "end", "data": {"build_duration": 1.25}}).encode()
            event_queue.put_nowait(("end-1", payload, time.time()))
            await event_queue.put((None, None, time.time()))

        class FakeAdapter:
            name = "agui"

            def initial_events(self):
                return []

            def final_events(self):
                return []

            def translate(self, _event_type, _event_data):
                return []

        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)

        frames = [
            frame
            async for frame, _event_type in wf_exec._stream_event_frames(
                adapter=FakeAdapter(),
                flow_id=uuid4(),
                flow_name="flow",
                background_tasks=SimpleNamespace(add_task=lambda *_args, **_kwargs: None),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="", mode="stream"),
                current_user=SimpleNamespace(id=uuid4()),
            )
        ]

        custom_events = [
            json.loads(line.removeprefix("data:").strip())
            for frame in frames
            for line in frame.decode("utf-8").splitlines()
            if line.startswith("data:")
        ]
        assert custom_events == [
            {
                "type": "CUSTOM",
                "name": "langflow.event",
                "value": {"event_type": "end", "data": {"build_duration": 1.25}},
            }
        ]

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

    async def test_reattach_owned_job_without_local_buffer_returns_409(self, monkeypatch: pytest.MonkeyPatch):
        """If the job exists but this worker has no replay buffer, return an explicit conflict."""
        from langflow.api.v2 import workflow as workflow_module

        job_id = uuid4()
        expected_user_id = uuid4()
        workflow_module._BACKGROUND_RUNS.pop(str(job_id), None)

        class FakeJobService:
            async def get_job_by_job_id(self, seen_job_id, user_id=None):
                assert seen_job_id == job_id
                assert user_id == expected_user_id
                return SimpleNamespace(type=workflow_module.JobType.WORKFLOW)

        monkeypatch.setattr(workflow_module, "get_job_service", lambda: FakeJobService())

        with pytest.raises(HTTPException) as exc_info:
            await workflow_module.reattach_workflow_events(
                str(job_id),
                http_request=SimpleNamespace(headers={}),
                current_user=SimpleNamespace(id=expected_user_id),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "BACKGROUND_EVENTS_UNAVAILABLE"

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

    async def test_background_buffer_binds_build_rows_to_returned_job_id(self, monkeypatch: pytest.MonkeyPatch):
        """Status reconstruction needs vertex_build rows logged under the public background job id."""
        from langflow.api.v2 import workflow_background as wf_bg
        from lfx.workflow.converters import ParsedWorkflowRun

        job_id = uuid4()
        captured: dict = {}

        class FakeAdapter:
            terminal_error_type = "RUN_ERROR"

            def cancel_events(self, _reason):
                return []

        async def fake_stream_event_frames(**kwargs):
            captured.update(kwargs)
            yield b"data: {}\n\n", "RUN_FINISHED"

        monkeypatch.setattr(wf_bg, "get_stream_adapter", lambda *_args, **_kwargs: FakeAdapter())
        monkeypatch.setattr(wf_bg, "_stream_event_frames", fake_stream_event_frames)
        monkeypatch.setattr(wf_bg, "_finalize_job_status", AsyncMock())

        bg_run = wf_bg._BackgroundRun(user_id=str(uuid4()))
        await wf_bg._buffer_background_run(
            bg_run=bg_run,
            flow=SimpleNamespace(id=uuid4(), name="flow"),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode="background"),
            job_id=str(job_id),
            current_user=SimpleNamespace(id=uuid4()),
            stream_protocol="agui",
        )

        assert captured["run_id"] == str(job_id)
        assert captured["track_job_status"] is False

    async def test_background_buffer_marks_job_in_progress(self, monkeypatch: pytest.MonkeyPatch):
        """A background job should leave QUEUED once its buffer task starts executing."""
        from langflow.api.v2 import workflow as workflow_module
        from langflow.api.v2 import workflow_background as wf_bg
        from lfx.workflow.converters import ParsedWorkflowRun

        job_id = uuid4()
        updates: list[tuple[object, object, bool]] = []

        class FakeAdapter:
            name = "agui"
            terminal_error_type = "RUN_ERROR"

            def cancel_events(self, _reason):
                return []

        class FakeJobService:
            async def update_job_status(self, seen_job_id, status, *, finished_timestamp=False):
                updates.append((seen_job_id, status, finished_timestamp))

        async def fake_stream_event_frames(**_kwargs):
            yield b"data: {}\n\n", "RUN_FINISHED"

        monkeypatch.setattr(wf_bg, "get_stream_adapter", lambda *_args, **_kwargs: FakeAdapter())
        monkeypatch.setattr(wf_bg, "get_job_service", lambda: FakeJobService())
        monkeypatch.setattr(wf_bg, "_stream_event_frames", fake_stream_event_frames)
        monkeypatch.setattr(wf_bg, "_finalize_job_status", AsyncMock())

        bg_run = wf_bg._BackgroundRun(user_id=str(uuid4()))
        await wf_bg._buffer_background_run(
            bg_run=bg_run,
            flow=SimpleNamespace(id=uuid4(), name="flow"),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode="background"),
            job_id=str(job_id),
            current_user=SimpleNamespace(id=uuid4()),
            stream_protocol="agui",
        )

        assert (job_id, workflow_module.JobStatus.IN_PROGRESS, False) in updates

    async def test_cancelled_agui_buffer_wakes_tail_reader_with_closed_text_and_run_finished(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """The owner task must append cancellation before marking replay done."""
        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.converters import ParsedWorkflowRun

        started = asyncio.Event()

        class FakeJobService:
            async def update_job_status(self, *_args, **_kwargs):
                return None

        async def fake_generate_flow_events(**kwargs):
            kwargs["event_manager"].on_token(data={"id": "m1", "chunk": "partial"})
            started.set()
            await asyncio.Event().wait()

        async def collect_tail(bg_run):
            tail = bg_run.base_index + len(bg_run.frames)
            return [frame async for frame in bg_run.replay(tail)]

        monkeypatch.setattr(wf_bg, "get_job_service", lambda: FakeJobService())
        monkeypatch.setattr(wf_bg, "_finalize_job_status", AsyncMock())
        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)

        bg_run = wf_bg._BackgroundRun(user_id=str(uuid4()), stream_protocol="agui")
        buffer_task = asyncio.create_task(
            wf_bg._buffer_background_run(
                bg_run=bg_run,
                flow=SimpleNamespace(id=uuid4(), name="flow"),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode="background"),
                job_id=str(uuid4()),
                current_user=SimpleNamespace(id=uuid4()),
                stream_protocol="agui",
            )
        )
        await asyncio.wait_for(started.wait(), timeout=2)
        for _ in range(100):
            payload_types = [_sse_payload_type(payload) for payload in _sse_payloads(bg_run.frames)]
            if "TEXT_MESSAGE_CONTENT" in payload_types:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("token content was never buffered")

        tail_task = asyncio.create_task(collect_tail(bg_run))
        await asyncio.sleep(0)

        buffer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await buffer_task
        tail_frames = await asyncio.wait_for(tail_task, timeout=2)

        tail_payloads = _sse_payloads(tail_frames)
        assert [_sse_payload_type(payload) for payload in tail_payloads] == [
            "TEXT_MESSAGE_END",
            "CUSTOM",
            "RUN_FINISHED",
        ]
        assert tail_payloads[0]["messageId"] == "m1"
        assert tail_payloads[1]["name"] == "langflow.run.cancelled"
        assert tail_payloads[1]["value"]["reason"] == "Workflow run cancelled."

    async def test_cancelled_langflow_buffer_wakes_tail_reader_with_langflow_cancelled(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Cancellation framing must stay protocol-native outside AG-UI too."""
        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.converters import ParsedWorkflowRun

        started = asyncio.Event()

        class FakeJobService:
            async def update_job_status(self, *_args, **_kwargs):
                return None

        async def fake_generate_flow_events(**kwargs):
            kwargs["event_manager"].on_token(data={"id": "m1", "chunk": "partial"})
            started.set()
            await asyncio.Event().wait()

        async def collect_tail(bg_run):
            tail = bg_run.base_index + len(bg_run.frames)
            return [frame async for frame in bg_run.replay(tail)]

        monkeypatch.setattr(wf_bg, "get_job_service", lambda: FakeJobService())
        monkeypatch.setattr(wf_bg, "_finalize_job_status", AsyncMock())
        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)

        bg_run = wf_bg._BackgroundRun(user_id=str(uuid4()), stream_protocol="langflow")
        buffer_task = asyncio.create_task(
            wf_bg._buffer_background_run(
                bg_run=bg_run,
                flow=SimpleNamespace(id=uuid4(), name="flow"),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode="background"),
                job_id=str(uuid4()),
                current_user=SimpleNamespace(id=uuid4()),
                stream_protocol="langflow",
            )
        )
        await asyncio.wait_for(started.wait(), timeout=2)
        for _ in range(100):
            payload_types = [_sse_payload_type(payload) for payload in _sse_payloads(bg_run.frames)]
            if "token" in payload_types:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("token event was never buffered")

        tail_task = asyncio.create_task(collect_tail(bg_run))
        await asyncio.sleep(0)

        buffer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await buffer_task
        tail_frames = await asyncio.wait_for(tail_task, timeout=2)

        [payload] = _sse_payloads(tail_frames)
        assert payload == {"event": "cancelled", "data": {"reason": "Workflow run cancelled."}}

    async def test_finish_cancelled_background_run_appends_terminal_before_waking_replay(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """The stop fallback must not wake replay readers before cancellation is buffered."""
        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.api.v2 import workflow_execution as wf_exec
        from lfx.workflow.converters import ParsedWorkflowRun

        job_id = str(uuid4())
        started = asyncio.Event()

        class FakeJobService:
            async def update_job_status(self, *_args, **_kwargs):
                return None

        async def fake_generate_flow_events(**kwargs):
            kwargs["event_manager"].on_token(data={"id": "m1", "chunk": "partial"})
            started.set()
            await asyncio.Event().wait()

        async def collect_tail(bg_run):
            tail = bg_run.base_index + len(bg_run.frames)
            return [frame async for frame in bg_run.replay(tail)]

        monkeypatch.setattr(wf_bg, "get_job_service", lambda: FakeJobService())
        monkeypatch.setattr(wf_bg, "_finalize_job_status", AsyncMock())
        monkeypatch.setattr(wf_exec, "generate_flow_events", fake_generate_flow_events)
        monkeypatch.setattr(wf_bg, "_BACKGROUND_RUNS", {})

        bg_run = wf_bg._BackgroundRun(user_id=str(uuid4()), stream_protocol="agui")
        wf_bg._BACKGROUND_RUNS[job_id] = bg_run
        buffer_task = asyncio.create_task(
            wf_bg._buffer_background_run(
                bg_run=bg_run,
                flow=SimpleNamespace(id=uuid4(), name="flow"),
                parsed=ParsedWorkflowRun(flow_id=str(uuid4()), input_value="hi", mode="background"),
                job_id=job_id,
                current_user=SimpleNamespace(id=uuid4()),
                stream_protocol="agui",
            )
        )
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            for _ in range(100):
                payload_types = [_sse_payload_type(payload) for payload in _sse_payloads(bg_run.frames)]
                if "TEXT_MESSAGE_CONTENT" in payload_types:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("token content was never buffered")

            tail_task = asyncio.create_task(collect_tail(bg_run))
            await asyncio.sleep(0)

            await wf_bg._finish_cancelled_background_run(job_id)
            tail_frames = await asyncio.wait_for(tail_task, timeout=2)

            tail_payloads = _sse_payloads(tail_frames)
            assert [_sse_payload_type(payload) for payload in tail_payloads] == [
                "TEXT_MESSAGE_END",
                "CUSTOM",
                "RUN_FINISHED",
            ]
            assert tail_payloads[0]["messageId"] == "m1"
            assert tail_payloads[1]["name"] == "langflow.run.cancelled"
            assert tail_payloads[1]["value"]["reason"] == "Workflow run cancelled."

            frames_after_fallback = list(bg_run.frames)
            buffer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await buffer_task
            assert bg_run.frames == frames_after_fallback
        finally:
            if not buffer_task.done():
                buffer_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await buffer_task
            await wf_bg._clear_background_run(job_id)

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

    async def test_completed_background_job_status_reconstructs_from_job_id(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A completed background job's GET status must reconstruct its outputs.

        Regression: the background build path minted its own ``run_id`` instead of
        using ``job_id``, so vertex builds were persisted under a different id than
        ``get_vertex_builds_by_job_id`` queries. Completed background jobs then 500
        with "No vertex builds found" on status reconstruction. The sync path
        already aligns ``run_id`` to ``job_id`` (``graph.set_run_id(job_id)``); the
        background path must too.
        """
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        # Drain the SSE buffer so the build runs and persists vertex builds.
        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        assert "RUN_FINISHED" in events.text

        # Wait for the buffer task to finalize the job row to completed.
        row = None
        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                if row is not None and row.status.value in ("completed", "failed"):
                    break
            await _asyncio.sleep(0.1)
        assert row is not None, "background job row was never created"
        assert row.status.value == "completed", f"background job did not complete: {row.status.value!r}"

        # GET status reconstructs from the vertex_build table keyed by job_id.
        status_resp = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)
        assert status_resp.status_code == 200, (
            "completed background job status failed to reconstruct "
            f"(run_id/job_id mismatch?): {status_resp.status_code} {status_resp.text}"
        )
        body = status_resp.json()
        assert body["status"] == "completed"
        assert "outputs" in body

    async def test_completed_background_job_status_recovers_session_id(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        """A completed background job's GET status must echo the session it ran under.

        Regression: ``reconstruct_workflow_response_from_job_id`` hardcoded
        ``session_id=None``, so every completed background job reported a null
        session even though the run executed under a real one, breaking the
        documented handle for continuing the same chat/memory thread. The session
        is recovered from the persisted terminal ``ChatOutputResponse.session_id``.
        """
        import asyncio as _asyncio
        from uuid import UUID as _UUID

        from langflow.services.database.models.jobs.model import Job as _Job

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, message="hi", mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        # Drain the SSE buffer so the build runs and persists vertex builds.
        events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
        assert events.status_code == 200
        assert "RUN_FINISHED" in events.text

        row = None
        for _ in range(100):
            async with session_scope() as session:
                row = await session.get(_Job, _UUID(job_id))
                if row is not None and row.status.value in ("completed", "failed"):
                    break
            await _asyncio.sleep(0.1)
        assert row is not None, "background job row was never created"
        assert row.status.value == "completed", f"background job did not complete: {row.status.value!r}"

        status_resp = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)
        assert status_resp.status_code == 200, status_resp.text
        body = status_resp.json()
        # _agui_body runs under session "thread-1"; before the fix this was null.
        assert body["session_id"] == "thread-1"

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
        from langflow.api.v2 import workflow_background as wf_bg
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

        monkeypatch.setattr(wf_bg, "BackgroundTasks", RecordingBackgroundTasks)

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
    v1 build pipeline wires it after ``end_all_traces`` in ``api/build.py``. The
    v2 background mode routes through that same build pipeline with the returned
    background job id, so the hook must fire exactly once for successful
    background runs.
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
        from langflow.api import build as _build_module

        captured: list[dict] = []

        class _RecordingMemoryBaseService:
            async def on_flow_output(self, **kwargs):
                captured.append(kwargs)

        monkeypatch.setattr(
            _build_module,
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
        """A run cancelled mid-flight must stay CANCELLED after the buffer ends.

        Race: ``stop_workflow`` sets the job to CANCELLED. The buffer task's
        ``finally`` block runs shortly after and previously wrote
        COMPLETED/FAILED unconditionally, silently overwriting the user's
        stop intent. Guarded by ``_finalize_job_status``.
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

        # Stop the run before it gets a chance to complete on its own. The
        # /stop endpoint flips the row to CANCELLED.
        stop = await client.post(
            "api/v2/workflows/stop",
            json={"job_id": job_id},
            headers=headers,
        )
        assert stop.status_code == 200

        # Give the buffer task time to reach its finally block and call
        # _finalize_job_status. Poll the row for stability.
        for _ in range(60):
            async with session_scope() as session:
                row = await session.get(_Job, job_uuid)
                if row is not None and row.status in (_JobStatus.COMPLETED, _JobStatus.FAILED):
                    break
            await _asyncio.sleep(0.1)

        async with session_scope() as session:
            row = await session.get(_Job, job_uuid)
            assert row is not None
            assert row.status == _JobStatus.CANCELLED, (
                f"Buffer task overwrote the user's cancellation: got {row.status} "
                f"(expected CANCELLED). The finally block in _buffer_background_run "
                f"is racing with stop_workflow."
            )


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


class TestBackgroundRunsRegistryEviction:
    """``_register_background_run`` must not evict still-running buffers.

    The registry is bounded by ``_MAX_BACKGROUND_RUNS``. The naive policy of
    popping the oldest entry by insertion order drops the re-attach handle for
    a long-running first job the moment the limit is hit, so the buffer task
    keeps appending into an orphaned ``_BackgroundRun`` while re-attach
    returns 404. Eviction must prefer completed entries first; falling back
    to evicting the oldest only when every slot is occupied by a running run.
    """

    async def test_eviction_prefers_completed_runs_over_running_ones(self, monkeypatch):
        from langflow.api.v2 import workflow_background as wf_bg

        monkeypatch.setattr(wf_bg, "_MAX_BACKGROUND_RUNS", 3)
        monkeypatch.setattr(wf_bg, "_BACKGROUND_RUNS", {})

        # Evicting a completed run has no live writer to stop, so the cancel path
        # must not fire; record any call to prove it doesn't.
        cancelled: list[str] = []

        async def fake_cancel(job_id):
            cancelled.append(job_id)
            return True

        monkeypatch.setattr(wf_bg, "_cancel_workflow_queue_job", fake_cancel)

        long_running = wf_bg._BackgroundRun(user_id="u")
        # done stays False; this is the run we must protect.
        await wf_bg._register_background_run("long", long_running)

        # Fill the rest with completed runs.
        for job_id in ("done1", "done2"):
            done_run = wf_bg._BackgroundRun(user_id="u")
            done_run.done = True
            await wf_bg._register_background_run(job_id, done_run)

        # Registry is now at the cap (3): [long, done1, done2]. Adding a new
        # entry must evict a completed run, not the still-running ``long``.
        new_run = wf_bg._BackgroundRun(user_id="u")
        await wf_bg._register_background_run("new", new_run)

        assert "long" in wf_bg._BACKGROUND_RUNS, "Still-running background run was evicted in favor of a completed one"
        assert "new" in wf_bg._BACKGROUND_RUNS
        assert cancelled == [], "Evicting a completed run must not cancel a queue job"

    async def test_eviction_falls_back_to_oldest_when_every_run_is_active(self, monkeypatch):
        """If every slot is occupied by a still-running run, evict the oldest anyway.

        Unbounded growth would leak memory. The fallback is intentional and
        documented; a warning log makes the situation visible. The evicted run's
        buffer writer is cancelled so it stops appending into a run no reader can
        find (the bounded-memory guarantee the registry exists to provide).
        """
        from langflow.api.v2 import workflow_background as wf_bg

        monkeypatch.setattr(wf_bg, "_MAX_BACKGROUND_RUNS", 2)
        monkeypatch.setattr(wf_bg, "_BACKGROUND_RUNS", {})

        cancelled: list[str] = []

        async def fake_cancel(job_id):
            cancelled.append(job_id)
            return True

        monkeypatch.setattr(wf_bg, "_cancel_workflow_queue_job", fake_cancel)

        for job_id in ("a", "b"):
            run = wf_bg._BackgroundRun(user_id="u")
            await wf_bg._register_background_run(job_id, run)

        # All running; adding a third must evict the oldest (a) and cancel it.
        third = wf_bg._BackgroundRun(user_id="u")
        await wf_bg._register_background_run("c", third)

        assert "a" not in wf_bg._BACKGROUND_RUNS
        assert "b" in wf_bg._BACKGROUND_RUNS
        assert "c" in wf_bg._BACKGROUND_RUNS
        assert cancelled == ["a"], "Evicted still-running run's buffer writer was not cancelled"


class TestClearBackgroundRun:
    """``_clear_background_run`` releases a stopped run's buffer and wakes waiters.

    Without this, ``stop_workflow`` revokes the buffer task but leaves the
    ``_BackgroundRun`` registered. Re-attach readers can hang on
    ``_cond.wait()`` indefinitely, and up to ``_MAX_BACKGROUND_RUNS`` cancelled
    buffers occupy memory.
    """

    async def test_clear_pops_registry_entry_and_finishes_buffer(self, monkeypatch):
        from langflow.api.v2 import workflow_background as wf_bg

        monkeypatch.setattr(wf_bg, "_BACKGROUND_RUNS", {})

        bg_run = wf_bg._BackgroundRun(user_id="u")
        await wf_bg._register_background_run("job-1", bg_run)
        assert bg_run.done is False

        await wf_bg._clear_background_run("job-1")

        assert "job-1" not in wf_bg._BACKGROUND_RUNS
        assert bg_run.done is True

    async def test_clear_is_a_noop_for_unknown_job_id(self, monkeypatch):
        from langflow.api.v2 import workflow_background as wf_bg

        monkeypatch.setattr(wf_bg, "_BACKGROUND_RUNS", {})

        # Must not raise even when nothing is registered.
        await wf_bg._clear_background_run("nope")


class TestBackgroundRunReplayConcurrentReaders:
    """``_BackgroundRun.replay`` must serve multiple concurrent re-attach readers.

    The buffer's contract is that any number of clients can attach mid-run and
    each one sees every frame from their ``start_index`` through ``finish``.
    The asyncio.Condition wakeup is broadcast (``notify_all``) so every waiter
    advances on each ``append``. This pins that contract at the unit level;
    Playwright exercises it indirectly.
    """

    async def test_two_concurrent_readers_each_receive_all_frames(self):
        import asyncio as _asyncio

        from langflow.api.v2 import workflow_background as wf_bg

        bg_run = wf_bg._BackgroundRun(user_id="u")

        async def consume() -> list[bytes]:
            return [frame async for frame in bg_run.replay(start_index=0)]

        reader_a = _asyncio.create_task(consume())
        reader_b = _asyncio.create_task(consume())

        # Give both readers two ticks to enter ``_cond.wait()``. One tick is
        # enough on CPython (asyncio schedules pending tasks FIFO on yield),
        # but a second pass is cheap defensive insurance against future
        # scheduler tweaks.
        await _asyncio.sleep(0)
        await _asyncio.sleep(0)

        await bg_run.append(b"frame1")
        await bg_run.append(b"frame2")
        await bg_run.finish()

        a_frames, b_frames = await _asyncio.wait_for(
            _asyncio.gather(reader_a, reader_b),
            timeout=5.0,
        )
        assert a_frames == [b"frame1", b"frame2"]
        assert b_frames == [b"frame1", b"frame2"]

    async def test_late_reader_replays_buffered_frames_then_tails(self):
        """A reader attaching after some frames have been buffered still sees them all.

        The first batch is drained from the snapshot; the reader then re-enters
        ``_cond.wait()`` and picks up subsequent ``append`` calls before
        ``finish`` releases it.
        """
        import asyncio as _asyncio

        from langflow.api.v2 import workflow_background as wf_bg

        bg_run = wf_bg._BackgroundRun(user_id="u")

        # Buffer two frames before any reader attaches.
        await bg_run.append(b"early-1")
        await bg_run.append(b"early-2")

        async def consume() -> list[bytes]:
            return [frame async for frame in bg_run.replay(start_index=0)]

        reader = _asyncio.create_task(consume())
        await _asyncio.sleep(0)  # let the reader yield the early batch and re-enter wait

        await bg_run.append(b"late-1")
        await bg_run.finish()

        frames = await _asyncio.wait_for(reader, timeout=5.0)
        assert frames == [b"early-1", b"early-2", b"late-1"]

    async def test_replay_with_start_index_skips_earlier_frames(self):
        """``start_index`` honors the Last-Event-ID hand-off semantics."""
        import asyncio as _asyncio

        from langflow.api.v2 import workflow_background as wf_bg

        bg_run = wf_bg._BackgroundRun(user_id="u")
        await bg_run.append(b"f0")
        await bg_run.append(b"f1")
        await bg_run.append(b"f2")
        await bg_run.finish()

        collected = [frame async for frame in bg_run.replay(start_index=1)]
        assert collected == [b"f1", b"f2"]

        # A start_index past the end yields nothing and returns cleanly.
        nothing = [frame async for frame in bg_run.replay(start_index=99)]
        assert nothing == []

        # Calling replay after finish from start_index=0 still replays the buffer.
        async def _drain() -> list[bytes]:
            return [frame async for frame in bg_run.replay(start_index=0)]

        replayed = await _asyncio.wait_for(_drain(), timeout=5.0)
        assert replayed == [b"f0", b"f1", b"f2"]


class TestBufferBackgroundRunUnknownProtocolGuard:
    """``_buffer_background_run`` flips the job to FAILED if the adapter registry was mutated.

    The route validates ``stream_protocol`` up front, but the buffer task
    re-resolves the adapter inside the fire-and-forget coroutine. If a
    registration was dropped between the route's check and the coroutine's
    start, ``get_stream_adapter`` raises ``UnknownStreamProtocolError`` and the
    coroutine must:
      - mark the buffer done (waking any re-attach reader)
      - update the job row to ``FAILED`` with a finished timestamp
      - return cleanly without raising (it is fire-and-forget)
    """

    async def test_missing_protocol_marks_bg_run_done_and_fails_job(
        self,
        created_api_key,
        empty_flow,
    ):
        """The defensive UnknownStreamProtocolError path finalizes job + buffer cleanly."""
        from uuid import uuid4 as _uuid4

        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.services.database.models.flow.model import Flow, FlowRead
        from langflow.services.database.models.jobs.model import Job, JobStatus
        from langflow.services.database.models.user.model import User as _User
        from langflow.services.database.models.user.model import UserRead
        from langflow.services.deps import get_job_service
        from lfx.workflow.adapters import STREAM_ADAPTERS as _REGISTRY
        from lfx.workflow.converters import ParsedWorkflowRun

        # Real Job row so update_job_status can flip it.
        job_id = _uuid4()
        await get_job_service().create_job(
            job_id=job_id,
            flow_id=empty_flow,
            user_id=created_api_key.user_id,
        )

        async with session_scope() as session:
            flow_row = await session.get(Flow, empty_flow)
            flow = FlowRead.model_validate(flow_row, from_attributes=True)
            user_row = await session.get(_User, created_api_key.user_id)
            user = UserRead.model_validate(user_row, from_attributes=True)

        bg_run = wf_bg._BackgroundRun(user_id=str(created_api_key.user_id))

        # ``get_stream_adapter`` reads the registry dict from
        # ``adapters.registry`` directly. Rebinding the imported reference on
        # ``workflow_background`` has no effect on the lookup; we have to mutate the
        # shared dict in place and restore it afterwards.
        snapshot = dict(_REGISTRY)
        _REGISTRY.clear()
        try:
            await wf_bg._buffer_background_run(
                bg_run=bg_run,
                flow=flow,
                parsed=ParsedWorkflowRun(flow_id=str(empty_flow), mode="background"),
                job_id=str(job_id),
                current_user=user,
                stream_protocol="agui",  # registered at import-time; cleared above
            )
        finally:
            _REGISTRY.update(snapshot)

        assert bg_run.done is True

        async with session_scope() as session:
            row = await session.get(Job, job_id)
        assert row is not None
        assert row.status == JobStatus.FAILED
        assert row.finished_timestamp is not None

    async def test_missing_protocol_does_not_raise(self, created_api_key, empty_flow):
        """The coroutine is fire-and-forget; it must swallow the registry mismatch cleanly."""
        from uuid import uuid4 as _uuid4

        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.services.database.models.flow.model import Flow, FlowRead
        from langflow.services.database.models.user.model import User as _User
        from langflow.services.database.models.user.model import UserRead
        from langflow.services.deps import get_job_service
        from lfx.workflow.adapters import STREAM_ADAPTERS as _REGISTRY
        from lfx.workflow.converters import ParsedWorkflowRun

        job_id = _uuid4()
        await get_job_service().create_job(
            job_id=job_id,
            flow_id=empty_flow,
            user_id=created_api_key.user_id,
        )

        async with session_scope() as session:
            flow_row = await session.get(Flow, empty_flow)
            flow = FlowRead.model_validate(flow_row, from_attributes=True)
            user_row = await session.get(_User, created_api_key.user_id)
            user = UserRead.model_validate(user_row, from_attributes=True)

        bg_run = wf_bg._BackgroundRun(user_id=str(created_api_key.user_id))

        snapshot = dict(_REGISTRY)
        _REGISTRY.clear()
        try:
            # Must not raise, even though the protocol is unknown.
            await wf_bg._buffer_background_run(
                bg_run=bg_run,
                flow=flow,
                parsed=ParsedWorkflowRun(flow_id=str(empty_flow), mode="background"),
                job_id=str(job_id),
                current_user=user,
                stream_protocol="langflow",
            )
        finally:
            _REGISTRY.update(snapshot)


class TestExecuteWorkflowBackgroundQueueOwnership:
    async def test_background_jobs_do_not_register_polling_owner(self, monkeypatch: pytest.MonkeyPatch):
        """Background jobs must not opt into Redis' polling-owner watchdog.

        ``register_job_owner`` is the Redis queue service's signal that a job
        has an active polling/streaming client expected to refresh
        ``touch_activity``. v2 background jobs run unattended and are stopped
        via the queue cancel side-channel plus the persisted workflow Job row,
        so registering them would let the polling watchdog reclaim long runs.
        """
        from langflow.api.v2 import workflow_background as wf_bg
        from lfx.workflow.converters import ParsedWorkflowRun

        job_id = uuid4()
        current_user_id = uuid4()
        flow_id = uuid4()
        created_jobs: list[object] = []
        registered_owners: list[tuple[str, object]] = []
        started_jobs: list[str] = []

        class FakeJobService:
            async def create_job(self, **kwargs):
                created_jobs.append(kwargs["job_id"])

        class FakeQueueService:
            def create_queue(self, _seen_job_id):
                return SimpleNamespace(), SimpleNamespace()

            async def register_job_owner(self, seen_job_id, user_id):
                registered_owners.append((seen_job_id, user_id))

            def start_job(self, seen_job_id, task_coro):
                started_jobs.append(seen_job_id)
                task_coro.close()

        monkeypatch.setattr(wf_bg, "get_job_service", lambda: FakeJobService())
        monkeypatch.setattr(wf_bg, "get_queue_service", lambda: FakeQueueService())
        monkeypatch.setattr(wf_bg, "_BACKGROUND_RUNS", {})

        response = await wf_bg.execute_workflow_background(
            parsed=ParsedWorkflowRun(flow_id=str(flow_id), mode="background"),
            flow=SimpleNamespace(id=flow_id, name="Background Flow"),
            job_id=job_id,
            current_user=SimpleNamespace(id=current_user_id),
            http_request=SimpleNamespace(),
            stream_protocol="agui",
        )

        assert str(response.job_id) == str(job_id)
        assert created_jobs == [job_id]
        assert started_jobs == [str(job_id)]
        assert registered_owners == []
        assert response.links["events"] == f"/api/v2/workflows/{job_id}/events"


class TestStopWorkflowEndToEnd:
    """The full ``POST /workflows/stop`` HTTP flow terminates the in-memory buffer too.

    ``test_background_run_can_be_stopped`` covers the 200 response. This class
    pins the side-effects: the in-process ``_BACKGROUND_RUNS`` entry remains
    replayable, the ``_BackgroundRun.done`` flag flips so re-attach readers
    unblock, and the Job row is marked ``CANCELLED``.
    """

    async def test_stop_finishes_replay_buffer_and_marks_job_cancelled(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
    ):
        from uuid import UUID as _UUID

        from langflow.api.v2 import workflow as workflow_module
        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.services.database.models.jobs.model import Job, JobStatus

        headers = {"x-api-key": created_api_key.api_key}
        start = await client.post(
            "api/v2/workflows",
            json=_agui_body(chatbot_flow, mode="background"),
            headers=headers,
        )
        assert start.status_code == 200
        job_id = start.json()["job_id"]

        # The registry holds the buffer keyed by job_id so reconnect can replay
        # the cancellation terminal event after /stop returns.
        assert job_id in workflow_module._BACKGROUND_RUNS, (
            "Background run was not registered; the stop assertions below would be vacuous"
        )
        bg_run = workflow_module._BACKGROUND_RUNS[job_id]

        try:
            stop = await client.post(
                "api/v2/workflows/stop",
                json={"job_id": job_id},
                headers=headers,
            )
            assert stop.status_code == 200

            # Side-effects: registry remains replayable, buffer finished, job row CANCELLED.
            assert job_id in workflow_module._BACKGROUND_RUNS
            assert bg_run.done is True

            events = await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)
            assert events.status_code == 200
            # A deliberate stop replays as a CUSTOM cancel marker + RUN_FINISHED, not
            # RUN_ERROR: a re-attaching client must not read a user-stop as a failure.
            assert "RUN_ERROR" not in events.text
            assert "langflow.run.cancelled" in events.text
            assert "RUN_FINISHED" in events.text

            async with session_scope() as session:
                row = await session.get(Job, _UUID(job_id))
            assert row is not None
            assert row.status == JobStatus.CANCELLED
        finally:
            await wf_bg._clear_background_run(job_id)

    async def test_stop_cancels_queue_owned_background_task_when_task_service_noops(
        self,
        client: AsyncClient,
        created_api_key,
        chatbot_flow,
        monkeypatch,
    ):
        """The v2 background runner is owned by the queue service, not TaskService."""
        from langflow.api.v2 import workflow_background as wf_bg
        from langflow.api.v2 import workflow_execution as wf_exec
        from langflow.services.deps import get_queue_service
        from langflow.services.job_queue.service import JobQueueNotFoundError

        started = asyncio.Event()
        cancelled = asyncio.Event()
        job_id: str | None = None

        async def _never_finishes(**_kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        class NoopTaskService:
            async def revoke_task(self, _task_id):
                return True

        monkeypatch.setattr(wf_bg, "_buffer_background_run", _never_finishes)
        monkeypatch.setattr(wf_exec, "get_task_service", lambda: NoopTaskService())

        headers = {"x-api-key": created_api_key.api_key}
        try:
            start = await client.post(
                "api/v2/workflows",
                json=_agui_body(chatbot_flow, mode="background"),
                headers=headers,
            )
            assert start.status_code == 200
            job_id = start.json()["job_id"]
            await asyncio.wait_for(started.wait(), timeout=2)

            stop = await client.post(
                "api/v2/workflows/stop",
                json={"job_id": job_id},
                headers=headers,
            )

            assert stop.status_code == 200
            assert cancelled.is_set()
            try:
                _, _, task, _ = get_queue_service().get_queue_data(job_id)
            except JobQueueNotFoundError:
                task = None
            assert task is None or task.done()
        finally:
            if job_id is not None:
                with contextlib.suppress(BaseException):
                    await get_queue_service().cleanup_job(job_id)
                await wf_bg._clear_background_run(job_id)

    async def test_stop_signals_cross_worker_queue_owner_before_marking_cancelled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Redis-backed jobs owned by another worker must be cancelled by pub/sub signal."""
        from langflow.api.v2 import workflow as workflow_module
        from langflow.api.v2 import workflow_background as wf_bg

        job_id = uuid4()
        current_user_id = uuid4()
        events: list[tuple[str, object, object | None]] = []

        class FakeJobService:
            def __init__(self) -> None:
                self.updates: list[tuple[object, object]] = []

            async def get_job_by_job_id(self, seen_job_id, user_id=None):
                assert seen_job_id == job_id
                assert user_id == current_user_id
                return SimpleNamespace(
                    type=workflow_module.JobType.WORKFLOW,
                    status=workflow_module.JobStatus.IN_PROGRESS,
                )

            async def update_job_status(self, seen_job_id, status):
                events.append(("update", seen_job_id, status))
                self.updates.append((seen_job_id, status))

        class CrossWorkerQueueService:
            cross_worker_cancel_enabled = True

            def __init__(self) -> None:
                self.local_cancels: list[str] = []
                self.signals: list[str] = []

            def get_queue_data(self, seen_job_id):
                assert seen_job_id == str(job_id)
                return SimpleNamespace(), SimpleNamespace(), None, None

            async def cancel_job(self, seen_job_id):
                self.local_cancels.append(seen_job_id)

            async def signal_cancel(self, seen_job_id):
                events.append(("signal", seen_job_id, None))
                self.signals.append(seen_job_id)
                return 0

        job_service = FakeJobService()
        queue_service = CrossWorkerQueueService()
        monkeypatch.setattr(workflow_module, "get_job_service", lambda: job_service)
        monkeypatch.setattr(wf_bg, "get_queue_service", lambda: queue_service)

        response = await workflow_module.stop_workflow(
            workflow_module.WorkflowStopRequest(job_id=job_id),
            current_user=SimpleNamespace(id=current_user_id),
        )

        assert str(response.job_id) == str(job_id)
        assert queue_service.local_cancels == []
        assert queue_service.signals == [str(job_id)]
        assert job_service.updates == [(job_id, workflow_module.JobStatus.CANCELLED)]
        assert events == [
            ("signal", str(job_id), None),
            ("update", job_id, workflow_module.JobStatus.CANCELLED),
        ]
