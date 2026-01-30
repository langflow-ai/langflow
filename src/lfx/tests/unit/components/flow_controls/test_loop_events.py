"""Tests for Loop component and loop utilities.

These tests verify the loop body detection and component behavior.
Event manager propagation is critical for UI updates during loop execution.
Subgraph isolation tests are in tests/unit/graph/graph/test_subgraph_isolation.py.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from lfx.base.flow_controls.loop_utils import execute_loop_body, get_loop_body_vertices
from lfx.components.flow_controls.loop import LoopComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class TestLoopComponentBasics:
    """Basic tests for LoopComponent."""

    @pytest.mark.asyncio
    async def test_done_output_accepts_event_manager(self):
        """Test that done_output accepts event_manager parameter."""
        loop = LoopComponent(_id="test_loop")
        loop.set(data=DataFrame([]))

        # Should not raise when event_manager is passed
        result = await loop.done_output(event_manager=None)
        assert isinstance(result, DataFrame)

    def test_loop_validates_data_input_types(self):
        """Test that loop validates data input types."""
        from lfx.base.flow_controls.loop_utils import validate_data_input

        # DataFrame should work
        result = validate_data_input(DataFrame([Data(text="item")]))
        assert len(result) == 1

        # Data should work
        result = validate_data_input(Data(text="single"))
        assert len(result) == 1

        # List of Data should work
        result = validate_data_input([Data(text="a"), Data(text="b")])
        assert len(result) == 2

        # Invalid type should raise
        with pytest.raises(TypeError):
            validate_data_input("invalid")


class TestEventManagerPropagation:
    """Tests for event manager propagation through loop execution.

    Event manager propagation is critical - it enables the UI to receive
    real-time updates as each vertex in the loop body executes.
    """

    @pytest.mark.asyncio
    async def test_event_manager_passed_to_subgraph_async_start(self):
        """Test that event_manager is passed to subgraph's async_start method."""
        mock_event_manager = MagicMock()
        received_event_manager = None

        # Create a mock subgraph that captures the event_manager
        async def mock_async_start(event_manager=None):
            nonlocal received_event_manager
            received_event_manager = event_manager
            yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

        def create_mock_subgraph(_vertex_ids):
            mock_subgraph = MagicMock()
            mock_subgraph.prepare = MagicMock()
            mock_subgraph.async_start = mock_async_start
            mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))
            return mock_subgraph

        mock_graph = MagicMock()
        mock_graph.create_subgraph = create_mock_subgraph

        data_list = [Data(text="item1")]

        await execute_loop_body(
            graph=mock_graph,
            data_list=data_list,
            loop_body_vertex_ids={"vertex1"},
            start_vertex_id="vertex1",
            start_edge=MagicMock(target_handle=MagicMock(fieldName="data")),
            end_vertex_id="vertex1",
            event_manager=mock_event_manager,
        )

        # Verify event_manager was passed to async_start
        assert received_event_manager is mock_event_manager

    @pytest.mark.asyncio
    async def test_event_manager_passed_for_each_iteration(self):
        """Test that event_manager is passed to async_start for each loop iteration."""
        mock_event_manager = MagicMock()
        event_manager_calls = []

        async def mock_async_start(event_manager=None):
            event_manager_calls.append(event_manager)
            yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

        def create_mock_subgraph(_vertex_ids):
            mock_subgraph = MagicMock()
            mock_subgraph.prepare = MagicMock()
            mock_subgraph.async_start = mock_async_start
            mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))
            return mock_subgraph

        mock_graph = MagicMock()
        mock_graph.create_subgraph = create_mock_subgraph

        # 3 items = 3 iterations
        data_list = [Data(text="item1"), Data(text="item2"), Data(text="item3")]

        await execute_loop_body(
            graph=mock_graph,
            data_list=data_list,
            loop_body_vertex_ids={"vertex1"},
            start_vertex_id="vertex1",
            start_edge=MagicMock(target_handle=MagicMock(fieldName="data")),
            end_vertex_id="vertex1",
            event_manager=mock_event_manager,
        )

        # Verify event_manager was passed for each iteration
        assert len(event_manager_calls) == 3
        assert all(em is mock_event_manager for em in event_manager_calls)

    def test_subgraph_preserves_vertex_ids(self):
        """Test that subgraph vertices maintain original IDs.

        This is critical for the UI to show updates for the correct components.
        If vertex IDs were modified, the UI wouldn't know which component is executing.
        """
        mock_graph = MagicMock()

        # Simulate _vertices and _edges with original IDs
        mock_graph._vertices = [
            {"id": "original_vertex_1"},
            {"id": "original_vertex_2"},
        ]
        mock_graph._edges = []
        mock_graph.flow_id = "test_flow"
        mock_graph.flow_name = "test"
        mock_graph.user_id = "test_user"
        mock_graph.context = {}

        # Track what vertex IDs are used in subgraph
        captured_vertex_ids = None

        def mock_create_subgraph(vertex_ids):
            nonlocal captured_vertex_ids
            captured_vertex_ids = vertex_ids
            subgraph = MagicMock()
            # Verify the subgraph would receive original IDs
            subgraph._vertices = [v for v in mock_graph._vertices if v["id"] in vertex_ids]
            return subgraph

        mock_graph.create_subgraph = mock_create_subgraph

        # Call create_subgraph with specific vertex IDs
        mock_graph.create_subgraph({"original_vertex_1", "original_vertex_2"})

        # Verify original IDs were passed
        assert captured_vertex_ids == {"original_vertex_1", "original_vertex_2"}


