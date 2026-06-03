"""Tests for flow graph visualization utilities.

Tests get_flow_graph_representations, get_flow_ascii_graph,
get_flow_text_repr, get_flow_graph_summary, and _build_text_repr_from_raw.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from langflow.agentic.utils.flow_graph import (
    _build_text_repr_from_raw,
    get_flow_ascii_graph,
    get_flow_graph_representations,
    get_flow_graph_summary,
    get_flow_text_repr,
)

MODULE = "langflow.agentic.utils.flow_graph"

FLOW_ID = str(uuid4())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLOW_DATA_WITH_NODES = {
    "nodes": [
        {"id": "n1", "data": {"type": "ChatInput", "node": {"display_name": "Chat Input"}}},
        {"id": "n2", "data": {"type": "OpenAIModel", "node": {"display_name": "OpenAI"}}},
    ],
    "edges": [
        {
            "source": "n1",
            "target": "n2",
            "data": {
                "sourceHandle": {"name": "message"},
                "targetHandle": {"fieldName": "input_value"},
            },
        }
    ],
}


def _make_flow(*, has_data=True, data=None, name="TestFlow"):
    return SimpleNamespace(
        id=UUID(FLOW_ID),
        name=name,
        tags=["test"],
        description="A test flow",
        data=(data if data is not None else (_FLOW_DATA_WITH_NODES if has_data else None)),
    )


# ---------------------------------------------------------------------------
# _build_text_repr_from_raw
# ---------------------------------------------------------------------------


class TestBuildTextReprFromRaw:
    def test_empty_returns_zero_counts(self):
        _, v, e = _build_text_repr_from_raw({"nodes": [], "edges": []}, "Flow")
        assert v == 0
        assert e == 0

    def test_nodes_listed_with_display_name(self):
        text, v, e = _build_text_repr_from_raw(_FLOW_DATA_WITH_NODES, "Flow")
        assert "Chat Input" in text
        assert "OpenAI" in text
        assert v == 2
        assert e == 1

    def test_edge_ports_shown(self):
        text, _, _ = _build_text_repr_from_raw(_FLOW_DATA_WITH_NODES, "Flow")
        assert "Chat Input.message" in text
        assert "OpenAI.input_value" in text

    def test_none_nodes_and_edges_handled_safely(self):
        """flow_data with None values must not raise TypeError."""
        _, v, e = _build_text_repr_from_raw({"nodes": None, "edges": None}, "Flow")
        assert v == 0
        assert e == 0

    def test_falls_back_to_type_when_no_display_name(self):
        data = {"nodes": [{"id": "n1", "data": {"type": "Milvus"}}], "edges": []}
        text, v, _ = _build_text_repr_from_raw(data, "Flow")
        assert "Milvus" in text
        assert v == 1

    def test_encoded_string_handles_dont_crash(self):
        """Edges with œ-encoded string sourceHandle must not raise."""
        data = {
            "nodes": [
                {"id": "n1", "data": {"type": "A", "node": {"display_name": "A"}}},
                {"id": "n2", "data": {"type": "B", "node": {"display_name": "B"}}},
            ],
            "edges": [
                {
                    "source": "n1",
                    "target": "n2",
                    "sourceHandle": "œdataTypeœ:œAœ",
                    "targetHandle": "œfieldNameœ:œinput_valueœ",
                    "data": {},  # no nested dicts
                }
            ],
        }
        text, _, edge_count = _build_text_repr_from_raw(data, "Flow")
        assert edge_count == 1
        assert "A" in text


# ---------------------------------------------------------------------------
# get_flow_graph_representations
# ---------------------------------------------------------------------------


class TestGetFlowGraphRepresentations:
    @pytest.mark.asyncio
    async def test_returns_all_fields_for_valid_flow(self):
        flow = _make_flow()
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow):
            result = await get_flow_graph_representations(FLOW_ID)

        assert result["flow_id"] == FLOW_ID
        assert result["flow_name"] == "TestFlow"
        assert result["vertex_count"] == 2
        assert result["edge_count"] == 1
        assert "text_repr" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_flow(self):
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None):
            result = await get_flow_graph_representations("nonexistent")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_for_flow_without_data(self):
        flow = _make_flow(has_data=False)
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow):
            result = await get_flow_graph_representations(FLOW_ID)

        assert "error" in result
        assert "no data" in result["error"]

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        with patch(
            f"{MODULE}.get_flow_by_id_or_endpoint_name",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB error"),
        ):
            result = await get_flow_graph_representations(FLOW_ID)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_encodes_edge_handles_in_raw_data(self):
        """Flow with œ-encoded handles must parse without error."""
        data_with_encoded = {
            "nodes": [
                {"id": "n1", "data": {"type": "Milvus", "node": {"display_name": "Milvus"}}},
                {"id": "n2", "data": {"type": "OpenAIModel", "node": {"display_name": "OpenAI"}}},
            ],
            "edges": [
                {
                    "source": "n1",
                    "target": "n2",
                    "sourceHandle": "œdataTypeœ:œMilvusœ,œidœ:œn1œ,œnameœ:œsearch_resultsœ",
                    "targetHandle": "œfieldNameœ:œinput_valueœ,œidœ:œn2œ",
                    "data": {},
                }
            ],
        }
        flow = _make_flow(data=data_with_encoded)
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow):
            result = await get_flow_graph_representations(FLOW_ID)

        # Must succeed even with encoded handles
        assert "error" not in result
        assert result["vertex_count"] == 2
        assert result["edge_count"] == 1


# ---------------------------------------------------------------------------
# get_flow_ascii_graph
# ---------------------------------------------------------------------------


class TestGetFlowAsciiGraph:
    @pytest.mark.asyncio
    async def test_returns_text_for_valid_flow(self):
        flow = _make_flow()
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow):
            result = await get_flow_ascii_graph(FLOW_ID)

        assert isinstance(result, str)
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_returns_error_string_for_missing_flow(self):
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None):
            result = await get_flow_ascii_graph("missing")

        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# get_flow_text_repr
# ---------------------------------------------------------------------------


class TestGetFlowTextRepr:
    @pytest.mark.asyncio
    async def test_returns_text_repr(self):
        flow = _make_flow()
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow):
            result = await get_flow_text_repr(FLOW_ID)

        assert "TestFlow" in result
        assert "Chat Input" in result

    @pytest.mark.asyncio
    async def test_returns_error_string_for_missing_flow(self):
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None):
            result = await get_flow_text_repr("missing")

        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# get_flow_graph_summary
# ---------------------------------------------------------------------------


class TestGetFlowGraphSummary:
    @pytest.mark.asyncio
    async def test_returns_metadata_with_counts(self):
        flow = _make_flow()
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow):
            result = await get_flow_graph_summary(FLOW_ID)

        assert result["flow_id"] == FLOW_ID
        assert result["vertex_count"] == 2
        assert result["edge_count"] == 1
        assert "n1" in result["vertices"]
        assert ("n1", "n2") in result["edges"]

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_flow(self):
        with patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None):
            result = await get_flow_graph_summary("missing")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self):
        with patch(
            f"{MODULE}.get_flow_by_id_or_endpoint_name",
            new_callable=AsyncMock,
            side_effect=RuntimeError("fail"),
        ):
            result = await get_flow_graph_summary(FLOW_ID)

        assert "error" in result
