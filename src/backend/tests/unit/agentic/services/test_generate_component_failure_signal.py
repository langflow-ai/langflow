"""Bug #7 (PR-12575): a failed generate_component sub-task was silently swallowed.

In a compound turn ("create a component AND build a flow with it"), the agent
calls the ``GenerateComponent`` tool mid-loop. When generation failed
validation, the tool only returned an error STRING to the agent -- which the
agent could bury in prose or paper over by substituting a generic component, so
the user never got a clear signal the component they asked for was never built.

The tool must ALSO push a structured failure onto the component-events queue so
the SSE layer surfaces a ``validation_failed`` signal regardless of what the
agent decides to say. A SUCCESSFUL generation must emit nothing.
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.component_events import (
    drain_component_events,
    reset_component_events,
)


@pytest.fixture
def fresh_component_events():
    reset_component_events()
    yield
    reset_component_events()


async def test_should_emit_validation_failed_signal_when_generation_fails(monkeypatch, fresh_component_events):  # noqa: ARG001
    from lfx.mcp.flow_builder_tools.run_tools import GenerateComponent

    async def _failed_generation(**_kwargs):
        return {"validated": False, "validation_error": "Output method 'run' has no return statement"}

    monkeypatch.setattr(
        "langflow.agentic.services.assistant_service.execute_flow_with_validation",
        _failed_generation,
    )

    tool = GenerateComponent()
    tool.set(spec="a tool that uppercases text")
    result = await tool.generate_component()

    # The agent still gets the error (so it can stop / retry honestly)...
    assert "error" in result.data
    # ...but the failure is ALSO surfaced as a structured, out-of-band signal
    # the frontend renders even if the agent's prose omits it.
    events = drain_component_events()
    assert len(events) == 1
    assert "Output method" in events[0]["error"]


async def test_should_not_emit_signal_when_generation_succeeds(monkeypatch, fresh_component_events):  # noqa: ARG001
    from lfx.mcp.flow_builder_tools.run_tools import GenerateComponent

    async def _ok_generation(**_kwargs):
        return {"validated": True, "class_name": "FooTool", "component_code": "class FooTool: ..."}

    monkeypatch.setattr(
        "langflow.agentic.services.assistant_service.execute_flow_with_validation",
        _ok_generation,
    )

    tool = GenerateComponent()
    tool.set(spec="a tool that uppercases text")
    result = await tool.generate_component()

    assert result.data.get("class_name") == "FooTool"
    assert drain_component_events() == []
