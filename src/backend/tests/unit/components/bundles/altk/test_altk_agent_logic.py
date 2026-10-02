"""Saved ALTK source still imports and fails with actionable retirement guidance."""

import pytest
from lfx.base.agents.altk_base_agent import ALTKBaseAgentComponent
from lfx.components.altk.altk_agent import ALTKAgentComponent, get_parent_agent_inputs


async def test_legacy_component_subclass_loads_but_cannot_execute():
    # Saved components import these historical names before defining their class.
    from lfx.base.agents.altk_tool_wrappers import PostToolProcessingWrapper, PreToolValidationWrapper

    class SavedALTKAgent(ALTKBaseAgentComponent):
        name = "ALTK Agent"
        inputs = ALTKAgentComponent.inputs
        outputs = ALTKAgentComponent.outputs

        def configure_tool_pipeline(self):
            self.pipeline_manager.configure_wrappers([PostToolProcessingWrapper(), PreToolValidationWrapper()])

    component = SavedALTKAgent(input_value="Saved flow", tools=[])
    assert component.input_value == "Saved flow"
    with pytest.raises(RuntimeError, match=r"retired.*1\.13\.0"):
        await component.message_response()


def test_legacy_executor_inputs_still_present():
    names = [field.name for field in get_parent_agent_inputs()]
    assert "verbose" in names
    assert "max_iterations" in names
    assert "handle_parsing_errors" in names
    assert "agent_llm" not in names
