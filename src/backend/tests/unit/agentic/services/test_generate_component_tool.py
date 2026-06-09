"""GenerateComponent MCP tool — the single-agent-loop keystone.

Lets ONE agent loop create a custom component mid-task (the Claude Code
pattern: one agent, many tools). Lives in lfx.mcp.flow_builder_tools but
exercised here because it lazily imports langflow.agentic.services.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from lfx.mcp.flow_builder_tools import GenerateComponent

EFV = "langflow.agentic.services.assistant_service.execute_flow_with_validation"


def _run(tool: GenerateComponent):
    return asyncio.run(tool.generate_component())


class TestGenerateComponentTool:
    def test_success_returns_class_name_for_the_agent(self):
        tool = GenerateComponent()
        tool.set(spec="a component that tells if a number is prime")
        with patch(
            EFV,
            new_callable=AsyncMock,
            return_value={"validated": True, "class_name": "PrimeChecker", "component_code": "code"},
        ) as m:
            data = _run(tool)

        m.assert_awaited_once()
        assert data.data["class_name"] == "PrimeChecker"
        # The LLM only reads `text`; it must learn the class name AND that it
        # is now usable via search_components.
        assert "PrimeChecker" in data.data["text"]
        assert "search_components" in data.data["text"]
        assert "error" not in data.data

    def test_validation_failure_surfaces_as_error_not_exception(self):
        tool = GenerateComponent()
        tool.set(spec="broken thing")
        with patch(
            EFV,
            new_callable=AsyncMock,
            return_value={"validated": False, "validation_error": "missing inputs"},
        ):
            data = _run(tool)

        assert "error" in data.data
        assert "missing inputs" in data.data["error"]
        assert data.data["text"] == data.data["error"]

    def test_empty_description_refuses_without_calling_pipeline(self):
        tool = GenerateComponent()
        tool.set(spec="   ")
        with patch(EFV, new_callable=AsyncMock) as m:
            data = _run(tool)

        m.assert_not_awaited()
        assert "error" in data.data

    def test_passes_request_provider_model_and_user_from_context(self):
        from langflow.agentic.services.agent_run_context import reset_agent_run_model, set_agent_run_model
        from langflow.agentic.services.user_components_context import (
            reset_current_user_id,
            set_current_user_id,
        )

        set_current_user_id("user-1")
        set_agent_run_model("OpenAI", "gpt-4o-mini", "OPENAI_API_KEY")
        try:
            tool = GenerateComponent()
            tool.set(spec="a JSON parser component")
            with patch(
                EFV,
                new_callable=AsyncMock,
                return_value={"validated": True, "class_name": "JsonParser", "component_code": "c"},
            ) as m:
                _run(tool)
            kwargs = m.call_args.kwargs
            assert kwargs["user_id"] == "user-1"
            assert kwargs["provider"] == "OpenAI"
            assert kwargs["model_name"] == "gpt-4o-mini"
            assert kwargs["api_key_var"] == "OPENAI_API_KEY"
            # A valid FLOW_ID must be passed so the internal generation
            # sub-flow's tracing doesn't log "Invalid flow_id ... None"
            # and fall back to a sentinel on every component generation.
            import uuid

            fid = kwargs["global_variables"]["FLOW_ID"]
            uuid.UUID(fid)  # raises if not a valid UUID string
        finally:
            reset_current_user_id()
            reset_agent_run_model()


class TestGenerateComponentContextIsolation:
    """A nested generation run must not touch the parent agent loop's state.

    Bug: during a `component_then_flow` build the agent has already added
    components to the working flow (events queued, working flow set). It
    then calls GenerateComponent, which re-enters
    `execute_flow_with_validation`. That pipeline drains flow events and
    `reset_working_flow()`s in the SAME ContextVar scope, so the parent's
    in-progress canvas is wiped and its pending events are stolen.
    """

    def test_should_preserve_parent_canvas_and_events_when_generating_component_during_build(self):
        from lfx.mcp.flow_builder_tools import (
            _emit,
            drain_flow_events,
            get_working_flow,
            init_working_flow,
            reset_working_flow,
        )

        async def scenario():
            # Arrange — parent agent loop already built a canvas + queued an event
            parent_flow = {"data": {"nodes": [{"id": "ChatInput-1"}], "edges": []}}
            init_working_flow(parent_flow, "flow-123")
            _emit("add_component", node={"id": "ChatInput-1"})

            async def _nested_pipeline(*_args, **_kwargs):
                # Mirror execute_flow_with_validation lines ~208-211: the
                # nested run drains events and resets the working flow.
                drain_flow_events()
                reset_working_flow()
                return {"validated": True, "class_name": "Prime", "component_code": "code"}

            tool = GenerateComponent()
            tool.set(spec="a component that tells if a number is prime")
            with patch(EFV, new_callable=AsyncMock, side_effect=_nested_pipeline):
                data = await tool.generate_component()

            # Assert — the agent still learns the class name...
            assert data.data["class_name"] == "Prime"
            # ...AND the parent canvas + queued events survived the nested run.
            assert get_working_flow() == parent_flow
            assert drain_flow_events() == [{"action": "add_component", "node": {"id": "ChatInput-1"}}]

        asyncio.run(scenario())
