"""Tests that ToolCallingAgentComponent wires LangChain middleware for legacy params.

Slices S14-S16 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.

- S14: max_iterations → ModelCallLimitMiddleware(run_limit=max_iterations).
- S15: handle_parsing_errors → ToolRetryMiddleware (best-effort equivalence).
- S16: verbose is no longer mapped to a debug flag (create_agent has no `debug=True` kwarg);
       drop silently to keep parity with the public API.
"""

from unittest.mock import MagicMock

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent


class _ToolCapableFakeChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **_kwargs):  # type: ignore[override]
        self._bound_tools = tools
        return self


def _fake_tool():
    tool = MagicMock()
    tool.name = "calc"
    return tool


def _component_with(monkeypatch, **kwargs) -> ToolCallingAgentComponent:
    monkeypatch.setattr(
        "lfx.components.langchain_utilities.tool_calling.get_llm",
        lambda **_: _ToolCapableFakeChatModel(responses=[AIMessage(content="ok")]),
    )
    component = ToolCallingAgentComponent()
    component._user_id = None
    component.cache = {}
    component.set(
        model="fake",
        tools=kwargs.get("tools", [_fake_tool()]),
        system_prompt="hi",
        chat_history=[],
        handle_parsing_errors=kwargs.get("handle_parsing_errors", False),
        verbose=kwargs.get("verbose", False),
        max_iterations=kwargs.get("max_iterations"),
        api_key=None,
    )
    return component


def _capture_create_agent(monkeypatch) -> dict:
    captured: dict = {}

    def _impl(**kwargs):
        captured.update(kwargs)
        from langchain.agents import create_agent

        return create_agent(model=kwargs["model"], tools=kwargs.get("tools") or [])

    monkeypatch.setattr("lfx.components.langchain_utilities.tool_calling.create_agent", _impl)
    return captured


def test_should_wire_model_call_limit_middleware_when_max_iterations_set(monkeypatch) -> None:
    captured = _capture_create_agent(monkeypatch)
    component = _component_with(monkeypatch, max_iterations=7)

    component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert any(isinstance(m, ModelCallLimitMiddleware) for m in middleware)


def test_should_set_run_limit_to_max_iterations_value(monkeypatch) -> None:
    captured = _capture_create_agent(monkeypatch)
    component = _component_with(monkeypatch, max_iterations=11)

    component.create_agent_runnable()

    limits = [m for m in captured["middleware"] if isinstance(m, ModelCallLimitMiddleware)]
    assert limits, "ModelCallLimitMiddleware must be wired"
    assert limits[0].run_limit == 11


def test_should_omit_model_call_limit_middleware_when_max_iterations_is_none(monkeypatch) -> None:
    captured = _capture_create_agent(monkeypatch)
    component = _component_with(monkeypatch, max_iterations=None)

    component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert not any(isinstance(m, ModelCallLimitMiddleware) for m in middleware)


def test_should_wire_tool_retry_middleware_when_handle_parsing_errors_true(monkeypatch) -> None:
    captured = _capture_create_agent(monkeypatch)
    component = _component_with(monkeypatch, handle_parsing_errors=True)

    component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert any(isinstance(m, ToolRetryMiddleware) for m in middleware)


def test_should_omit_tool_retry_middleware_when_handle_parsing_errors_false(monkeypatch) -> None:
    captured = _capture_create_agent(monkeypatch)
    component = _component_with(monkeypatch, handle_parsing_errors=False)

    component.create_agent_runnable()

    middleware = captured.get("middleware") or []
    assert not any(isinstance(m, ToolRetryMiddleware) for m in middleware)
