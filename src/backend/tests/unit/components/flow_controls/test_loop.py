import json
from uuid import UUID

import orjson
import pytest
from httpx import AsyncClient
from langflow.memory import aget_messages
from langflow.services.database.models.flow import FlowCreate
from lfx.components.data_source.url import URLComponent
from lfx.components.flow_controls import LoopComponent
from lfx.components.input_output import ChatOutput
from lfx.components.llm_operations import StructuredOutputComponent
from lfx.components.models_and_agents import PromptComponent
from lfx.components.openai.openai_chat_model import OpenAIModelComponent
from lfx.components.processing import ParserComponent, SplitTextComponent
from lfx.graph import Graph
from lfx.schema.data import Data

from tests.api_keys import get_openai_api_key, has_api_key
from tests.base import ComponentTestBaseWithClient
from tests.unit.build_utils import build_flow, get_build_events

TEXT = (
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet. "
    "lorem ipsum dolor sit amet lorem ipsum dolor sit amet lorem ipsum dolor sit amet."
)


class TestLoopComponentWithAPI(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return LoopComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "data": [[Data(text="Hello World")]],
            "loop_input": [Data(text=TEXT)],
        }

    def test_latest_version(self, component_class, default_kwargs) -> None:
        """Test that the component works with the latest version."""
        result = component_class(**default_kwargs)
        assert result is not None, "Component returned None for the latest version."

    async def _create_flow(self, client, json_loop_test, logged_in_headers):
        vector_store = orjson.loads(json_loop_test)
        data = vector_store["data"]
        vector_store = FlowCreate(name="Flow", description="description", data=data, endpoint_name="f")
        response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
        response.raise_for_status()
        return response.json()["id"]

    async def check_messages(self, flow_id):
        messages = await aget_messages(flow_id=UUID(flow_id), order="ASC")
        assert len(messages) == 1
        assert messages[0].session_id == flow_id
        assert messages[0].sender == "Machine"
        assert messages[0].sender_name == "AI"
        assert len(messages[0].text) > 0
        return messages

    async def test_build_flow_loop(self, client, json_loop_test, logged_in_headers):
        """Test building a flow with a loop component."""
        # Create the flow
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)

        # Start the build and get job_id
        build_response = await build_flow(client, flow_id, logged_in_headers)
        job_id = build_response["job_id"]
        assert job_id is not None

        # Get the events stream
        events_response = await get_build_events(client, job_id, logged_in_headers)
        assert events_response.status_code == 200

        # Process the events stream
        chat_output = None
        lines = []
        async for line in events_response.aiter_lines():
            if not line:  # Skip empty lines
                continue
            lines.append(line)
            if "ChatOutput" in line:
                chat_output = json.loads(line)
            # Process events if needed
            # We could add specific assertions here for loop-related events
        assert chat_output is not None
        messages = await self.check_messages(flow_id)
        ai_message = messages[0].text
        json_data = orjson.loads(ai_message)

        # Use a for loop for better debugging
        found = []
        json_data = [(data["text"], q_dict) for data, q_dict in json_data]
        for text, q_dict in json_data:
            expected_text = f"==> {q_dict['q']}"
            assert expected_text in text, (
                f"Found {found} until now, but expected '{expected_text}' not found in '{text}',"
                f"and the json_data is {json_data}"
            )
            found.append(expected_text)

    async def test_run_flow_loop(self, client: AsyncClient, created_api_key, json_loop_test, logged_in_headers):
        flow_id = await self._create_flow(client, json_loop_test, logged_in_headers)
        headers = {"x-api-key": created_api_key.api_key}
        payload = {
            "input_value": TEXT,
            "input_type": "chat",
            "session_id": f"{flow_id}run",
            "output_type": "chat",
            "tweaks": {},
        }
        response = await client.post(f"/api/v1/run/{flow_id}", json=payload, headers=headers)
        data = response.json()
        assert "outputs" in data
        assert "session_id" in data
        assert len(data["outputs"][-1]["outputs"]) > 0