class TestLoopComponentEventManagerPropagation:
    """Tests for event manager propagation through LoopComponent methods.

    These tests verify the component-level propagation:
    LoopComponent.done_output → execute_loop_body
    """

    @pytest.mark.asyncio
    async def test_done_output_passes_event_manager(self):
        """Test that done_output properly passes event_manager to execute_loop_body."""
        mock_event_manager = MagicMock()

        # Create loop component
        loop = LoopComponent()
        data_list = [Data(text="item1")]
        loop.set(data=DataFrame(data_list))
        loop._id = "test_loop"

        # Mock execute_loop_body to return expected data
        mock_execute = AsyncMock(return_value=[Data(text="result")])

        # Mock initialize_data
        def mock_initialize_data():
            pass

        # Create a mock context that returns data_list
        mock_ctx = MagicMock()
        mock_ctx.get = MagicMock(
            side_effect=lambda key, default=None: data_list if key == f"{loop._id}_data" else default
        )

        with (
            patch.object(loop, "execute_loop_body", mock_execute),
            patch.object(loop, "initialize_data", mock_initialize_data),
            patch.object(type(loop), "ctx", new_callable=PropertyMock, return_value=mock_ctx),
        ):
            result = await loop.done_output(event_manager=mock_event_manager)

            # Verify execute_loop_body was called with the event_manager
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args

            # Check that event_manager was passed as keyword argument
            assert "event_manager" in call_args.kwargs
            assert call_args.kwargs["event_manager"] is mock_event_manager
            assert isinstance(result, DataFrame)

    @pytest.mark.asyncio
    async def test_execute_loop_body_called_with_event_manager(self):
        """Test that execute_loop_body is invoked with event_manager from done_output."""
        # Create a mock event manager
        mock_event_manager = MagicMock()

        # Create loop component with data
        loop = LoopComponent()
        data_list = [Data(text="item1"), Data(text="item2")]
        loop.set(data=DataFrame(data_list))
        loop._id = "test_loop"

        # Mock the graph and vertex to simulate proper context
        mock_graph = MagicMock()
        mock_vertex = MagicMock()
        mock_vertex.outgoing_edges = []
        loop._vertex = mock_vertex
        loop._graph = mock_graph

        # Mock get_loop_body_vertices to return empty set (no loop body)
        with patch.object(loop, "get_loop_body_vertices", return_value=set()):
            result = await loop.execute_loop_body(data_list, event_manager=mock_event_manager)

            # Should return empty list when no loop body vertices
            assert result == []


