"""RunFlow MCP tool — the agent-facing piece.

Lives in lfx.mcp.flow_builder_tools but is exercised here (backend tree)
because it lazily imports langflow.agentic.services.flow_run, which the
isolated lfx suite cannot resolve.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from lfx.mcp.flow_builder_tools import (
    RunFlow,
    drain_flow_events,
    init_working_flow,
    reset_working_flow,
)

RWF = "langflow.agentic.services.flow_run.run_working_flow"


def _run(tool: RunFlow):
    return asyncio.run(tool.run_flow())


class TestRunFlowTool:
    def setup_method(self):
        reset_working_flow()

    def test_returns_result_text_for_the_agent_on_success(self):
        init_working_flow(
            {"name": "F", "data": {"nodes": [{"id": "ChatInput-1"}], "edges": []}},
            "flow-1",
        )
        with patch(RWF, new_callable=AsyncMock, return_value={"result": "woof"}) as m:
            data = _run(RunFlow())

        m.assert_awaited_once()
        # The LLM reads `text`; it must carry the run result so the agent can
        # answer questions about it.
        assert data.data["text"] == "woof"
        assert data.data["result"] == "woof"

    def test_exposes_run_metrics_to_the_agent(self):
        init_working_flow(
            {"name": "F", "data": {"nodes": [{"id": "ChatInput-1"}], "edges": []}},
            "flow-1",
        )
        metrics = {
            "duration_seconds": 1.25,
            "input_tokens": 7,
            "output_tokens": 3,
            "total_tokens": 10,
        }
        with patch(
            RWF,
            new_callable=AsyncMock,
            return_value={"result": "woof", "metrics": metrics},
        ):
            data = _run(RunFlow())

        # Structured for any programmatic use.
        assert data.data["metrics"] == metrics
        # The LLM only reads `text`; the performance summary must be in it so
        # the agent can actually report time/tokens to the user.
        assert "1.25" in data.data["text"]
        assert "10" in data.data["text"]

    def test_refuses_when_canvas_is_empty_without_running(self):
        init_working_flow({"name": "F", "data": {"nodes": [], "edges": []}}, "flow-1")
        with patch(RWF, new_callable=AsyncMock) as m:
            data = _run(RunFlow())

        m.assert_not_awaited()
        assert "error" in data.data
        assert "no flow" in data.data["error"].lower() or "empty" in data.data["error"].lower()

    def test_surfaces_run_error_as_data_error_not_exception(self):
        init_working_flow(
            {"name": "F", "data": {"nodes": [{"id": "Agent-1"}], "edges": []}},
            "flow-1",
        )
        with patch(RWF, new_callable=AsyncMock, return_value={"error": "Rate limit exceeded."}):
            data = _run(RunFlow())

        assert data.data["error"] == "Rate limit exceeded."
        assert data.data["text"] == "Rate limit exceeded."

    def test_passes_working_flow_and_flow_id_to_orchestration(self):
        flow = {"name": "F", "data": {"nodes": [{"id": "ChatInput-1"}], "edges": []}}
        init_working_flow(flow, "flow-xyz")
        with patch(RWF, new_callable=AsyncMock, return_value={"result": "ok"}) as m:
            _run(RunFlow())

        kwargs = m.call_args.kwargs
        assert kwargs["flow_id"] == "flow-xyz"
        assert kwargs["flow_data"]["data"]["nodes"][0]["id"] == "ChatInput-1"


class TestRunFlowEmitsRanSignal:
    """RunFlow must emit a deterministic ``flow_ran`` signal on success.

    This is the LLM/language-agnostic anchor for "the agent built AND ran
    the flow this turn → apply it to the canvas". It fires on the REAL
    action (a successful run), never inferred from the user's wording, so
    paraphrases like "rode ele" / "run it" / any language work identically.
    """

    def setup_method(self):
        reset_working_flow()

    def test_emits_flow_ran_on_successful_run(self):
        init_working_flow(
            {"name": "F", "data": {"nodes": [{"id": "ChatInput-1"}], "edges": []}},
            "flow-1",
        )
        with patch(RWF, new_callable=AsyncMock, return_value={"result": "12.0"}):
            _run(RunFlow())

        events = drain_flow_events()
        ran = [e for e in events if e.get("action") == "flow_ran"]
        assert len(ran) == 1, f"expected exactly one flow_ran, got {events}"

    def test_does_not_emit_flow_ran_when_run_errors(self):
        init_working_flow(
            {"name": "F", "data": {"nodes": [{"id": "Agent-1"}], "edges": []}},
            "flow-1",
        )
        with patch(RWF, new_callable=AsyncMock, return_value={"error": "Authentication failed."}):
            _run(RunFlow())

        assert not [e for e in drain_flow_events() if e.get("action") == "flow_ran"], (
            "a failed run must NOT claim the flow ran (no false canvas application)"
        )

    def test_does_not_emit_flow_ran_when_canvas_empty(self):
        init_working_flow({"name": "F", "data": {"nodes": [], "edges": []}}, "flow-1")
        with patch(RWF, new_callable=AsyncMock):
            _run(RunFlow())

        assert not [e for e in drain_flow_events() if e.get("action") == "flow_ran"]


class TestRunFlowInjectsVerifiedModel:
    """The assistant-triggered run must use a model that AUTHENTICATES.

    Bug (real user): the assistant built ChatInput->Agent->ChatOutput and
    ran it; the Agent's model (LLM-chosen / empty) had no configured key
    -> "Authentication failed. Check your API key." The assistant itself
    runs with a verified provider/model/api_key (agent_run_context); that
    working credential must be injected into the Agent before running so
    the user actually gets a result. Deterministic, LLM-agnostic.
    """

    def setup_method(self):
        reset_working_flow()

    def teardown_method(self):
        from langflow.agentic.services.agent_run_context import reset_agent_run_model

        reset_working_flow()
        reset_agent_run_model()

    def _agent_flow(self):
        return {
            "name": "F",
            "data": {
                "nodes": [
                    {
                        "id": "Agent-1",
                        "data": {"type": "Agent", "node": {"template": {"model": {"value": ""}}}},
                    }
                ],
                "edges": [],
            },
        }

    def test_injects_the_assistants_verified_model_into_modelless_agent_before_running(self):
        from langflow.agentic.services.agent_run_context import set_agent_run_model

        set_agent_run_model("OpenAI", "gpt-4o", "OPENAI_API_KEY")
        init_working_flow(self._agent_flow(), "flow-1")

        with patch(RWF, new_callable=AsyncMock, return_value={"result": "42 is prime"}) as m:
            data = _run(RunFlow())

        flow_data = m.await_args.kwargs["flow_data"]
        agent_tmpl = flow_data["data"]["nodes"][0]["data"]["node"]["template"]
        model_value = agent_tmpl["model"]["value"]
        # The Agent now carries the assistant's verified model (structured),
        # not the empty/LLM-chosen one -> the run can authenticate.
        assert isinstance(model_value, list)
        assert model_value
        assert model_value[0]["name"] == "gpt-4o"
        assert model_value[0]["provider"] == "OpenAI"
        assert data.data["result"] == "42 is prime"

    def test_runs_normally_when_no_verified_model_is_bound(self):
        # No agent_run_context set -> no injection, but the run still works
        # (no regression to the existing success path).
        init_working_flow(self._agent_flow(), "flow-1")
        with patch(RWF, new_callable=AsyncMock, return_value={"result": "ok"}) as m:
            data = _run(RunFlow())

        m.assert_awaited_once()
        assert data.data["result"] == "ok"


class TestRunFlowEnforcesRequestedModel:
    """A model the USER explicitly named must win on the canvas.

    Bug (real user): asked for the OpenAI gpt-5.4 model; the assistant's prose
    said gpt-5.4 but the canvas Agent showed gpt-5.5 (the assistant's OWN
    runtime model). Root cause: the agent left the Agent's model empty/wrong,
    and the run-time fill used the assistant's verified runtime model instead
    of the model the user asked for. When the request named a model, it must be
    ENFORCED on every Agent (overwrite), never the runtime model.
    """

    def setup_method(self):
        reset_working_flow()

    def teardown_method(self):
        from langflow.agentic.services.agent_run_context import (
            reset_agent_run_model,
            reset_requested_agent_model,
        )

        reset_working_flow()
        reset_agent_run_model()
        reset_requested_agent_model()

    def _agent_flow(self, existing_model_name: str):
        # Simulate what the build produced: an Agent already carrying the
        # assistant's runtime model (the wrong one) — enforcement must replace it.
        model_value = [{"provider": "OpenAI", "name": existing_model_name}] if existing_model_name else ""
        return {
            "name": "F",
            "data": {
                "nodes": [
                    {
                        "id": "Agent-1",
                        "data": {"type": "Agent", "node": {"template": {"model": {"value": model_value}}}},
                    }
                ],
                "edges": [],
            },
        }

    def test_enforces_the_user_named_model_over_the_runtime_model(self):
        from langflow.agentic.services.agent_run_context import (
            set_agent_run_model,
            set_requested_agent_model,
        )

        # Assistant's own runtime model (the one that would be wrongly injected).
        set_agent_run_model("OpenAI", "gpt-5.5", "OPENAI_API_KEY")
        # The model the user explicitly asked for.
        set_requested_agent_model("OpenAI", "gpt-5.4", "OPENAI_API_KEY")
        # Build left the Agent on the assistant's runtime model (the bug).
        init_working_flow(self._agent_flow("gpt-5.5"), "flow-1")

        with patch(RWF, new_callable=AsyncMock, return_value={"result": "good morning!"}) as m:
            _run(RunFlow())

        flow_data = m.await_args.kwargs["flow_data"]
        model_value = flow_data["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert isinstance(model_value, list)
        assert model_value
        assert model_value[0]["name"] == "gpt-5.4"
        assert model_value[0]["provider"] == "OpenAI"

    def test_enforces_user_model_even_when_agent_left_it_empty(self):
        from langflow.agentic.services.agent_run_context import (
            set_agent_run_model,
            set_requested_agent_model,
        )

        set_agent_run_model("OpenAI", "gpt-5.5", "OPENAI_API_KEY")
        set_requested_agent_model("OpenAI", "gpt-5.4", "OPENAI_API_KEY")
        init_working_flow(self._agent_flow(""), "flow-1")  # empty model

        with patch(RWF, new_callable=AsyncMock, return_value={"result": "ok"}) as m:
            _run(RunFlow())

        flow_data = m.await_args.kwargs["flow_data"]
        model_value = flow_data["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert model_value[0]["name"] == "gpt-5.4"

    def test_falls_back_to_runtime_model_when_no_model_was_requested(self):
        # Regression guard: with no explicit request, the existing behavior
        # (fill an empty model with the verified runtime model) is preserved.
        from langflow.agentic.services.agent_run_context import set_agent_run_model

        set_agent_run_model("OpenAI", "gpt-5.5", "OPENAI_API_KEY")
        init_working_flow(self._agent_flow(""), "flow-1")

        with patch(RWF, new_callable=AsyncMock, return_value={"result": "ok"}) as m:
            _run(RunFlow())

        flow_data = m.await_args.kwargs["flow_data"]
        model_value = flow_data["data"]["nodes"][0]["data"]["node"]["template"]["model"]["value"]
        assert model_value[0]["name"] == "gpt-5.5"
