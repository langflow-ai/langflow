"""Tests wiring the default system prompt template into Agent components."""

from lfx.base.agents.default_system_prompt import DEFAULT_SYSTEM_PROMPT_TEMPLATE


def _get_input_default(component_cls, input_name: str) -> str:
    """Return the default ``value`` of a named input on a component class."""
    for inp in component_cls.inputs:
        if getattr(inp, "name", None) == input_name:
            return getattr(inp, "value", None)
    msg = f"input {input_name!r} not found on {component_cls.__name__}"
    raise AssertionError(msg)


# Slice M — AgentComponent default system_prompt uses the new template
def test_should_use_default_template_as_system_prompt_default_on_agent_component():
    from lfx.components.models_and_agents.agent import AgentComponent

    value = _get_input_default(AgentComponent, "system_prompt")

    assert value == DEFAULT_SYSTEM_PROMPT_TEMPLATE


# Slice N — ToolCallingAgentComponent default system_prompt uses the new template
def test_should_use_default_template_as_system_prompt_default_on_tool_calling_agent():
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent

    value = _get_input_default(ToolCallingAgentComponent, "system_prompt")

    assert value == DEFAULT_SYSTEM_PROMPT_TEMPLATE


def _make_tool_calling_stub(system_prompt: str, monkeypatch):
    """Build a ToolCallingAgentComponent stub with LLM resolution and tool-agent creation short-circuited."""
    from types import SimpleNamespace

    from lfx.components.langchain_utilities import tool_calling as tc_module
    from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent

    component = ToolCallingAgentComponent.__new__(ToolCallingAgentComponent)
    component.system_prompt = system_prompt
    component.tools = []
    llm_stub = SimpleNamespace(model_name="fake-model-xyz")
    monkeypatch.setattr(component, "_get_llm", lambda: llm_stub, raising=False)
    monkeypatch.setattr(component, "validate_tool_names", lambda: None, raising=False)
    # Short-circuit agent construction — we only care about prompt rendering side-effects.
    monkeypatch.setattr(tc_module, "create_tool_calling_agent", lambda *_a, **_kw: object())
    monkeypatch.setattr(tc_module, "is_granite_model", lambda _llm: False)
    return component


# Slice O.3 — create_agent_runnable publishes substituted prompt via _effective_system_prompt
def test_should_publish_substituted_prompt_on_effective_system_prompt_when_placeholders_present(monkeypatch):
    # Arrange
    original = "Today is {current_date}. You are {model_name}. {optional_user_context}"
    component = _make_tool_calling_stub(original, monkeypatch)

    # Act
    component.create_agent_runnable()

    # Assert — user-facing system_prompt is preserved (no mutation).
    assert component.system_prompt == original
    # Assert — rendered prompt is published on _effective_system_prompt for run_agent.
    effective = component._effective_system_prompt
    assert "{current_date}" not in effective
    assert "{model_name}" not in effective
    assert "{optional_user_context}" not in effective
    assert "fake-model-xyz" in effective


# Slice O.4 — create_agent_runnable leaves _effective_system_prompt unset when no placeholders
def test_should_not_publish_effective_system_prompt_when_no_known_placeholders(monkeypatch):
    # Arrange
    custom_prompt = "You are a pirate."
    component = _make_tool_calling_stub(custom_prompt, monkeypatch)

    # Act
    component.create_agent_runnable()

    # Assert — no substitution happened; user-facing prompt untouched.
    assert component.system_prompt == custom_prompt
    # Assert — _effective_system_prompt stays unset; run_agent will fall back to system_prompt.
    assert not hasattr(component, "_effective_system_prompt")
