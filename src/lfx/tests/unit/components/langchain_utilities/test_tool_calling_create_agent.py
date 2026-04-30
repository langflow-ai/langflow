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


def _fake_chat_model() -> _ToolCapableFakeChatModel:
    return _ToolCapableFakeChatModel(responses=[AIMessage(content="fake answer")])


def _fake_tool():
    tool = MagicMock()
    tool.name = "calculator"
    tool.description = "Adds two numbers"
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
