"""Integration test proving A2A agent-to-agent operability end-to-end.

Unlike the rest of the A2A suite, this test does **not** mock flow
execution. A real Langflow flow (``MemoryChatbotNoLLM`` — runs without any
API keys) is exposed as an A2A agent, and a separate A2A client invokes it
over the real REST protocol, receiving the real artifact the flow computed.

It also validates the exchanged AgentCard and Task against the official
``a2a-sdk`` pydantic types, so the bytes on the wire are protocol-shaped,
not just internally consistent.

This is the "operability" proof: one agent (the client) talks to another
agent (a Langflow flow) over A2A, end to end, with real execution.
"""

import json
from pathlib import Path

import pytest
from a2a.types import AgentCard, Task
from httpx import AsyncClient
from langflow.api.a2a.client import A2AClient, extract_text_artifacts
from langflow.services.database.models.flow.model import FlowCreate
from lfx.components.a2a import A2AClientComponent, ApprovalGateComponent
from lfx.schema.message import Message

pytestmark = pytest.mark.asyncio

# Real, runnable, no-API-key flow shipped with the test suite.
_FLOW_PATH = Path(__file__).resolve().parents[3] / "data" / "MemoryChatbotNoLLM.json"


def _load_flow_data() -> dict:
    raw = json.loads(_FLOW_PATH.read_text(encoding="utf-8"))
    return raw.get("data", raw)


async def _expose_flow_as_a2a(client: AsyncClient, headers: dict, *, slug: str, name: str) -> str:
    """Create the no-LLM flow and turn it into an A2A agent. Returns flow_id."""
    flow = FlowCreate(name=name, description="No-LLM flow exposed via A2A", data=_load_flow_data())
    create = await client.post("api/v1/flows/", json=flow.model_dump(), headers=headers)
    assert create.status_code == 201, create.text
    flow_id = create.json()["id"]

    cfg = await client.put(
        f"api/v1/flows/{flow_id}/a2a-config",
        json={"a2a_enabled": True, "a2a_agent_slug": slug, "a2a_name": name},
        headers=headers,
    )
    assert cfg.status_code == 200, cfg.text
    return flow_id