@pytest.mark.skipif(not has_api_key("OPENAI_API_KEY"), reason="OPENAI_API_KEY is not set")
def loop_flow():
    """Complete loop flow that processes multiple URLs through a loop."""
    # Create URL component to fetch content from multiple sources
    url_component = URLComponent()
    url_component.set(urls=["https://docs.langflow.org/"])

    # Create SplitText component to chunk the content
    split_text_component = SplitTextComponent()
    split_text_component.set(
        data_inputs=url_component.fetch_content,
        chunk_size=1000,
        chunk_overlap=200,
        separator="\n\n",
    )

    # Create Loop component to iterate through the chunks
    loop_component = LoopComponent()
    loop_component.set(data=split_text_component.split_text)

    # Create Parser component to format the current loop item
    parser_component = ParserComponent()
    parser_component.set(
        input_data=loop_component.item_output,
        pattern="Content: {text}",
        sep="\n",
    )

    # Create Prompt component to create processing instructions
    prompt_component = PromptComponent()
    prompt_component.set(
        template="Analyze and summarize this content: {context}",
        input_text=parser_component.parse_combined_text,
    )

    # Create OpenAI model component for processing
    openai_component = OpenAIModelComponent()
    openai_component.set(
        api_key=get_openai_api_key(),
        model_name="gpt-4.1-mini",
        temperature=0.7,
    )

    # Create StructuredOutput component to process content
    structured_output = StructuredOutputComponent()
    structured_output.set(
        llm=openai_component.build_model,
        input_value=prompt_component.build_prompt,
        schema_name="ProcessedContent",
        system_prompt=(  # Added missing system_prompt - this was causing the "Multiple structured outputs" error
            "You are an AI that extracts one structured JSON object from unstructured text. "
            "Use a predefined schema with expected types (str, int, float, bool, dict). "
            "If multiple structures exist, extract only the first most complete one. "
            "Fill missing or ambiguous values with defaults: null for missing values. "
            "Ignore duplicates and partial repeats. "
            "Always return one valid JSON, never throw errors or return multiple objects."
            "Output: A single well-formed JSON object, and nothing else."
        ),
        output_schema=[  # Fixed schema types to match expected format
            {"name": "summary", "type": "str", "description": "Key summary of the content", "multiple": False},
            {"name": "topics", "type": "list", "description": "Main topics covered", "multiple": False},
            {"name": "source_url", "type": "str", "description": "Source URL of the content", "multiple": False},
        ],
    )

    # Connect the feedback loop - StructuredOutput back to Loop item input
    # Note: 'item' is a special dynamic input for LoopComponent feedback loops
    loop_component.set(item=structured_output.build_structured_output)
    # Create ChatOutput component to display final results
    chat_output = ChatOutput()
    chat_output.set(input_value=loop_component.done_output)

    return Graph(start=url_component, end=chat_output)


@pytest.mark.xfail
async def test_loop_flow():
    """Test that loop_flow creates a working graph with proper loop feedback connection."""
    flow = loop_flow()
    assert flow is not None
    assert flow._start is not None
    assert flow._end is not None

    # Verify all expected components are present
    expected_vertices = {
        "URLComponent",
        "SplitTextComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "OpenAIModelComponent",
        "StructuredOutputComponent",
        "ChatOutput",
    }

    assert all(vertex.id.split("-")[0] in expected_vertices for vertex in flow.vertices)

    expected_execution_order = [
        "OpenAIModelComponent",
        "URLComponent",
        "SplitTextComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "StructuredOutputComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "StructuredOutputComponent",
        "LoopComponent",
        "ParserComponent",
        "PromptComponent",
        "StructuredOutputComponent",
        "LoopComponent",
        "ChatOutput",
    ]
    results = [result async for result in flow.async_start()]
    result_order = [result.vertex.id.split("-")[0] for result in results if hasattr(result, "vertex")]
    assert result_order == expected_execution_order


