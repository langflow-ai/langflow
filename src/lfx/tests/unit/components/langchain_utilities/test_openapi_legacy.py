"""Regression tests for the legacy `OpenAPIAgentComponent`.

Bugs covered here:

1. `Path.suffix` comparison bug: legacy code checked `{"yaml", "yml"}` but
   `Path.suffix` returns `".yaml"` / `".yml"` (with the dot). YAML files were
   routed to `JsonSpec.from_file`, raising `JSONDecodeError`.
2. Nested `json_explorer` executor parsing-error handling: `OpenAPIToolkit`
   builds an inner `AgentExecutor` (the `json_explorer` tool). The legacy code
   set `handle_parsing_errors=True` only on the OUTER executor — the inner one
   was left at `False`, so any LLM whose output diverges from the ReAct format
   (very common with gpt-4o) crashed the flow.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_classic.agents import AgentExecutor
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.components.langchain_utilities.openapi import OpenAPIAgentComponent


def test_should_load_yaml_spec_via_yaml_branch_when_path_has_yaml_suffix(tmp_path):
    """Route YAML specs through the YAML branch (not JsonSpec.from_file).

    `Path.suffix` returns `.yaml` (with the dot), so the suffix check must be
    `{".yaml", ".yml"}`. Previously it was `{"yaml", "yml"}` and YAML files were
    routed to `JsonSpec.from_file`, which raised JSONDecodeError on the first
    line of the YAML document.
    """
    yaml_file = tmp_path / "petstore.yaml"
    yaml_file.write_text(
        "openapi: 3.0.0\n"
        "info:\n"
        "  title: Test\n"
        "  version: 1.0.0\n"
        "servers:\n"
        "  - url: https://api.example.com\n"
        "paths:\n"
        "  /ping:\n"
        "    get:\n"
        "      summary: Ping\n"
        "      responses:\n"
        "        '200':\n"
        "          description: OK\n",
        encoding="utf-8",
    )

    component = OpenAPIAgentComponent()
    component._user_id = None
    # Bypass model resolution; we only care about the file-routing branch.
    with patch.object(OpenAPIAgentComponent, "_get_llm", return_value=MagicMock()):
        component.set_attributes(
            {
                "model": "fake",
                "api_key": None,
                "path": str(yaml_file),
                "allow_dangerous_requests": True,
                "verbose": False,
                "handle_parsing_errors": True,
                "max_iterations": 5,
            }
        )
        try:
            component.build_agent()
        except Exception as e:
            # Anything related to JSON parsing means the YAML branch was bypassed
            # and the file was sent to JsonSpec.from_file — that's the bug.
            msg = str(e).lower()
            if "expecting value" in msg or "jsondecodeerror" in msg:
                pytest.fail(f"Legacy YAML suffix bug regressed (file routed to JSON parser): {e}")
            # Other failures (e.g. toolkit construction with a MagicMock LLM) are not
            # part of this regression check.


def test_should_propagate_handle_parsing_errors_to_nested_json_explorer_executor(tmp_path):
    """Nested `json_explorer` AgentExecutor must inherit `handle_parsing_errors`.

    `OpenAPIToolkit` constructs an internal `create_json_agent` and exposes its
    AgentExecutor as the `json_explorer` tool. If `handle_parsing_errors` is
    not passed through, that nested executor stays at the default `False` and
    the flow crashes whenever the LLM produces non-ReAct output (which is
    common with gpt-4o):

        ValueError: An output parsing error occurred. In order to pass this
        error back to the agent and have it try again, pass
        `handle_parsing_errors=True` to the AgentExecutor. ...

    The component sets `handle_parsing_errors=True` on the outer executor; we
    must propagate it to the nested one too.
    """
    yaml_file = tmp_path / "spec.yaml"
    yaml_file.write_text(
        "openapi: 3.0.0\n"
        "info: {title: T, version: 1}\n"
        "servers: [{url: https://x}]\n"
        "paths:\n"
        "  /pet:\n"
        "    get: {summary: Get pets, responses: {'200': {description: OK}}}\n",
        encoding="utf-8",
    )
    llm = FakeListChatModel(responses=["dummy"])
    component = OpenAPIAgentComponent()
    component._user_id = None
    with patch.object(OpenAPIAgentComponent, "_get_llm", return_value=llm):
        component.set_attributes(
            {
                "model": "fake",
                "api_key": None,
                "path": str(yaml_file),
                "allow_dangerous_requests": True,
                "verbose": False,
                "handle_parsing_errors": True,
                "max_iterations": 5,
            }
        )
        executor = component.build_agent()

    nested_executors = []
    for t in executor.tools:
        func = getattr(t, "func", None)
        owner = getattr(func, "__self__", None)
        if isinstance(owner, AgentExecutor):
            nested_executors.append(owner)
    assert nested_executors, "expected at least one nested AgentExecutor inside OpenAPIToolkit"
    for nested in nested_executors:
        assert nested.handle_parsing_errors is True, (
            f"nested executor must inherit handle_parsing_errors=True, got {nested.handle_parsing_errors!r}"
        )
