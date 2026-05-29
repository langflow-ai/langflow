"""Tests for flow JSON extraction from markdown responses."""

import json

from langflow.agentic.helpers.code_extraction import extract_flow_json


class TestExtractFlowJson:
    def test_extracts_flow_json_block(self):
        flow_data = {"name": "Test", "data": {"nodes": [], "edges": []}}
        text = f"Here's the flow:\n\n```flow_json\n{json.dumps(flow_data)}\n```\n\nDone!"
        result = extract_flow_json(text)
        assert result == flow_data

    def test_returns_none_when_no_flow_block(self):
        text = "Just a regular response with no flow data."
        assert extract_flow_json(text) is None

    def test_returns_none_for_invalid_json(self):
        text = "```flow_json\n{invalid json}\n```"
        assert extract_flow_json(text) is None

    def test_returns_none_for_python_code_block(self):
        text = "```python\nclass MyComponent(Component): pass\n```"
        assert extract_flow_json(text) is None

    def test_extracts_from_mixed_content(self):
        flow_data = {"name": "RAG", "data": {"nodes": [{"id": "1"}], "edges": []}}
        text = (
            "I built a RAG pipeline for you.\n\n"
            "```python\nprint('hello')\n```\n\n"
            f"```flow_json\n{json.dumps(flow_data)}\n```\n\n"
            "Let me know if you need changes."
        )
        result = extract_flow_json(text)
        assert result == flow_data

    def test_handles_pretty_printed_json(self):
        flow_data = {"name": "Test", "data": {"nodes": [], "edges": []}}
        pretty = json.dumps(flow_data, indent=2)
        text = f"```flow_json\n{pretty}\n```"
        result = extract_flow_json(text)
        assert result == flow_data

    def test_case_insensitive(self):
        flow_data = {"name": "Test"}
        text = f"```FLOW_JSON\n{json.dumps(flow_data)}\n```"
        result = extract_flow_json(text)
        assert result == flow_data