class TestLoopComponentSubgraphExecution:
    """Tests for the new subgraph-based loop execution implementation."""

    def test_loop_component_initialization(self):
        """Test that LoopComponent initializes correctly with data."""
        from lfx.schema.dataframe import DataFrame

        data_list = [Data(text="item1"), Data(text="item2"), Data(text="item3")]
        loop = LoopComponent()
        loop.set(data=DataFrame(data_list))

        assert hasattr(loop, "initialize_data")
        assert hasattr(loop, "get_loop_body_vertices")

    def test_validate_data_with_dataframe(self):
        """Test that _validate_data correctly handles DataFrame input."""
        from lfx.schema.dataframe import DataFrame

        data_list = [Data(text="item1"), Data(text="item2")]
        df = DataFrame(data_list)

        loop = LoopComponent()
        validated = loop._validate_data(df)

        assert isinstance(validated, list)
        assert len(validated) == 2
        assert all(isinstance(item, Data) for item in validated)

    def test_validate_data_with_single_data(self):
        """Test that _validate_data correctly handles single Data input."""
        single_data = Data(text="single item")

        loop = LoopComponent()
        validated = loop._validate_data(single_data)

        assert isinstance(validated, list)
        assert len(validated) == 1
        assert validated[0] == single_data

    def test_validate_data_with_list(self):
        """Test that _validate_data correctly handles list of Data input."""
        data_list = [Data(text="item1"), Data(text="item2")]

        loop = LoopComponent()
        validated = loop._validate_data(data_list)

        assert isinstance(validated, list)
        assert len(validated) == 2
        assert validated == data_list

    def test_validate_data_with_invalid_input(self):
        """Test that _validate_data raises TypeError for invalid input."""
        loop = LoopComponent()

        with pytest.raises(TypeError, match="must be a DataFrame"):
            loop._validate_data("invalid input")

        with pytest.raises(TypeError, match="must be a DataFrame"):
            loop._validate_data([1, 2, 3])

    def test_get_loop_body_vertices_without_vertex(self):
        """Test that get_loop_body_vertices returns empty set when no vertex context."""
        loop = LoopComponent()

        # Without _vertex attribute, should return empty set
        result = loop.get_loop_body_vertices()

        assert result == set()

    def test_get_loop_body_start_vertex_without_vertex(self):
        """Test that _get_loop_body_start_vertex returns None when no vertex context."""
        loop = LoopComponent()

        # Without _vertex attribute, should return None
        result = loop._get_loop_body_start_vertex()

        assert result is None

    def test_extract_loop_output_with_empty_results(self):
        """Test that _extract_loop_output handles empty results."""
        from unittest.mock import patch

        loop = LoopComponent()

        # Mock get_incoming_edge_by_target_param to return None
        with patch.object(loop, "get_incoming_edge_by_target_param", return_value=None):
            result = loop._extract_loop_output([])

            assert isinstance(result, Data)
            assert result.text == ""

    def test_component_has_subgraph_methods(self):
        """Test that LoopComponent has the new subgraph execution methods."""
        loop = LoopComponent()

        # Check that new methods exist
        assert hasattr(loop, "get_loop_body_vertices")
        assert hasattr(loop, "execute_loop_body")
        assert hasattr(loop, "_get_loop_body_start_vertex")
        assert hasattr(loop, "_extract_loop_output")

        # Check that methods are callable
        assert callable(loop.get_loop_body_vertices)
        assert callable(loop.execute_loop_body)
        assert callable(loop._get_loop_body_start_vertex)
        assert callable(loop._extract_loop_output)

    async def test_event_manager_passed_to_subgraph(self):
        """Test that event_manager is properly passed to subgraph execution."""
        from contextlib import asynccontextmanager
        from unittest.mock import MagicMock, patch

        from lfx.schema.dataframe import DataFrame

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

        # Now test with actual loop body vertices
        # Track whether event_manager was passed correctly
        event_manager_received = []

        # Create an async generator that yields mock results
        async def mock_async_start(event_manager=None):
            event_manager_received.append(event_manager)
            yield MagicMock(valid=True, result_dict={"outputs": {}})

        mock_subgraph = MagicMock()
        mock_subgraph.prepare = MagicMock()
        mock_subgraph.async_start = mock_async_start
        mock_subgraph._vertices = []  # Empty list for iteration
        mock_subgraph.get_vertex = MagicMock(return_value=MagicMock(update_raw_params=MagicMock()))

        # Create async context manager for create_subgraph
        @asynccontextmanager
        async def mock_create_subgraph(vertex_ids):  # noqa: ARG001
            yield mock_subgraph

        with (
            patch.object(loop, "get_loop_body_vertices", return_value={"vertex1"}),
            patch.object(loop, "_get_loop_body_start_vertex", return_value="vertex1"),
            patch.object(loop.graph, "create_subgraph", mock_create_subgraph),
        ):
            result = await loop.execute_loop_body(data_list, event_manager=mock_event_manager)

            # Should have processed all items (one call per item)
            assert len(event_manager_received) == 2
            # Verify event_manager was passed correctly to each iteration
            assert all(em is mock_event_manager for em in event_manager_received)

    async def test_done_output_passes_event_manager(self):
        """Test that done_output properly passes event_manager to execute_loop_body."""
        from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

        from lfx.schema.dataframe import DataFrame

        # Create a mock event manager
        mock_event_manager = MagicMock()

        # Create loop component
        loop = LoopComponent()
        data_list = [Data(text="item1")]
        loop.set(data=DataFrame(data_list))
        loop._id = "test_loop"
        # Set the event manager as an instance attribute (this is how it's accessed in done_output)
        loop._event_manager = mock_event_manager

        # Mock execute_loop_body to return expected data
        mock_execute = AsyncMock(return_value=[Data(text="result")])

        # Mock initialize_data to set up the context with data
        def mock_initialize_data():
            # Simulate what initialize_data does - set up context with data
            pass

        # Create a mock context that returns data_list when get is called
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

    def test_get_loop_body_vertices_simple_loop(self):
        """Test get_loop_body_vertices with a simple loop structure."""
        from unittest.mock import MagicMock, PropertyMock, patch

        # Create loop component
        loop = LoopComponent()

        # Mock the vertex and graph structure for a simple loop:
        # Loop -> ComponentA -> ComponentB -> back to Loop
        mock_vertex = MagicMock()
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "component_a"
        mock_vertex.outgoing_edges = [mock_edge]

        mock_graph = MagicMock()
        mock_graph.successor_map = {"component_a": ["component_b"], "component_b": ["loop_end"], "loop_end": []}

        loop._vertex = mock_vertex

        # Mock get_incoming_edge_by_target_param to return the end vertex
        with (
            patch.object(loop, "get_incoming_edge_by_target_param", return_value="loop_end"),
            patch.object(type(loop), "graph", new_callable=PropertyMock, return_value=mock_graph),
        ):
            result = loop.get_loop_body_vertices()

            # Should include all vertices in the loop body
            assert "component_a" in result
            assert "component_b" in result
            assert "loop_end" in result
            assert len(result) == 3

    def test_get_loop_body_vertices_complex_loop(self):
        """Test get_loop_body_vertices with a complex loop structure with branches."""
        from unittest.mock import MagicMock, PropertyMock, patch

        # Create loop component
        loop = LoopComponent()

        # Mock a complex loop structure:
        # Loop -> A -> B -> D -> End
        #           -> C -> D
        mock_vertex = MagicMock()
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "component_a"
        mock_vertex.outgoing_edges = [mock_edge]

        mock_graph = MagicMock()
        mock_graph.successor_map = {
            "component_a": ["component_b", "component_c"],
            "component_b": ["component_d"],
            "component_c": ["component_d"],
            "component_d": ["loop_end"],
            "loop_end": [],
        }

        loop._vertex = mock_vertex

        # Mock get_incoming_edge_by_target_param to return the end vertex
        with (
            patch.object(loop, "get_incoming_edge_by_target_param", return_value="loop_end"),
            patch.object(type(loop), "graph", new_callable=PropertyMock, return_value=mock_graph),
        ):
            result = loop.get_loop_body_vertices()

            # Should include all vertices in the loop body including branches
            assert "component_a" in result
            assert "component_b" in result
            assert "component_c" in result
            assert "component_d" in result
            assert "loop_end" in result
            assert len(result) == 5

    def test_get_loop_body_vertices_no_outgoing_edges(self):
        """Test get_loop_body_vertices when loop has no outgoing edges."""
        from unittest.mock import MagicMock

        # Create loop component
        loop = LoopComponent()

        # Mock vertex with no outgoing edges
        mock_vertex = MagicMock()
        mock_vertex.outgoing_edges = []

        loop._vertex = mock_vertex

        result = loop.get_loop_body_vertices()

        # Should return empty set
        assert result == set()

    def test_get_loop_body_vertices_no_end_vertex(self):
        """Test get_loop_body_vertices when there's no vertex feeding back to item input."""
        from unittest.mock import MagicMock, patch

        # Create loop component
        loop = LoopComponent()

        # Mock vertex with outgoing edges
        mock_vertex = MagicMock()
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "component_a"
        mock_vertex.outgoing_edges = [mock_edge]

        loop._vertex = mock_vertex

        # Mock get_incoming_edge_by_target_param to return None (no end vertex)
        with patch.object(loop, "get_incoming_edge_by_target_param", return_value=None):
            result = loop.get_loop_body_vertices()

            # Should return empty set
            assert result == set()

    def test_get_loop_body_vertices_with_cycle(self):
        """Test get_loop_body_vertices with a cycle in the loop body."""
        from unittest.mock import MagicMock, PropertyMock, patch

        # Create loop component
        loop = LoopComponent()

        # Mock a loop structure with internal cycle:
        # Loop -> A -> B -> C -> B (cycle) -> D -> End
        mock_vertex = MagicMock()
        mock_edge = MagicMock()
        mock_edge.source_handle.name = "item"
        mock_edge.target_id = "component_a"
        mock_vertex.outgoing_edges = [mock_edge]

        mock_graph = MagicMock()
        mock_graph.successor_map = {
            "component_a": ["component_b"],
            "component_b": ["component_c"],
            "component_c": ["component_b", "component_d"],  # Cycle back to B
            "component_d": ["loop_end"],
            "loop_end": [],
        }

        loop._vertex = mock_vertex

        # Mock get_incoming_edge_by_target_param to return the end vertex
        with (
            patch.object(loop, "get_incoming_edge_by_target_param", return_value="loop_end"),
            patch.object(type(loop), "graph", new_callable=PropertyMock, return_value=mock_graph),
        ):
            result = loop.get_loop_body_vertices()

            # Should handle cycle correctly and include all vertices
            assert "component_a" in result
            assert "component_b" in result
            assert "component_c" in result
            assert "component_d" in result
            assert "loop_end" in result
            assert len(result) == 5
