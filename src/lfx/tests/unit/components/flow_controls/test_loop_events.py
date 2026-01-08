"""Tests for Loop component event emission from subgraph execution.

These tests verify that when LoopComponent executes its loop body as a subgraph,
events are properly emitted so the UI updates correctly.

Key requirements:
1. Events should be emitted for each vertex in the loop body
2. Events should use the ORIGINAL vertex IDs (not subgraph copies)
3. Events should be emitted for each iteration
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from lfx.base.flow_controls.loop_utils import execute_loop_body, get_loop_body_vertices
from lfx.components.flow_controls.loop import LoopComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class TestLoopEventEmissionUnit:
    """Unit tests for event emission during loop subgraph execution."""

    async def test_event_manager_passed_to_subgraph_async_start(self):
        """Test that event_manager is passed to subgraph's async_start method."""
        mock_event_manager = MagicMock()
        received_event_manager = None

        # Create a mock subgraph that captures the event_manager
        async def mock_async_start(event_manager=None):
            nonlocal received_event_manager
            received_event_manager = event_manager
            yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

        mock_subgraph = MagicMock()
        mock_subgraph.prepare = MagicMock()
        mock_subgraph.async_start = mock_async_start
        mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))

        mock_graph = MagicMock()
        mock_graph.create_subgraph = MagicMock(return_value=mock_subgraph)

        data_list = [Data(text="item1")]

        with patch("copy.deepcopy", return_value=mock_subgraph):
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

    async def test_event_manager_passed_for_each_iteration(self):
        """Test that event_manager is passed to async_start for each loop iteration."""
        mock_event_manager = MagicMock()
        event_manager_calls = []

        async def mock_async_start(event_manager=None):
            event_manager_calls.append(event_manager)
            yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

        mock_subgraph = MagicMock()
        mock_subgraph.prepare = MagicMock()
        mock_subgraph.async_start = mock_async_start
        mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))

        mock_graph = MagicMock()
        mock_graph.create_subgraph = MagicMock(return_value=mock_subgraph)

        # 3 items = 3 iterations
        data_list = [Data(text="item1"), Data(text="item2"), Data(text="item3")]

        with patch("copy.deepcopy", return_value=mock_subgraph):
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

    async def test_subgraph_preserves_vertex_ids(self):
        """Test that subgraph vertices maintain original IDs."""
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
    """Tests for event manager propagation through LoopComponent."""

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

    def test_identifies_simple_loop_body(self):
        """Test identification of vertices in a simple loop body."""
        # Create mock vertex
        mock_vertex = MagicMock()
        mock_vertex.id = "loop_component"
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "component_a"
        mock_vertex.outgoing_edges = [mock_edge]

        # Create mock graph
        mock_graph = MagicMock()
        mock_graph.successor_map = {
            "component_a": ["component_b"],
            "component_b": ["feedback_vertex"],
            "feedback_vertex": [],
        }

        # Mock get_incoming_edge_by_target_param
        def mock_get_incoming_edge(param):
            if param == "item":
                return "feedback_vertex"
            return None

        result = get_loop_body_vertices(
            vertex=mock_vertex,
            graph=mock_graph,
            get_incoming_edge_by_target_param_fn=mock_get_incoming_edge,
        )

        assert "component_a" in result
        assert "component_b" in result
        assert "feedback_vertex" in result

    def test_handles_no_outgoing_edges(self):
        """Test when loop has no outgoing edges."""
        mock_vertex = MagicMock()
        mock_vertex.outgoing_edges = []

        mock_graph = MagicMock()
        mock_graph.successor_map = {}

        result = get_loop_body_vertices(
            vertex=mock_vertex,
            graph=mock_graph,
            get_incoming_edge_by_target_param_fn=lambda _: None,
        )

        assert result == set()

    def test_handles_no_feedback_vertex(self):
        """Test when there's no vertex feeding back to loop."""
        mock_vertex = MagicMock()
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "component_a"
        mock_vertex.outgoing_edges = [mock_edge]

        mock_graph = MagicMock()
        mock_graph.successor_map = {"component_a": []}

        result = get_loop_body_vertices(
            vertex=mock_vertex,
            graph=mock_graph,
            get_incoming_edge_by_target_param_fn=lambda _: None,  # No feedback
        )

        assert result == set()

    def test_includes_all_predecessors(self):
        """Test that all predecessors of loop body vertices are included."""
        mock_vertex = MagicMock()
        mock_vertex.id = "loop_component"
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "processing_vertex"
        mock_vertex.outgoing_edges = [mock_edge]

        # Create a graph where processing_vertex has predecessors (e.g., an LLM model)
        mock_graph = MagicMock()
        mock_graph.successor_map = {
            "llm_model": ["processing_vertex"],  # LLM is a predecessor
            "processing_vertex": ["feedback_vertex"],
            "feedback_vertex": [],
        }

        def mock_get_incoming_edge(param):
            if param == "item":
                return "feedback_vertex"
            return None

        result = get_loop_body_vertices(
            vertex=mock_vertex,
            graph=mock_graph,
            get_incoming_edge_by_target_param_fn=mock_get_incoming_edge,
        )

        # Should include the LLM model predecessor
        assert "llm_model" in result
        assert "processing_vertex" in result
        assert "feedback_vertex" in result