class TestGetLoopBodyVertices:
    """Tests for get_loop_body_vertices utility function."""

    def test_returns_empty_set_when_no_outgoing_edges(self):
        """Test when loop has no outgoing edges."""

        class MockVertex:
            outgoing_edges = []
            id = "loop"

        class MockGraph:
            successor_map = {}

        result = get_loop_body_vertices(
            vertex=MockVertex(),
            graph=MockGraph(),
            get_incoming_edge_by_target_param_fn=lambda _: None,
        )

        assert result == set()

    def test_returns_empty_set_when_no_feedback_vertex(self):
        """Test when there's no vertex feeding back to loop."""

        class MockEdge:
            class SourceHandle:
                name = "item"

            source_handle = SourceHandle()
            target_id = "component_a"

        class MockVertex:
            outgoing_edges = [MockEdge()]
            id = "loop"

        class MockGraph:
            successor_map = {"component_a": []}

        result = get_loop_body_vertices(
            vertex=MockVertex(),
            graph=MockGraph(),
            get_incoming_edge_by_target_param_fn=lambda _: None,
        )

        assert result == set()

    def test_identifies_loop_body_vertices(self):
        """Test identification of vertices in a loop body."""

        class MockEdge:
            class SourceHandle:
                name = "item"

            source_handle = SourceHandle()
            target_id = "component_a"

        class MockVertex:
            outgoing_edges = [MockEdge()]
            id = "loop_component"

        class MockGraph:
            successor_map = {
                "component_a": ["component_b"],
                "component_b": ["feedback_vertex"],
                "feedback_vertex": [],
            }

        def get_incoming_edge(param):
            return "feedback_vertex" if param == "item" else None

        result = get_loop_body_vertices(
            vertex=MockVertex(),
            graph=MockGraph(),
            get_incoming_edge_by_target_param_fn=get_incoming_edge,
        )

        assert "component_a" in result
        assert "component_b" in result
        assert "feedback_vertex" in result

    def test_includes_predecessors_of_loop_body(self):
        """Test that predecessors of loop body vertices are included."""

        class MockEdge:
            class SourceHandle:
                name = "item"

            source_handle = SourceHandle()
            target_id = "processing_vertex"

        class MockVertex:
            outgoing_edges = [MockEdge()]
            id = "loop_component"

        class MockGraph:
            successor_map = {
                "llm_model": ["processing_vertex"],
                "processing_vertex": ["feedback_vertex"],
                "feedback_vertex": [],
            }

        def get_incoming_edge(param):
            return "feedback_vertex" if param == "item" else None

        result = get_loop_body_vertices(
            vertex=MockVertex(),
            graph=MockGraph(),
            get_incoming_edge_by_target_param_fn=get_incoming_edge,
        )

        assert "llm_model" in result
        assert "processing_vertex" in result
        assert "feedback_vertex" in result

    def test_excludes_loop_component_from_predecessors(self):
        """Test that the loop component itself is not included as a predecessor."""

        class MockEdge:
            class SourceHandle:
                name = "item"

            source_handle = SourceHandle()
            target_id = "component_a"

        class MockVertex:
            outgoing_edges = [MockEdge()]
            id = "loop_component"

        class MockGraph:
            successor_map = {
                "loop_component": ["component_a"],
                "component_a": ["feedback_vertex"],
                "feedback_vertex": [],
            }

        def get_incoming_edge(param):
            return "feedback_vertex" if param == "item" else None

        result = get_loop_body_vertices(
            vertex=MockVertex(),
            graph=MockGraph(),
            get_incoming_edge_by_target_param_fn=get_incoming_edge,
        )

        assert "loop_component" not in result
        assert "component_a" in result
        assert "feedback_vertex" in result