class TestA2AAgentToAgentOperability:
    """End-to-end: a client agent delegates a task to a Langflow agent over A2A."""

    async def test_real_round_trip_message_send(self, client: AsyncClient, logged_in_headers):
        """Discover → delegate → receive, with REAL flow execution (no mocks)."""
        slug = "ata-send"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Send Agent")

        # The "calling agent": a real A2A client whose transport is the
        # in-process Langflow app (same pattern the MCP client-server test uses).
        caller = A2AClient(client, base_url=f"/a2a/{slug}", headers=logged_in_headers)

        # 1) Discovery — and the card must validate against the official type.
        card = await caller.get_agent_card()
        AgentCard.model_validate(card)
        assert card["name"] == "Send Agent"
        assert card["capabilities"]["streaming"] is True

        # 2) Delegate a task. The probe must reappear in the agent's real output,
        #    proving the flow actually executed on our input (not a canned reply).
        probe = "PingFromCallingAgent-42"
        task = await caller.send_message(probe, context_id="ctx-ata-send")

        assert task["status"]["state"] == "completed", task
        Task.model_validate(task)  # protocol-shape compliance

        texts = extract_text_artifacts(task)
        assert texts, f"expected text artifacts, got: {task}"
        assert probe in " ".join(texts), f"flow output did not reflect input: {texts}"

        # 3) The task is independently retrievable (polling path).
        polled = await caller.get_task(task["id"])
        assert polled["id"] == task["id"]
        assert polled["status"]["state"] == "completed"

    async def test_real_round_trip_streaming(self, client: AsyncClient, logged_in_headers):
        """The streaming endpoint drives a real execution to a terminal state."""
        slug = "ata-stream"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Stream Agent")
        caller = A2AClient(client, base_url=f"/a2a/{slug}", headers=logged_in_headers)

        probe = "StreamProbe-77"
        events = [e async for e in caller.stream_message(probe, context_id="ctx-ata-stream")]
        assert events, "no SSE events received"

        states = [e["status"]["state"] for e in events if e.get("kind") == "status-update"]
        assert "working" in states
        assert "completed" in states

        # The real output text must surface, either as streamed artifact chunks
        # or the final artifact emitted before completion.
        streamed_text = "".join(
            part.get("text", "")
            for e in events
            if e.get("kind") == "artifact-update"
            for part in e.get("artifact", {}).get("parts", [])
        )
        assert probe in streamed_text, f"streamed output did not reflect input: {streamed_text!r}"

    async def test_multi_turn_same_context_real_execution(self, client: AsyncClient, logged_in_headers):
        """Two turns sharing a contextId both execute for real and complete."""
        slug = "ata-multiturn"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Multiturn Agent")
        caller = A2AClient(client, base_url=f"/a2a/{slug}", headers=logged_in_headers)

        t1 = await caller.send_message("first turn ABC", context_id="ctx-shared")
        t2 = await caller.send_message("second turn XYZ", context_id="ctx-shared")

        assert t1["status"]["state"] == "completed"
        assert t2["status"]["state"] == "completed"
        assert t1["id"] != t2["id"]
        assert t1["contextId"] == t2["contextId"] == "ctx-shared"

    async def test_tasks_are_scoped_to_their_agent(self, client: AsyncClient, logged_in_headers):
        """One agent cannot read or list another agent's tasks (isolation)."""
        await _expose_flow_as_a2a(client, logged_in_headers, slug="iso-a", name="Agent A")
        await _expose_flow_as_a2a(client, logged_in_headers, slug="iso-b", name="Agent B")
        caller_a = A2AClient(client, base_url="/a2a/iso-a", headers=logged_in_headers)

        task = await caller_a.send_message("secret work for A", context_id="ctx-iso")
        task_id = task["id"]

        # Reading A's task through A's endpoint works...
        assert (await caller_a.get_task(task_id))["id"] == task_id

        # ...but the SAME task id is invisible through agent B's endpoint.
        cross = await client.get(f"/a2a/iso-b/v1/tasks/{task_id}", headers=logged_in_headers)
        assert cross.status_code == 404

        # And B's task list does not include A's task.
        b_list = await client.get("/a2a/iso-b/v1/tasks", headers=logged_in_headers)
        assert b_list.status_code == 200
        assert task_id not in {t["id"] for t in b_list.json()}

    async def test_a2a_client_component_delegates_to_langflow_agent(self, client: AsyncClient, logged_in_headers):
        """Langflow → Langflow over A2A via the "A2A Agent" canvas component.

        A flow is exposed as an A2A agent (server), and the A2A Client
        *component* — the node a builder drops into a flow — delegates a task
        to it and returns the remote agent's real result as a Message.
        """
        slug = "ata-component"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Component Target")

        token = logged_in_headers["Authorization"].removeprefix("Bearer ")
        probe = "ComponentProbe-99"

        component = A2AClientComponent()
        component.set(agent_url=f"/a2a/{slug}", input_value=probe, auth_token=token, context_id="")
        # Route the component's A2A calls through the in-process app.
        component._http_client = client

        result = await component.call_remote_agent()

        assert isinstance(result, Message)
        assert probe in (result.text or ""), f"component did not return the remote agent's output: {result.text!r}"


class TestApprovalGate:
    """The Approval Gate guardrail can block or release a side-effecting action."""

    def test_approved_releases_action(self):
        gate = ApprovalGateComponent()
        gate.set(input_value=Message(text="deploy to prod"), is_approved=True)
        out = gate.gate()
        assert isinstance(out, Message)
        assert out.text == "deploy to prod"

    def test_rejected_blocks_action(self):
        gate = ApprovalGateComponent()
        gate.set(input_value=Message(text="deploy to prod"), is_approved=False, rejection_reason="needs review")
        with pytest.raises(ValueError, match="blocked"):
            gate.gate()

    async def test_gate_controls_a2a_delegation(self, client: AsyncClient, logged_in_headers):
        """Approve → the A2A delegation runs; reject → it is blocked before any call."""
        slug = "ata-gated"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Gated Target")
        token = logged_in_headers["Authorization"].removeprefix("Bearer ")

        async def delegate_after_gate(*, approved: bool) -> Message:
            gate = ApprovalGateComponent()
            gate.set(input_value=Message(text="GatedProbe-7"), is_approved=approved, rejection_reason="denied")
            released = gate.gate()  # raises ValueError if not approved
            agent = A2AClientComponent()
            agent.set(agent_url=f"/a2a/{slug}", input_value=released.text, auth_token=token, context_id="")
            agent._http_client = client
            return await agent.call_remote_agent()

        # Approved → the real delegation completes and returns the agent's output.
        result = await delegate_after_gate(approved=True)
        assert "GatedProbe-7" in (result.text or "")

        # Rejected → the gate raises and the A2A delegation never happens.
        with pytest.raises(ValueError, match="blocked"):
            await delegate_after_gate(approved=False)


