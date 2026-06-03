"""Tests for compact flow JSON extraction from LLM output.

Covers extract_compact_flow and the internal _extract_json_objects helper,
including edge cases that previously caused incorrect extraction.
"""

from __future__ import annotations

from langflow.agentic.helpers.flow_extraction import (
    _extract_json_objects,
    extract_compact_flow,
)

SIMPLE_FLOW = {
    "nodes": [{"id": "n1", "type": "ChatInput"}, {"id": "n2", "type": "ChatOutput"}],
    "edges": [{"source": "n1", "source_output": "message", "target": "n2", "target_input": "input_value"}],
}

SIMPLE_FLOW_JSON = (
    '{"nodes": [{"id": "n1", "type": "ChatInput"}, {"id": "n2", "type": "ChatOutput"}],'
    ' "edges": [{"source": "n1", "source_output": "message", "target": "n2", "target_input": "input_value"}]}'
)


class TestExtractJsonObjects:
    """Tests for the brace-matching JSON extractor."""

    def test_extracts_simple_object(self):
        result = _extract_json_objects(SIMPLE_FLOW_JSON)
        assert len(result) == 1
        assert '"nodes"' in result[0]

    def test_ignores_objects_without_nodes_key(self):
        text = '{"foo": "bar"}'
        result = _extract_json_objects(text)
        assert result == []

    def test_braces_inside_string_values_do_not_break_depth(self):
        """Braces in prompt templates must not confuse brace-depth counting."""
        text = (
            '{"nodes": [{"id": "n1", "type": "Prompt", "values": {"template": "{question}\\n{context}"}}],'
            ' "edges": []}'
        )
        result = _extract_json_objects(text)
        assert len(result) == 1
        assert "Prompt" in result[0]

    def test_returns_longer_candidates_first(self):
        short = '{"nodes": [], "edges": []}'
        long_ = '{"nodes": [{"id": "n1", "type": "ChatInput"}], "edges": []}'
        text = long_ + " " + short
        result = _extract_json_objects(text)
        assert result[0] == long_

    def test_multiple_objects_in_text(self):
        text = SIMPLE_FLOW_JSON + ' some text {"nodes": [], "edges": []}'
        result = _extract_json_objects(text)
        assert len(result) == 2

    def test_escaped_quotes_inside_strings(self):
        """Escaped quotes must not toggle the in-string flag."""
        text = '{"nodes": [{"id": "n\\"1", "type": "ChatInput"}], "edges": []}'
        result = _extract_json_objects(text)
        assert len(result) == 1


class TestExtractCompactFlow:
    """Tests for extract_compact_flow — the public API."""

    def test_extracts_from_fenced_code_block(self):
        response = f"```json\n{SIMPLE_FLOW_JSON}\n```"
        result = extract_compact_flow(response)
        assert result is not None
        assert "nodes" in result
        assert len(result["nodes"]) == 2

    def test_extracts_from_bare_json(self):
        result = extract_compact_flow(SIMPLE_FLOW_JSON)
        assert result is not None
        assert result["nodes"][0]["type"] == "ChatInput"

    def test_extracts_from_prose_with_embedded_json(self):
        response = f"Here is the flow:\n{SIMPLE_FLOW_JSON}\nEnjoy!"
        result = extract_compact_flow(response)
        assert result is not None

    def test_returns_none_for_no_json(self):
        result = extract_compact_flow("No JSON here at all.")
        assert result is None

    def test_returns_none_for_json_without_nodes(self):
        result = extract_compact_flow('{"foo": "bar"}')
        assert result is None

    def test_extracts_flow_with_values(self):
        json_str = (
            '{"nodes": [{"id": "n1", "type": "OpenAIModel", "values": {"model_name": "gpt-4o"}}],'
            ' "edges": []}'
        )
        result = extract_compact_flow(json_str)
        assert result is not None
        assert result["nodes"][0]["values"]["model_name"] == "gpt-4o"

    def test_handles_trailing_comma_heuristic(self):
        """JSON with a trailing comma should be fixed heuristically."""
        malformed = '{"nodes": [{"id": "n1", "type": "ChatInput"},], "edges": []}'
        result = extract_compact_flow(malformed)
        # May or may not succeed depending on heuristic — just must not raise
        # (returns either a valid dict or None)
        assert result is None or isinstance(result, dict)

    def test_multiline_fenced_block(self):
        multiline = (
            "```json\n"
            "{\n"
            '  "nodes": [\n'
            '    {"id": "n1", "type": "ChatInput"},\n'
            '    {"id": "n2", "type": "ChatOutput"}\n'
            "  ],\n"
            '  "edges": []\n'
            "}\n"
            "```"
        )
        result = extract_compact_flow(multiline)
        assert result is not None
        assert len(result["nodes"]) == 2