class TestSubgraphIsolation:
    """Tests for subgraph isolation and proper execution context."""

    async def test_each_iteration_uses_fresh_subgraph_copy(self):
        """Test that each iteration uses a fresh deep copy of the subgraph."""
        deepcopy_calls = []

        def tracking_deepcopy(obj):
            copy = MagicMock()
            copy.prepare = MagicMock()
            copy.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))

            async def mock_async_start(**_kwargs):
                yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

            copy.async_start = mock_async_start
            deepcopy_calls.append(id(obj))
            return copy

        mock_subgraph = MagicMock()
        mock_graph = MagicMock()
        mock_graph.create_subgraph = MagicMock(return_value=mock_subgraph)

        data_list = [Data(text="item1"), Data(text="item2"), Data(text="item3")]

        with patch("lfx.base.flow_controls.loop_utils.copy.deepcopy", tracking_deepcopy):
            await execute_loop_body(
                graph=mock_graph,
                data_list=data_list,
                loop_body_vertex_ids={"vertex1"},
                start_vertex_id="vertex1",
                start_edge=MagicMock(target_handle=MagicMock(fieldName="data")),
                end_vertex_id="vertex1",
                event_manager=None,
            )

        # Should have called deepcopy once per iteration
        assert len(deepcopy_calls) == 3

    async def test_start_vertex_receives_correct_item(self):
        """Test that each iteration's start vertex receives the correct data item."""
        received_items = []

        def create_mock_subgraph():
            mock_custom_component = MagicMock()

            def capture_set(**kwargs):
                if "data" in kwargs:
                    received_items.append(kwargs["data"])

            mock_custom_component.set = capture_set

            mock_vertex = MagicMock()
            mock_vertex.custom_component = mock_custom_component

            mock_subgraph = MagicMock()
            mock_subgraph.prepare = MagicMock()
            mock_subgraph.get_vertex = MagicMock(return_value=mock_vertex)

            async def mock_async_start(**_kwargs):
                yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

            mock_subgraph.async_start = mock_async_start
            return mock_subgraph

        mock_graph = MagicMock()
        base_subgraph = MagicMock()
        mock_graph.create_subgraph = MagicMock(return_value=base_subgraph)

        data_list = [
            Data(text="first"),
            Data(text="second"),
            Data(text="third"),
        ]

        with patch("lfx.base.flow_controls.loop_utils.copy.deepcopy", lambda _: create_mock_subgraph()):
            await execute_loop_body(
                graph=mock_graph,
                data_list=data_list,
                loop_body_vertex_ids={"vertex1"},
                start_vertex_id="vertex1",
                start_edge=MagicMock(target_handle=MagicMock(fieldName="data")),
                end_vertex_id="vertex1",
                event_manager=None,
            )

        # Each item should have been passed to the start vertex
        assert len(received_items) == 3
        assert received_items[0].text == "first"
        assert received_items[1].text == "second"
        assert received_items[2].text == "third"
