"""GH #13618 — component_code_search tool silently reports an empty library.

The ``ComponentLibrarySearch`` component behind ``LangflowAssistant.json``'s
component_code_search tool combined three defects into a confidently wrong
"the component library is empty" answer:

1. An unknown ``column`` returns an empty DataFrame instead of raising, so
   the agent cannot self-correct (the DataFrame has only ``file_path`` and
   ``text`` columns, but the model guesses ``name``/``code``).
2. The ``column`` tool arg never documents the valid column names.
3. ``number_candidates`` ships as 2, making enumeration questions
   unanswerable over a ~500-file index with no truncation signal.

These tests load the REAL code from the flow JSON (the same loader path
production uses) and pin the corrected behavior. The component sources the
installed component library itself, so there is no DataFrame to inject --
the search below runs against the real library.
"""

import json
from pathlib import Path

import pytest
from lfx.custom.eval import eval_custom_component_code

FLOW_PATH = Path(__file__).parents[4] / "base" / "langflow" / "agentic" / "flows" / "LangflowAssistant.json"

MIN_ENUMERATION_CANDIDATES = 10


def _keyword_search_template() -> dict:
    data = json.loads(FLOW_PATH.read_text(encoding="utf-8"))
    for node in data["data"]["nodes"]:
        node_data = node.get("data", {})
        if node_data.get("type") == "ComponentLibrarySearch":
            return node_data["node"]["template"]
    msg = "ComponentLibrarySearch node not found in LangflowAssistant.json"
    raise AssertionError(msg)


def _component_instance():
    component_class = eval_custom_component_code(_keyword_search_template()["code"]["value"])
    instance = component_class()
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


class TestMalformedToolCallsFailVisibly:
    """A malformed call must raise so the agent can self-correct, never return arbitrary rows.

    Each case below previously returned the *entire* library -- 158 rows of component source,
    uncapped -- which the agent reads as a result set. That is the confidently-wrong failure
    mode GH #13618 is about, and it also bypassed ``number_candidates`` straight into context.
    """

    def test_should_raise_when_keywords_are_empty(self):
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = []

        with pytest.raises(ValueError, match="at least one non-empty search term"):
            instance.search()

    def test_should_raise_when_keywords_are_only_whitespace(self):
        """A blank keyword strips to "" and ``str.contains("")`` matches every row."""
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = ["   "]

        with pytest.raises(ValueError, match="at least one non-empty search term"):
            instance.search()

    def test_should_accept_a_bare_string_as_a_single_keyword(self):
        """Models routinely send a string for a list argument; that is unambiguous, not an error."""
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = "ChatInput"

        result = instance.search()

        assert 0 < len(result) <= instance.number_candidates

    def test_should_raise_on_a_keywords_type_it_cannot_interpret(self):
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = {"not": "a list"}

        with pytest.raises(TypeError, match="must be a list of strings"):
            instance.search()


class TestOutputSchemaIsStable:
    @pytest.mark.parametrize("match_type", ["any", "all", "coverage"])
    def test_should_return_only_the_documented_columns(self, match_type):
        """``coverage`` -- the mode the shipped flow uses -- leaked its internal ``_score``."""
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = ["Component"]
        instance.match_type = match_type

        assert list(instance.search().columns) == ["file_path", "text"]

    def test_should_respect_the_candidate_cap(self):
        instance = _component_instance()
        instance.column = "text"
        instance.keywords = ["a"]
        instance.number_candidates = 3

        assert len(instance.search()) <= 3
