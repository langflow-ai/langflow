"""Tests for the modern replacements of the legacy LangChain agent components.

The migrated trio (`SQLDatabaseAgentComponent`, `JSONDataAgentComponent`,
`OpenAPISpecAgentComponent`) uses `langchain.agents.create_agent` and returns a
`CompiledStateGraph`. The legacy `VectorStoreRouterAgentComponent` is kept as
legacy with no replacement (it relies on `VectorStoreInfo`, an input port that
no longer exists in current Langflow).

All four legacy components keep working at runtime via the `AgentExecutor`
fallback in `_build_graph_input` (see `test_legacy_agent_executor_fallback.py`).

Each component test verifies:
- `build_agent()` produces a `CompiledStateGraph`
- The toolkit's tools reach `create_agent`
- The legacy prompt prefix is passed as `system_prompt`
- `max_iterations` and `handle_parsing_errors` map to LangGraph middleware
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# All components exercised here (`sql_database_agent`, `json_data_agent`,
# `openapi_spec_agent`) depend on `langchain_community`, which lives in lfx's
# `integration` dep group — not installed by `uv sync --dev` in unit-test envs.
pytest.importorskip("langchain_community")

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph


class _ToolCapableFakeChatModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel that pretends to support bind_tools (no-op)."""

    def bind_tools(self, tools, **_kwargs):  # type: ignore[override]
        self._bound_tools = tools
        return self


def _fake_chat_model() -> _ToolCapableFakeChatModel:
    return _ToolCapableFakeChatModel(responses=[AIMessage(content="ok")])


# ============================================================================
# SQLDatabaseAgentComponent
# ============================================================================


def _sql_component(monkeypatch, **overrides):
    from lfx.components.langchain_utilities.sql_database_agent import SQLDatabaseAgentComponent

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.sql_database_agent.get_llm",
        lambda **_: _fake_chat_model(),
    )
    component = SQLDatabaseAgentComponent()
    component._user_id = None
    defaults = {
        "model": "fake-model",
        "api_key": None,
        "database_uri": "sqlite:///:memory:",
        "extra_tools": [],
        "handle_parsing_errors": True,
        "verbose": False,
        "max_iterations": 15,
    }
    defaults.update(overrides)
    component.set_attributes(defaults)
    return component


def test_sql_should_return_compiled_state_graph(monkeypatch) -> None:
    component = _sql_component(monkeypatch)

    runnable = component.build_agent()

    assert isinstance(runnable, CompiledStateGraph)


def test_sql_should_pass_sql_prefix_with_dialect_filled(monkeypatch) -> None:
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.sql_database_agent.create_agent",
        _capture_create_agent,
    )
    component = _sql_component(monkeypatch)

    component.build_agent()

    system_prompt = captured.get("system_prompt") or ""
    assert "SQL database" in system_prompt
    assert "{dialect}" not in system_prompt
    assert "{top_k}" not in system_prompt


def test_sql_should_pass_toolkit_tools_to_create_agent(monkeypatch) -> None:
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.sql_database_agent.create_agent",
        _capture_create_agent,
    )
    component = _sql_component(monkeypatch)

    component.build_agent()

    tool_names = {getattr(t, "name", "") for t in (captured.get("tools") or [])}
    assert {"sql_db_query", "sql_db_schema", "sql_db_list_tables", "sql_db_query_checker"} <= tool_names


def test_sql_should_append_extra_tools(monkeypatch) -> None:
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.sql_database_agent.create_agent",
        _capture_create_agent,
    )
    extra_tool = MagicMock()
    extra_tool.name = "extra_tool"
    component = _sql_component(monkeypatch, extra_tools=[extra_tool])

    component.build_agent()

    names = [getattr(t, "name", "") for t in (captured.get("tools") or [])]
    assert "extra_tool" in names


def test_sql_should_wire_max_iterations_middleware(monkeypatch) -> None:
    from langchain.agents.middleware import ModelCallLimitMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.sql_database_agent.create_agent",
        _capture_create_agent,
    )
    component = _sql_component(monkeypatch, max_iterations=7)

    component.build_agent()

    middleware = captured.get("middleware") or []
    limiters = [m for m in middleware if isinstance(m, ModelCallLimitMiddleware)]
    assert limiters
    assert limiters[0].run_limit == 7


def test_sql_should_wire_tool_retry_when_handle_parsing_errors(monkeypatch) -> None:
    from langchain.agents.middleware import ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.sql_database_agent.create_agent",
        _capture_create_agent,
    )
    component = _sql_component(monkeypatch, handle_parsing_errors=True)

    component.build_agent()

    middleware = captured.get("middleware") or []
    assert any(isinstance(m, ToolRetryMiddleware) for m in middleware)