class TestA2ATraceVisibility:
    """A2A delegation and approval decisions are recorded as trace logs.

    Component.log() both stores to the component and forwards to the tracing
    service, so asserting the emitted log proves the activity is visible in
    Langflow Traces when a tracer is active.
    """

    async def test_delegation_status_logged_for_traces(self, client: AsyncClient, logged_in_headers):
        slug = "ata-trace"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="Trace Target")
        token = logged_in_headers["Authorization"].removeprefix("Bearer ")

        comp = A2AClientComponent()
        comp.set(agent_url=f"/a2a/{slug}", input_value="TraceProbe-5", auth_token=token, context_id="")
        comp._http_client = client
        await comp.call_remote_agent()

        delegation_logs = [lg for lg in comp._logs if lg.name == "a2a_delegation"]
        assert delegation_logs, f"no a2a_delegation trace log; logs={[lg.name for lg in comp._logs]}"
        recorded = str(delegation_logs[0].message)
        assert "completed" in recorded  # the delegated task's status is in the trace

    def test_approval_decision_logged_for_traces(self):
        approved = ApprovalGateComponent()
        approved.set(input_value=Message(text="x"), is_approved=True)
        approved.gate()
        assert any(lg.name == "approval_gate" and "approved" in str(lg.message) for lg in approved._logs)

        rejected = ApprovalGateComponent()
        rejected.set(input_value=Message(text="x"), is_approved=False, rejection_reason="no")
        with pytest.raises(ValueError, match="blocked"):
            rejected.gate()
        assert any(lg.name == "approval_gate" and "rejected" in str(lg.message) for lg in rejected._logs)


class TestA2ADatabaseTaskStore:
    """A2A task state is persisted to the database, not just process memory."""

    async def test_tasks_persist_across_manager_instances(self, client: AsyncClient, logged_in_headers):  # noqa: ARG002
        from langflow.api.a2a.db_task_manager import DatabaseTaskManager

        writer = DatabaseTaskManager()
        created = await writer.create_task(flow_id="flow-xyz", context_id="ctx-db")
        task_id = created["id"]

        # A brand-new manager instance shares no in-process state, so seeing
        # the task proves it was read back from the database.
        reader = DatabaseTaskManager()
        fetched = await reader.get_task(task_id)
        assert fetched is not None
        assert fetched["id"] == task_id
        assert fetched["metadata"]["flowId"] == "flow-xyz"

        # State transitions and artifacts persist too.
        await writer.update_state(
            task_id,
            "completed",
            artifacts=[{"artifactId": "a", "parts": [{"kind": "text", "text": "done"}]}],
        )
        reloaded = await reader.get_task(task_id)
        assert reloaded["status"]["state"] == "completed"
        assert reloaded["artifacts"][0]["parts"][0]["text"] == "done"

    async def test_http_task_is_in_database(self, client: AsyncClient, logged_in_headers):
        """A task created via the HTTP API is retrievable from the DB store directly."""
        from langflow.api.a2a.db_task_manager import DatabaseTaskManager

        slug = "ata-dbtask"
        await _expose_flow_as_a2a(client, logged_in_headers, slug=slug, name="DB Task Agent")
        caller = A2AClient(client, base_url=f"/a2a/{slug}", headers=logged_in_headers)
        task = await caller.send_message("persist me", context_id="ctx-http-db")

        # Read it straight from the database via a fresh manager.
        from_db = await DatabaseTaskManager().get_task(task["id"])
        assert from_db is not None
        assert from_db["status"]["state"] == "completed"
