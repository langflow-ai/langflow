"""Tests for compact flow validation against the live registry.

Uses a minimal stub for all_types_dict so no real Langflow server is needed.
"""

from __future__ import annotations

import pytest
from langflow.agentic.helpers.flow_validation import FlowValidationResult, validate_compact_flow

# ---------------------------------------------------------------------------
# Minimal all_types_dict stub
# ---------------------------------------------------------------------------

_STUB_TEMPLATE = {
    "ChatInput": {
        "display_name": "Chat Input",
        "outputs": [{"name": "message", "types": ["Message"]}],
        "template": {
            "input_value": {"type": "str", "input_types": ["str"]},
        },
    },
    "OpenAIModel": {
        "display_name": "OpenAI",
        "outputs": [{"name": "text_output", "types": ["Message"]}],
        "template": {
            "input_value": {"type": "str", "input_types": ["Message", "str"]},
            "model_name": {"type": "str", "input_types": ["str"]},
        },
    },
    "ChatOutput": {
        "display_name": "Chat Output",
        "outputs": [],
        "template": {
            "input_value": {"type": "str", "input_types": ["Message", "str"]},
        },
    },
}

ALL_TYPES_DICT = {
    "Inputs": {"ChatInput": _STUB_TEMPLATE["ChatInput"]},
    "Models": {"OpenAIModel": _STUB_TEMPLATE["OpenAIModel"]},
    "Outputs": {"ChatOutput": _STUB_TEMPLATE["ChatOutput"]},
}

VALID_COMPACT = {
    "nodes": [
        {"id": "n1", "type": "ChatInput"},
        {"id": "n2", "type": "OpenAIModel"},
        {"id": "n3", "type": "ChatOutput"},
    ],
    "edges": [
        {"source": "n1", "source_output": "message", "target": "n2", "target_input": "input_value"},
        {"source": "n2", "source_output": "text_output", "target": "n3", "target_input": "input_value"},
    ],
}


class TestValidateCompactFlow:
    """Tests for the async validate_compact_flow function."""

    @pytest.mark.asyncio
    async def test_valid_flow_passes(self):
        result = await validate_compact_flow(VALID_COMPACT, all_types_dict=ALL_TYPES_DICT)
        assert isinstance(result, FlowValidationResult)
        assert result.is_valid
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_unknown_component_type_fails(self):
        bad = {
            "nodes": [{"id": "n1", "type": "NonExistentComponent"}],
            "edges": [],
        }
        result = await validate_compact_flow(bad, all_types_dict=ALL_TYPES_DICT)
        assert not result.is_valid
        assert any("NonExistentComponent" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_duplicate_node_ids_fail(self):
        bad = {
            "nodes": [
                {"id": "n1", "type": "ChatInput"},
                {"id": "n1", "type": "ChatOutput"},
            ],
            "edges": [],
        }
        result = await validate_compact_flow(bad, all_types_dict=ALL_TYPES_DICT)
        assert not result.is_valid
        assert any("duplicate" in e.lower() or "n1" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_edge_referencing_missing_node_fails(self):
        bad = {
            "nodes": [{"id": "n1", "type": "ChatInput"}],
            "edges": [
                {
                    "source": "n1",
                    "source_output": "message",
                    "target": "ghost",
                    "target_input": "input_value",
                }
            ],
        }
        result = await validate_compact_flow(bad, all_types_dict=ALL_TYPES_DICT)
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_empty_nodes_list_fails(self):
        result = await validate_compact_flow({"nodes": [], "edges": []}, all_types_dict=ALL_TYPES_DICT)
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_invalid_output_name_fails_or_warns(self):
        """Invalid source_output should produce an error or warning."""
        bad = {
            "nodes": [
                {"id": "n1", "type": "ChatInput"},
                {"id": "n2", "type": "ChatOutput"},
            ],
            "edges": [
                {
                    "source": "n1",
                    "source_output": "nonexistent_output",
                    "target": "n2",
                    "target_input": "input_value",
                }
            ],
        }
        result = await validate_compact_flow(bad, all_types_dict=ALL_TYPES_DICT)
        # May be an error or warning — either signals the problem
        has_feedback = not result.is_valid or len(result.warnings) > 0
        assert has_feedback

    @pytest.mark.asyncio
    async def test_missing_nodes_key_fails(self):
        result = await validate_compact_flow({"edges": []}, all_types_dict=ALL_TYPES_DICT)
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_result_contains_compact_data_on_success(self):
        result = await validate_compact_flow(VALID_COMPACT, all_types_dict=ALL_TYPES_DICT)
        assert result.compact_data is not None
        assert "nodes" in result.compact_data
