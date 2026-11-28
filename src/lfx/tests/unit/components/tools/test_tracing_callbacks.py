"""Standalone tool outputs retain workflow callbacks on real LangChain tools."""

import asyncio
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from langchain_core.callbacks import AsyncCallbackManager, BaseCallbackHandler, CallbackManager
from lfx.base.tools.component_tool import ComponentStructuredTool
from lfx.components.tools.python_repl import PythonREPLToolComponent
from lfx.components.tools.search_api import SearchAPIComponent
from lfx.components.tools.serp_api import SerpAPIComponent
from lfx.components.tools.wikidata_api import WikidataAPIComponent, WikidataAPIWrapper
from lfx.services.model_provider_policy import (
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)
from pydantic import BaseModel


@pytest.fixture
def administrator_execution_context():
    """Bind an explicit administrator so the Python REPL tool runs under the admin-only default."""
    token = set_current_model_provider_policy_context(user_id="local-admin", attributes={"is_superuser": True})
    try:
        yield
    finally:
        reset_current_model_provider_policy_context(token)


class _RecordingCallback(BaseCallbackHandler):
    def __init__(self):
        self.tool_runs = []

    def on_tool_start(self, _serialized, _input, *, run_id, **_kwargs):
        self.tool_runs.append(run_id)


class _ScopedCallback(BaseCallbackHandler):
    def __init__(self):
        self.enters = 0
        self.exits = 0

    @contextmanager
    def langflow_invocation_scope(self):
        self.enters += 1
        try:
            yield
        finally:
            self.exits += 1


@pytest.mark.parametrize("manager_type", [CallbackManager, AsyncCallbackManager])
def test_component_tool_accepts_langchain_callback_manager(manager_type):
    """Tool execution receives either LangChain callback manager variant."""

    async def tool_output(query: str) -> str:
        return query

    class ToolArgs(BaseModel):
        query: str

    callback = _ScopedCallback()
    if manager_type is AsyncCallbackManager:
        tool = ComponentStructuredTool(
            name="fixture_tool",
            description="fixture",
            coroutine=tool_output,
            args_schema=ToolArgs,
        )
        manager = manager_type(handlers=[callback])
        result = asyncio.run(tool._arun(query="fixture", config={"callbacks": manager}))
    else:
        tool = ComponentStructuredTool(
            name="fixture_tool",
            description="fixture",
            func=lambda query: query,
            args_schema=ToolArgs,
        )
        manager = manager_type(handlers=[callback])
        result = tool._run(query="fixture", config={"callbacks": manager})

    assert result == ("fixture", None)
    assert (callback.enters, callback.exits) == (1, 1)


@pytest.mark.parametrize(
    "component_class",
    [PythonREPLToolComponent, SearchAPIComponent, SerpAPIComponent, WikidataAPIComponent],
)
@pytest.mark.usefixtures("administrator_execution_context")
def test_standalone_tool_output_keeps_workflow_callback(component_class, monkeypatch):
    callback = _RecordingCallback()
    monkeypatch.setattr(component_class, "get_langchain_callbacks", lambda _self: [callback])
    if component_class in {SearchAPIComponent, SerpAPIComponent}:
        wrapper = SimpleNamespace(results=lambda **_kwargs: {"organic_results": [{"snippet": "fixture result"}]})
        if component_class is SerpAPIComponent:
            wrapper.results = lambda *_args, **_kwargs: {"organic_results": [{"snippet": "fixture result"}]}
        monkeypatch.setattr(component_class, "_build_wrapper", lambda *_args, **_kwargs: wrapper)
    elif component_class is WikidataAPIComponent:
        monkeypatch.setattr(WikidataAPIWrapper, "results", lambda *_args: [{"label": "fixture result"}])

    component = component_class()
    if component_class is PythonREPLToolComponent:
        # Keep the real tool and callback path without the optional interpreter package.
        class _FakePythonREPL:
            def __init__(self, _globals=None):
                pass

            @staticmethod
            def sanitize_input(code):
                return code.strip()

            def run(self, _code):
                return "fixture result"

        utilities = SimpleNamespace(PythonREPL=_FakePythonREPL)
        monkeypatch.setitem(sys.modules, "langchain_experimental", SimpleNamespace(utilities=utilities))
        monkeypatch.setitem(sys.modules, "langchain_experimental.utilities", utilities)
        component.python_code = "print('fixture result')"
    elif component_class is WikidataAPIComponent:
        component.query = "fixture query"
    else:
        component.input_value = "fixture query"

    result = component.run_model()

    assert "fixture result" in str(result)
    assert len(callback.tool_runs) == 1
