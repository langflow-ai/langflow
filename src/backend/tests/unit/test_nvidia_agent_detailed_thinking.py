"""Regression for #8928: Agent + NVIDIA detailed_thinking attribute."""

import pytest
from lfx.base.models.model import DETAILED_THINKING_PREFIX, LCModelComponent
from lfx.components.models_and_agents.agent import AgentComponent

from tests.unit.mock_language_model import MockLanguageModel


def test_lc_model_component_has_detailed_thinking_default():
    """LCModelComponent must expose detailed_thinking so Agent+NVIDIA never raises."""
    comp = LCModelComponent.__new__(LCModelComponent)
    comp.__dict__["_attributes"] = {}
    comp.__dict__["_inputs"] = {}
    comp.__dict__["_outputs_map"] = {}
    try:
        val = comp.detailed_thinking  # should be False after fix, raises before
    except AttributeError as e:
        pytest.fail(f"detailed_thinking attribute not found: {e}")
    assert val is False


def test_agent_component_has_detailed_thinking_default():
    """AgentComponent must also expose detailed_thinking without raising."""
    agent = AgentComponent.__new__(AgentComponent)
    # Simulate minimal init without going through Component.__init__ fully
    # Ensure _attributes exists to trigger __getattr__ path
    agent.__dict__["_attributes"] = {}
    agent.__dict__["_inputs"] = {}
    agent.__dict__["_outputs_map"] = {}
    try:
        val = agent.detailed_thinking
    except AttributeError as e:
        pytest.fail(f"Agent detailed_thinking attribute not found: {e}")
    assert val is False


@pytest.mark.asyncio
async def test_lc_model_get_chat_result_handles_missing_detailed_thinking():
    """LCModelComponent.get_chat_result must not raise when detailed_thinking is absent."""

    # Create minimal concrete subclass
    class DummyModel(LCModelComponent):
        def build_model(self):
            return MockLanguageModel()

    comp = DummyModel.__new__(DummyModel)
    comp.__dict__["_attributes"] = {}
    comp.__dict__["_inputs"] = {}
    comp.__dict__["_outputs_map"] = {}
    # Ensure detailed_thinking not in attributes (simulates non-Nemotron model)
    called = {}

    async def fake_get_chat_result(**kwargs):
        called["system_message"] = kwargs.get("system_message")
        from lfx.schema.message import Message as Msg

        return Msg(text="ok")

    # Patch instance method
    object.__setattr__(comp, "_get_chat_result", fake_get_chat_result)
    mock_runnable = MockLanguageModel()

    result = await comp.get_chat_result(runnable=mock_runnable, stream=False, input_value="Hi", system_message="hi")
    assert result.text == "ok"
    assert called["system_message"] == "hi"


@pytest.mark.asyncio
async def test_lc_model_prefixes_system_message_when_detailed_thinking_true():
    """When detailed_thinking is True, system_message must be prefixed."""

    class DummyModel(LCModelComponent):
        def build_model(self):
            return MockLanguageModel()

    comp = DummyModel.__new__(DummyModel)
    comp.__dict__["_attributes"] = {"detailed_thinking": True}
    comp.__dict__["_inputs"] = {}
    comp.__dict__["_outputs_map"] = {}

    called = {}

    async def fake_get_chat_result(**kwargs):
        called["system_message"] = kwargs.get("system_message")
        from lfx.schema.message import Message as Msg

        return Msg(text="ok")

    object.__setattr__(comp, "_get_chat_result", fake_get_chat_result)
    mock_runnable = MockLanguageModel()

    result = await comp.get_chat_result(runnable=mock_runnable, stream=False, input_value="Hi", system_message="orig")
    assert result.text == "ok"
    assert called["system_message"] == DETAILED_THINKING_PREFIX + "orig"
    assert called["system_message"].startswith("detailed thinking on")
