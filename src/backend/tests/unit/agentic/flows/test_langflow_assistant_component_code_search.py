"""Regression guards for the bundled LangflowAssistant component-code search tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

LANGFLOW_ASSISTANT_JSON = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "base"
    / "langflow"
    / "agentic"
    / "flows"
    / "LangflowAssistant.json"
)


@pytest.fixture(scope="module")
def component_code_search_template() -> dict:
    flow = json.loads(LANGFLOW_ASSISTANT_JSON.read_text(encoding="utf-8"))
    for node in flow["data"]["nodes"]:
        node_data = node.get("data", {})
        if node_data.get("type") == "DataFrameKeywordSearch":
            return node_data["node"]["template"]
    msg = "DataFrameKeywordSearch node not found in LangflowAssistant.json"
    raise AssertionError(msg)


def test_component_code_search_does_not_expose_column_to_model(component_code_search_template: dict):
    column = component_code_search_template["column"]
    assert column["value"] == "text"
    assert column["tool_mode"] is False

    tool = component_code_search_template["tools_metadata"]["value"][0]
    assert tool["name"] == "component_code_search"
    assert set(tool["args"]) == {"keywords"}


def test_component_code_search_fails_loudly_for_unknown_columns(component_code_search_template: dict):
    code = component_code_search_template["code"]["value"]
    assert "BoolInput, IntInput, Output" in code
    assert "IntInput(" in code
    assert "raise ValueError" in code
    assert "Unknown column" in code
    assert "Valid columns" in code
