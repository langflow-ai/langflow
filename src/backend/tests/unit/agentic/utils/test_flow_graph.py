"""Tests for flow graph visualization utilities.

Tests get_flow_graph_representations, get_flow_ascii_graph,
get_flow_text_repr, and get_flow_graph_summary.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from langflow.agentic.utils.flow_graph import (
    get_flow_ascii_graph,
    get_flow_graph_representations,
    get_flow_graph_summary,
    get_flow_text_repr,
)

MODULE = "langflow.agentic.utils.flow_graph"

FLOW_ID = str(uuid4())


def _mock_logger():
    """Create a mock async logger."""
    mock = MagicMock()
    mock.aerror = AsyncMock()
    mock.ainfo = AsyncMock()
    mock.awarning = AsyncMock()
    return mock


def _make_flow(*, has_data=True, name="TestFlow"):
    """Create a mock flow object."""
    flow = MagicMock()
    flow.id = UUID(FLOW_ID)
    flow.name = name
    flow.tags = ["test"]
    flow.description = "A test flow"
    flow.data = {"nodes": [], "edges": []} if has_data else None
    return flow


def _make_graph(vertex_ids=None, edge_pairs=None):
    """Create a mock graph with vertices and edges."""
    graph = MagicMock()

    vertices = []
    for vid in ["v1", "v2"] if vertex_ids is None else vertex_ids:
        v = MagicMock()
        v.id = vid
        vertices.append(v)
    graph.vertices = vertices

    edges = []
    for src, tgt in [("v1", "v2")] if edge_pairs is None else edge_pairs:
        e = MagicMock()
        e.source_id = src
        e.target_id = tgt
        edges.append(e)
    graph.edges = edges

    graph.__repr__ = MagicMock(return_value="Graph(vertices=2, edges=1)")  # type: ignore[method-assign]
    return graph


class TestGetFlowGraphRepresentations:
    """Tests for get_flow_graph_representations."""

    @pytest.mark.asyncio
    async def test_should_return_all_data(self):
        """Should return ascii_graph, text_repr, vertex/edge counts."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.draw_graph", return_value="[v1] -> [v2]"),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_representations("test-flow")

        assert result["flow_id"] == FLOW_ID
        assert result["flow_name"] == "TestFlow"
        assert result["ascii_graph"] == "[v1] -> [v2]"
        assert result["vertex_count"] == 2
        assert result["edge_count"] == 1
        assert result["tags"] == ["test"]

    @pytest.mark.asyncio
    async def test_should_return_error_when_flow_not_found(self):
        """Should return error dict for nonexistent flow."""
        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_representations("missing-flow")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_should_return_error_when_no_data(self):
        """Should return error for flow with no data."""
        flow = _make_flow(has_data=False)

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_representations("test-flow")

        assert "error" in result
        assert "no data" in result["error"]

    @pytest.mark.asyncio
    async def test_should_handle_draw_graph_failure(self):
        """Should return fallback message when draw_graph raises."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.draw_graph", side_effect=RuntimeError("too complex")),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_representations("test-flow")

        assert "failed" in result["ascii_graph"].lower()

    @pytest.mark.asyncio
    async def test_should_return_none_ascii_when_no_vertices(self):
        """Should return None for ascii_graph when graph has no vertices."""
        flow = _make_flow()
        graph = _make_graph(vertex_ids=[], edge_pairs=[])

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_representations("test-flow")

        assert result["ascii_graph"] is None


class TestGetFlowAsciiGraph:
    """Tests for get_flow_ascii_graph."""

    @pytest.mark.asyncio
    async def test_should_return_ascii_string(self):
        """Should return the ASCII graph string."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.draw_graph", return_value="[v1] -> [v2]"),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_ascii_graph("test-flow")

        assert result == "[v1] -> [v2]"

    @pytest.mark.asyncio
    async def test_should_return_error_string(self):
        """Should return 'Error: ...' for nonexistent flow."""
        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_ascii_graph("missing-flow")

        assert result.startswith("Error:")


class TestGetFlowTextRepr:
    """Tests for get_flow_text_repr."""

    @pytest.mark.asyncio
    async def test_should_return_repr_string(self):
        """Should return the graph's text representation."""
        flow = _make_flow()
        graph = _make_graph()

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.draw_graph", return_value="ascii"),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_text_repr("test-flow")

        assert isinstance(result, str)


class TestGetFlowGraphSummary:
    """Tests for get_flow_graph_summary."""

    @pytest.mark.asyncio
    async def test_should_return_metadata(self):
        """Should return flow metadata with counts, vertices, edges."""
        flow = _make_flow()
        graph = _make_graph(vertex_ids=["a", "b", "c"], edge_pairs=[("a", "b"), ("b", "c")])

        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=flow),
            patch(f"{MODULE}.Graph.from_payload", return_value=graph),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_summary("test-flow")

        assert result["flow_id"] == FLOW_ID
        assert result["vertex_count"] == 3
        assert result["edge_count"] == 2
        assert result["vertices"] == ["a", "b", "c"]
        assert ("a", "b") in result["edges"]

    @pytest.mark.asyncio
    async def test_should_return_error_when_not_found(self):
        """Should return error dict for nonexistent flow."""
        with (
            patch(f"{MODULE}.get_flow_by_id_or_endpoint_name", new_callable=AsyncMock, return_value=None),
            patch(f"{MODULE}.logger", _mock_logger()),
        ):
            result = await get_flow_graph_summary("missing-flow")

        assert "error" in result
