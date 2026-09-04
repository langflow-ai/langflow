"""GH #13618 — component_code_search tool silently reports an empty library.

The inline ``DataFrameKeywordSearch`` component in ``LangflowAssistant.json``
combines three defects into a confidently wrong "the component library is
empty" answer:

1. An unknown ``column`` returns an empty DataFrame instead of raising, so
   the agent cannot self-correct (the DataFrame has only ``file_path`` and
   ``text`` columns, but the model guesses ``name``/``code``).
2. The ``column`` tool arg never documents the valid column names.
3. ``number_candidates`` ships as 2, making enumeration questions
   unanswerable over a ~500-file index with no truncation signal.

These tests load the REAL inline code from the flow JSON (the same loader
path production uses) and pin the corrected behavior.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
from langflow.schema import DataFrame
from lfx.custom.eval import eval_custom_component_code

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"

MIN_ENUMERATION_CANDIDATES = 10


def _keyword_search_template() -> dict:
    data = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    for node in data["data"]["nodes"]:
        node_data = node.get("data", {})
        if node_data.get("type") == "DataFrameKeywordSearch":
            return node_data["node"]["template"]
    msg = "DataFrameKeywordSearch node not found in LangflowAssistant.json"
    raise AssertionError(msg)


def _component_instance():
    component_class = eval_custom_component_code(_keyword_search_template()["code"]["value"])
    instance = component_class()
    instance.dataframe = DataFrame(
        pd.DataFrame(
            [
                {"file_path": "openai.py", "text": "class OpenAIModel(Component): build()..."},
                {"file_path": "chat_input.py", "text": "class ChatInput(Component): build()..."},
                {"file_path": "agent.py", "text": "class Agent(Component): tools..."},
            ]
        )
    )
    instance.match_type = "any"
    instance.case_sensitive = False
    instance.number_candidates = 10
    return instance


class TestInvalidColumnHandling:
    @pytest.mark.parametrize("invalid_column", ["name", "code"])
    def test_should_raise_value_error_when_column_does_not_exist(self, invalid_column):
        instance = _component_instance()
        instance.column = invalid_column
        instance.keywords = ["component"]

        with pytest.raises(ValueError, match="file_path") as exc_info:
            instance.search()

        assert invalid_column in str(exc_info.value)

    def test_should_return_matches_when_searching_valid_text_column(self):
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = ["class", "Component"]

        result = instance.search()

        assert len(result) > 0


class TestToolArgDocumentation:
    def test_should_document_valid_columns_in_column_tool_arg_info(self):
        template = _keyword_search_template()
        info = template["column"]["info"]

        assert "file_path" in info, f"Tool arg info must name the valid columns, got: {info!r}"
        assert "text" in info, f"Tool arg info must name the valid columns, got: {info!r}"


class TestEnumerationCandidateCap:
    def test_should_ship_an_enumeration_friendly_candidate_cap(self):
        template = _keyword_search_template()
        configured = template["number_candidates"]["value"]

        assert configured >= MIN_ENUMERATION_CANDIDATES, (
            f"number_candidates={configured} cannot answer enumeration questions over ~500 indexed files"
        )