# ============================================================================
# JSONDataAgentComponent
# ============================================================================


@pytest.fixture
def json_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"users": [{"name": "Alice"}]}')
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


def _json_component(json_path: str, **overrides):
    from lfx.components.langchain_utilities.json_data_agent import JSONDataAgentComponent

    component = JSONDataAgentComponent()
    component._user_id = None
    defaults = {
        "llm": _fake_chat_model(),
        "path": json_path,
        "handle_parsing_errors": True,
        "verbose": False,
        "max_iterations": 15,
    }
    defaults.update(overrides)
    component.set_attributes(defaults)
    return component


def test_json_should_return_compiled_state_graph(json_file) -> None:
    component = _json_component(json_file)

    with patch("lfx.components.langchain_utilities.json_data_agent.get_settings_service") as mock_settings:
        mock_settings.return_value.settings.storage_type = "local"
        runnable = component.build_agent()

    assert isinstance(runnable, CompiledStateGraph)


def test_json_should_pass_json_prefix_as_system_prompt(json_file, monkeypatch) -> None:
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.json_data_agent.create_agent",
        _capture_create_agent,
    )
    component = _json_component(json_file)

    with patch("lfx.components.langchain_utilities.json_data_agent.get_settings_service") as mock_settings:
        mock_settings.return_value.settings.storage_type = "local"
        component.build_agent()

    system_prompt = captured.get("system_prompt") or ""
    assert "JSON" in system_prompt or "json" in system_prompt


def test_json_should_pass_toolkit_tools_to_create_agent(json_file, monkeypatch) -> None:
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.json_data_agent.create_agent",
        _capture_create_agent,
    )
    component = _json_component(json_file)

    with patch("lfx.components.langchain_utilities.json_data_agent.get_settings_service") as mock_settings:
        mock_settings.return_value.settings.storage_type = "local"
        component.build_agent()

    names = {getattr(t, "name", "") for t in (captured.get("tools") or [])}
    assert {"json_spec_list_keys", "json_spec_get_value"} <= names


# ============================================================================
# OpenAPISpecAgentComponent
# ============================================================================


@pytest.fixture
def openapi_yaml_file():
    spec = """
openapi: 3.0.0
info:
  title: Test
  version: 1.0.0
servers:
  - url: https://api.example.com
paths:
  /ping:
    get:
      summary: Ping
      responses:
        '200':
          description: OK
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(spec)
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


def _openapi_component(monkeypatch, openapi_path: str, **overrides):
    from lfx.components.langchain_utilities.openapi_spec_agent import OpenAPISpecAgentComponent

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.openapi_spec_agent.get_llm",
        lambda **_: _fake_chat_model(),
    )
    component = OpenAPISpecAgentComponent()
    component._user_id = None
    defaults = {
        "model": "fake-model",
        "api_key": None,
        "path": openapi_path,
        # Required by OpenAPIToolkit.from_llm before create_agent is reached.
        "allow_dangerous_requests": True,
        "handle_parsing_errors": True,
        "verbose": False,
        "max_iterations": 15,
    }
    defaults.update(overrides)
    component.set_attributes(defaults)
    return component


def test_openapi_should_pass_openapi_prefix_as_system_prompt(monkeypatch, openapi_yaml_file) -> None:
    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.openapi_spec_agent.create_agent",
        _capture_create_agent,
    )
    component = _openapi_component(monkeypatch, openapi_yaml_file)

    component.build_agent()

    system_prompt = captured.get("system_prompt") or ""
    assert "openapi" in system_prompt.lower() or "API" in system_prompt


def test_openapi_should_wire_middleware(monkeypatch, openapi_yaml_file) -> None:
    from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware

    captured: dict = {}

    def _capture_create_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock(spec=CompiledStateGraph)

    monkeypatch.setattr(
        "lfx.components.langchain_utilities.openapi_spec_agent.create_agent",
        _capture_create_agent,
    )
    component = _openapi_component(monkeypatch, openapi_yaml_file, max_iterations=5, handle_parsing_errors=True)

    component.build_agent()

    middleware = captured.get("middleware") or []
    limiters = [m for m in middleware if isinstance(m, ModelCallLimitMiddleware)]
    retries = [m for m in middleware if isinstance(m, ToolRetryMiddleware)]
    assert limiters
    assert limiters[0].run_limit == 5
    assert retries


# NOTE: VectorStoreRouterAgentComponent has no modern replacement — kept as legacy.
# Its runtime behavior is covered by the AgentExecutor fallback in
# `test_legacy_agent_executor_fallback.py`.
