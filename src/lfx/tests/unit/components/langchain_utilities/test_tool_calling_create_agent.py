"""Tests for ToolCallingAgentComponent.create_agent_runnable returning CompiledStateGraph.

Slice S7 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent


class _ToolCapableFakeChatModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel that pretends to support bind_tools (no-op)."""

    def bind_tools(self, tools, **_kwargs):  # type: ignore[override]
        # langchain.agents.create_agent calls bind_tools when constructing the model node;
        # for unit tests we just return self so the graph can be compiled successfully.
        self._bound_tools = tools
        return self


class _ToolCapableFakeWatsonxModel(_ToolCapableFakeChatModel):
    """Class name contains 'watsonx' so `is_watsonx_model(llm)` returns True;
    no `model_id` set so `is_granite_model(llm)` returns False — used to
    exercise the non-granite WatsonX branch (Llama/Mistral hosted on WatsonX).
    """


def _fake_chat_model() -> _ToolCapableFakeChatModel:
    return _ToolCapableFakeChatModel(responses=[AIMessage(content="fake answer")])


def _fake_tool(name: str = "calculator", description: str = "Adds two numbers"):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.args_schema = None
    return tool


def _component_with(model, tools, **kwargs) -> ToolCallingAgentComponent:
    component = ToolCallingAgentComponent()
    component._user_id = None
    component.cache = {}
    component.set(
        model=model,
        tools=tools,
        system_prompt=kwargs.get("system_prompt", "You are helpful."),
        chat_history=kwargs.get("chat_history", []),
        handle_parsing_errors=kwargs.get("handle_parsing_errors", True),
        verbose=kwargs.get("verbose", False),
        max_iterations=kwargs.get("max_iterations", 15),
        api_key=None,
    )
    return component


def test_should_return_compiled_state_graph_when_create_agent_runnable_called(monkeypatch) -> None:
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _fake_chat_model(),
    )
    component = _component_with(model="fake-model", tools=[_fake_tool()])

    runnable = component.create_agent_runnable()

    assert isinstance(runnable, CompiledStateGraph)


def test_should_return_compiled_state_graph_when_no_tools_provided(monkeypatch) -> None:
    """create_agent must accept an empty tool list — agent without tools is still valid."""
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _fake_chat_model(),
    )
    component = _component_with(model="fake-model", tools=[])

    runnable = component.create_agent_runnable()

    assert isinstance(runnable, CompiledStateGraph)


def test_should_pass_system_prompt_to_create_agent(monkeypatch) -> None:
    """The system_prompt configured on the component must reach create_agent's `system_prompt` kwarg."""
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        # Return a real graph so the rest of the chain works
        from langchain.agents import create_agent

        return create_agent(model=kwargs["model"], tools=kwargs.get("tools") or [])

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _fake_chat_model(),
    )
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.create_agent",
        _capture_create_agent,
    )

    component = _component_with(
        model="fake-model",
        tools=[_fake_tool()],
        system_prompt="You are a careful research agent.",
    )

    component.create_agent_runnable()

    assert captured.get("system_prompt") == "You are a careful research agent."


def test_should_omit_system_prompt_when_blank(monkeypatch) -> None:
    """Blank system_prompt should not be passed (avoid empty SystemMessage)."""
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        from langchain.agents import create_agent

        return create_agent(model=kwargs["model"], tools=kwargs.get("tools") or [])

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _fake_chat_model(),
    )
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.create_agent",
        _capture_create_agent,
    )

    component = _component_with(model="fake-model", tools=[_fake_tool()], system_prompt="   ")

    component.create_agent_runnable()

    assert captured.get("system_prompt") in (None, "")


def test_should_inject_enhanced_system_prompt_for_non_granite_watsonx_models(monkeypatch) -> None:
    """Bug: enhanced system prompt (TOOL USAGE GUIDELINES) was Granite-only,
    but the WatsonX platform tool-calling issues affect ALL WatsonX models
    (Llama, Mistral, etc.). The middleware that handles those issues already
    fires on `is_watsonx_model` — the system prompt enhancement must align.

    Acceptance: a non-granite, WatsonX-hosted model with 2+ tools must receive
    the TOOL USAGE GUIDELINES injection, matching the middleware's scope.
    """
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        # Return a stub graph — we only inspect captured kwargs. Calling the real
        # create_agent here would trigger ToolNode init, which rejects MagicMock
        # tools as "not a callable with __name__".
        return MagicMock()

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _ToolCapableFakeWatsonxModel(responses=[AIMessage(content="ok")]),
    )
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.create_agent",
        _capture_create_agent,
    )

    tools = [_fake_tool(name="calculator"), _fake_tool(name="fetch_url")]
    component = _component_with(
        model="fake-watsonx-llama",
        tools=tools,
        system_prompt="You are a helpful assistant.",
    )
    # `set()` wraps list args in MagicMock; assign directly so `len(tools) > 1`
    # is true inside `get_enhanced_system_prompt` (it short-circuits on len<=1).
    component.tools = tools

    component.create_agent_runnable()

    system_prompt = captured.get("system_prompt") or ""
    assert "TOOL USAGE GUIDELINES" in system_prompt, (
        f"Non-granite WatsonX models should receive TOOL USAGE GUIDELINES; "
        f"got system_prompt={system_prompt!r}"
    )


def test_should_return_compiled_state_graph_when_build_agent_called(monkeypatch) -> None:
    """Bug: LCToolsAgentComponent.build_agent() wraps the new CompiledStateGraph
    (returned by create_agent_runnable) in RunnableAgent + AgentExecutor with
    `input_keys_arg=["input"]`. The graph expects `{"messages": [...]}`, not
    `{"input": str}` — any flow consuming the "Agent" output port silently gets
    a key-mismatched executor.

    Expected: build_agent() returns the CompiledStateGraph directly (the same
    runnable that run_agent() consumes via astream_events).
    """
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _fake_chat_model(),
    )
    component = _component_with(model="fake-model", tools=[_fake_tool()])

    result = component.build_agent()

    assert isinstance(result, CompiledStateGraph)


def test_should_raise_not_implemented_when_model_does_not_support_tool_calling(monkeypatch) -> None:
    """Models that raise NotImplementedError on bind_tools should be re-raised with a helpful message."""

    class NoToolsModel:
        def bind_tools(self, *_args, **_kwargs):
            msg = "this fake model does not support tool calling"
            raise NotImplementedError(msg)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: NoToolsModel(),
    )
    component = _component_with(model="fake-model", tools=[_fake_tool()])

    with pytest.raises(NotImplementedError):
        component.create_agent_runnable()
