"""Tests for Loop component and loop utilities.

These tests verify the loop body detection and component behavior.
Event manager propagation is critical for UI updates during loop execution.
Subgraph isolation tests are in tests/unit/graph/graph/test_subgraph_isolation.py.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from lfx.base.flow_controls.loop_utils import (
    execute_loop_body,
    get_loop_body_start_edges,
    get_loop_body_start_vertices,
    get_loop_body_vertices,
)
from lfx.components.flow_controls.loop import LoopComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


def create_subgraph_context_manager_mock(subgraph_factory):
    """Create a mock for create_subgraph that works as an async context manager.

    Args:
        subgraph_factory: A callable that takes vertex_ids and returns a mock subgraph
    """

    @asynccontextmanager
    async def mock_create_subgraph(vertex_ids):
        subgraph = subgraph_factory(vertex_ids)
        try:
            yield subgraph
        finally:
            pass  # Cleanup would happen here in real code

    return mock_create_subgraph


class TestLoopComponentBasics:
    """Basic tests for LoopComponent."""

    @pytest.mark.asyncio
    async def test_done_output_uses_event_manager(self):
        """Test that done_output uses self._event_manager."""
        loop = LoopComponent(_id="test_loop")
        loop.set(data=DataFrame([]))
        loop._event_manager = None

        # Should not raise and should work with empty data
        result = await loop.done_output()
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
        """The loop body's runner must forward event_manager into the executor's runtime_options."""
        from lfx.execution import (
            Coordinator,
            ExecutorRegistry,
            reset_default_coordinator,
            set_default_coordinator,
        )
        from lfx.execution.executor import Executor
        from lfx.execution.types import RunComplete

        try:
            mock_event_manager = MagicMock()
            seen: list = []

            class _Recorder(Executor):
                kind = "in-process"

                async def execute(self, unit):
                    seen.append(unit.runtime_options.get("event_manager"))
                    yield RunComplete(outputs=[])

            registry = ExecutorRegistry()
            registry.register(_Recorder())
            set_default_coordinator(Coordinator(registry=registry))

            def create_mock_subgraph(_vertex_ids):
                mock_subgraph = MagicMock()
                mock_subgraph._vertices = []
                mock_subgraph.prepare = MagicMock()
                mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))
                return mock_subgraph

            mock_graph = MagicMock()
            mock_graph.create_subgraph = create_subgraph_context_manager_mock(create_mock_subgraph)

            await execute_loop_body(
                graph=mock_graph,
                data_list=[Data(text="item1")],
                loop_body_vertex_ids={"vertex1"},
                start_edges=[MagicMock(target_id="vertex1", target_handle=MagicMock(field_name="data"))],
                end_vertex_id="vertex1",
                event_manager=mock_event_manager,
            )

            assert len(seen) == 1
            assert seen[0] is mock_event_manager
        finally:
            reset_default_coordinator()

    @pytest.mark.asyncio
    async def test_event_manager_passed_for_each_iteration(self):
        """Every loop iteration runs through the executor with the same event_manager."""
        from lfx.execution import (
            Coordinator,
            ExecutorRegistry,
            reset_default_coordinator,
            set_default_coordinator,
        )
        from lfx.execution.executor import Executor
        from lfx.execution.types import RunComplete

        try:
            mock_event_manager = MagicMock()
            seen: list = []

            class _Recorder(Executor):
                kind = "in-process"

                async def execute(self, unit):
                    seen.append(unit.runtime_options.get("event_manager"))
                    yield RunComplete(outputs=[])

            registry = ExecutorRegistry()
            registry.register(_Recorder())
            set_default_coordinator(Coordinator(registry=registry))

            def create_mock_subgraph(_vertex_ids):
                mock_subgraph = MagicMock()
                mock_subgraph._vertices = []
                mock_subgraph.prepare = MagicMock()
                mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(custom_component=MagicMock()))
                return mock_subgraph

            mock_graph = MagicMock()
            mock_graph.create_subgraph = create_subgraph_context_manager_mock(create_mock_subgraph)

            await execute_loop_body(
                graph=mock_graph,
                data_list=[Data(text="item1"), Data(text="item2"), Data(text="item3")],
                loop_body_vertex_ids={"vertex1"},
                start_edges=[MagicMock(target_id="vertex1", target_handle=MagicMock(field_name="data"))],
                end_vertex_id="vertex1",
                event_manager=mock_event_manager,
            )

            assert len(seen) == 3
            assert all(em is mock_event_manager for em in seen)
        finally:
            reset_default_coordinator()

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
        """Test that done_output properly passes self._event_manager to execute_loop_body."""
        mock_event_manager = MagicMock()

        # Create loop component
        loop = LoopComponent()
        data_list = [Data(text="item1")]
        loop.set(data=DataFrame(data_list))
        loop._id = "test_loop"
        loop._event_manager = mock_event_manager  # Set event manager on component

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
            result = await loop.done_output()

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


class TestRawParamsInjection:
    """Tests for loop item injection into vertex raw_params.

    These tests verify the fix for the bug where HandleInput fields (type="other")
    were not receiving loop items because:
    1. Fields with type="other" are skipped during field param processing
    2. The updated_raw_params flag was being reset too early
    3. Multiple build_params() calls would rebuild params, losing the injected values
    """

    def test_updated_raw_params_flag_persists_across_multiple_build_params_calls(self):
        """Test that updated_raw_params flag persists across multiple build_params() calls.

        This is the core fix: the flag must stay True through ALL build_params() calls
        during initialization, not just the first one.
        """
        from unittest.mock import MagicMock

        from lfx.schema.data import Data

        # Create a mock vertex with the necessary attributes
        mock_vertex = MagicMock()
        mock_vertex.graph = MagicMock()
        mock_vertex.updated_raw_params = False
        mock_vertex.raw_params = {}
        mock_vertex.params = {}

        # Import the actual build_params method
        from lfx.graph.vertex.base import Vertex

        # Bind build_params to our mock
        mock_vertex.build_params = Vertex.build_params.__get__(mock_vertex)

        # Simulate loop item injection
        test_data = Data(text="test item")
        mock_vertex.raw_params = {"input_data": test_data}
        mock_vertex.params = {"input_data": test_data}
        mock_vertex.updated_raw_params = True

        # First build_params() call - should skip and keep flag True
        mock_vertex.build_params()
        assert mock_vertex.updated_raw_params is True, "Flag should persist after first build_params()"

        # Second build_params() call - should also skip and keep flag True
        mock_vertex.build_params()
        assert mock_vertex.updated_raw_params is True, "Flag should persist after second build_params()"

        # Third build_params() call - should still skip and keep flag True
        mock_vertex.build_params()
        assert mock_vertex.updated_raw_params is True, "Flag should persist after third build_params()"

    def test_update_raw_params_sets_flag_and_updates_params(self):
        """Test that update_raw_params sets the flag and updates both raw_params and params.

        This verifies that when we inject loop items via update_raw_params:
        1. Both raw_params and params are updated
        2. The updated_raw_params flag is set to True
        3. This protects against build_params() rebuilding
        """
        from unittest.mock import MagicMock

        from lfx.graph.vertex.base import Vertex
        from lfx.schema.data import Data

        # Create a mock vertex with minimal setup
        mock_vertex = MagicMock()
        mock_vertex.raw_params = {"existing_param": "value"}
        mock_vertex.params = {"existing_param": "value"}
        mock_vertex.updated_raw_params = False

        # Bind the actual update_raw_params method
        mock_vertex.update_raw_params = Vertex.update_raw_params.__get__(mock_vertex)

        # Inject loop item
        test_data = Data(text="test item")
        mock_vertex.update_raw_params({"input_data": test_data}, overwrite=True)

        # Verify both raw_params and params are updated
        assert "input_data" in mock_vertex.raw_params
        assert mock_vertex.raw_params["input_data"] == test_data
        assert "input_data" in mock_vertex.params
        assert mock_vertex.params["input_data"] == test_data

        # Verify flag is set
        assert mock_vertex.updated_raw_params is True

    @pytest.mark.asyncio
    async def test_loop_item_injection_via_execute_loop_body(self):
        """Test that execute_loop_body actually injects loop items into vertex raw_params.

        This is an integration-style test that exercises the actual loop_utils.py code path,
        verifying that update_raw_params() is called with loop items during execution.
        """
        from unittest.mock import MagicMock

        from lfx.schema.data import Data

        # Track calls to update_raw_params
        update_raw_params_calls = []

        def mock_update_raw_params(params, overwrite=False):  # noqa: FBT002
            update_raw_params_calls.append((params, overwrite))

        # Create mock vertex that tracks update_raw_params calls
        mock_start_vertex = MagicMock()
        mock_start_vertex.id = "start_vertex"
        mock_start_vertex.custom_component = MagicMock()
        mock_start_vertex.update_raw_params = mock_update_raw_params

        # Create mock subgraph
        def create_mock_subgraph(_vertex_ids):
            mock_subgraph = MagicMock()
            mock_subgraph._vertices = [
                {"id": "start_vertex", "data": {"node": {"template": {"input_data": {"value": None}}}}}
            ]
            mock_subgraph.prepare = MagicMock()
            mock_subgraph.get_vertex = MagicMock(return_value=mock_start_vertex)

            # Mock async_start to yield valid results
            async def mock_async_start(**_kwargs):
                yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

            mock_subgraph.async_start = mock_async_start
            return mock_subgraph

        mock_graph = MagicMock()
        mock_graph.create_subgraph = create_subgraph_context_manager_mock(create_mock_subgraph)

        # Test data
        data_list = [
            Data(text="First item"),
            Data(text="Second item"),
        ]

        # Mock edge with field_name, targeting the start vertex
        mock_edge = MagicMock()
        mock_edge.target_id = "start_vertex"
        mock_edge.target_handle.field_name = "input_data"

        # Execute loop body
        await execute_loop_body(
            graph=mock_graph,
            data_list=data_list,
            loop_body_vertex_ids={"start_vertex"},
            start_edges=[mock_edge],
            end_vertex_id="start_vertex",
            event_manager=None,
        )

        # Verify update_raw_params was called for each loop item
        assert len(update_raw_params_calls) == 2, "Should call update_raw_params for each loop iteration"

        # Verify first call had first item
        first_call_params, first_call_overwrite = update_raw_params_calls[0]
        assert "input_data" in first_call_params
        assert first_call_params["input_data"].text == "First item"
        assert first_call_overwrite is True

        # Verify second call had second item
        second_call_params, second_call_overwrite = update_raw_params_calls[1]
        assert "input_data" in second_call_params
        assert second_call_params["input_data"].text == "Second item"
        assert second_call_overwrite is True

    @pytest.mark.asyncio
    async def test_loop_item_injected_into_every_fan_out_branch(self):
        """Loop.item connected directly to multiple branches must inject the item into all of them.

        Regression test for https://github.com/langflow-ai/langflow/issues/14964:
        when Loop.item fans out to two (or more) vertices, only start_edges[0] used
        to receive the current iteration item - the other branch(es) got None.
        """
        from unittest.mock import MagicMock

        from lfx.schema.data import Data

        # Track update_raw_params calls per vertex so we can tell branches apart.
        update_raw_params_calls: dict[str, list] = {"branch_a": [], "branch_b": []}

        def make_mock_vertex(vertex_id: str):
            vertex = MagicMock()
            vertex.id = vertex_id
            vertex.custom_component = MagicMock()
            vertex.update_raw_params = lambda params, overwrite=False, vid=vertex_id: (
                update_raw_params_calls[vid].append((params, overwrite))
            )
            return vertex

        mock_branch_a = make_mock_vertex("branch_a")
        mock_branch_b = make_mock_vertex("branch_b")
        vertices_by_id = {"branch_a": mock_branch_a, "branch_b": mock_branch_b}

        def create_mock_subgraph(_vertex_ids):
            mock_subgraph = MagicMock()
            mock_subgraph._vertices = [
                {"id": "branch_a", "data": {"node": {"template": {"a_id": {"value": None}}}}},
                {"id": "branch_b", "data": {"node": {"template": {"b_id": {"value": None}}}}},
            ]
            mock_subgraph.prepare = MagicMock()
            mock_subgraph.get_vertex = MagicMock(side_effect=lambda vid: vertices_by_id[vid])

            async def mock_async_start(**_kwargs):
                yield MagicMock(valid=True, result_dict=MagicMock(outputs={}))

            mock_subgraph.async_start = mock_async_start
            return mock_subgraph

        mock_graph = MagicMock()
        mock_graph.create_subgraph = create_subgraph_context_manager_mock(create_mock_subgraph)

        data_list = [Data(text="Q001"), Data(text="Q002")]

        # Two edges fan out from the same Loop.item output to two independent branches.
        edge_to_a = MagicMock(target_id="branch_a", target_handle=MagicMock(field_name="a_id"))
        edge_to_b = MagicMock(target_id="branch_b", target_handle=MagicMock(field_name="b_id"))

        await execute_loop_body(
            graph=mock_graph,
            data_list=data_list,
            loop_body_vertex_ids={"branch_a", "branch_b"},
            start_edges=[edge_to_a, edge_to_b],
            end_vertex_id="branch_b",
            event_manager=None,
        )

        # Both branches must receive the current item on every iteration - not just
        # whichever edge happened to be start_edges[0].
        assert len(update_raw_params_calls["branch_a"]) == 2
        assert len(update_raw_params_calls["branch_b"]) == 2

        for i, expected_text in enumerate(["Q001", "Q002"]):
            a_params, a_overwrite = update_raw_params_calls["branch_a"][i]
            b_params, b_overwrite = update_raw_params_calls["branch_b"][i]
            assert a_params["a_id"].text == expected_text
            assert b_params["b_id"].text == expected_text
            assert a_overwrite is True
            assert b_overwrite is True


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


class TestGetLoopBodyStartVerticesAndEdges:
    """Tests for get_loop_body_start_vertices / get_loop_body_start_edges.

    Regression coverage for https://github.com/langflow-ai/langflow/issues/14964:
    these must return every edge/vertex fanning out from the loop's output, not
    just the first one.
    """

    class _SourceHandle:
        def __init__(self, name):
            self.name = name

    class _Edge:
        def __init__(self, target_id, source_handle_name="item"):
            self.target_id = target_id
            self.source_handle = TestGetLoopBodyStartVerticesAndEdges._SourceHandle(source_handle_name)

    def test_returns_all_vertices_for_single_edge(self):
        vertex = type("MockVertex", (), {"outgoing_edges": [self._Edge("component_a")]})()

        assert get_loop_body_start_vertices(vertex) == ["component_a"]

    def test_returns_all_vertices_when_item_fans_out(self):
        """The reported bug: two branches connected directly to Loop.item."""
        edges = [self._Edge("branch_a"), self._Edge("branch_b")]
        vertex = type("MockVertex", (), {"outgoing_edges": edges})()

        assert get_loop_body_start_vertices(vertex) == ["branch_a", "branch_b"]

    def test_returns_empty_list_when_no_matching_edges(self):
        edges = [self._Edge("other_target", source_handle_name="done")]
        vertex = type("MockVertex", (), {"outgoing_edges": edges})()

        assert get_loop_body_start_vertices(vertex) == []

    def test_start_edges_matches_start_vertices_length(self):
        edges = [self._Edge("branch_a"), self._Edge("branch_b"), self._Edge("branch_c")]
        vertex = type("MockVertex", (), {"outgoing_edges": edges})()

        result_edges = get_loop_body_start_edges(vertex)

        assert result_edges == edges
        assert [e.target_id for e in result_edges] == get_loop_body_start_vertices(vertex)
