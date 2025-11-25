from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from lfx.graph.graph.base import Graph
from lfx.helpers.flow import (
    build_schema_from_inputs,
    get_arg_names,
    get_flow_by_id_or_name,
    get_flow_inputs,
    list_flows,
    list_flows_by_flow_folder,
    list_flows_by_folder_id,
    load_flow,
    run_flow,
)
from lfx.schema.schema import INPUT_FIELD_NAME


class TestGetFlowInputs:
    """Test get_flow_inputs function."""

    def test_get_flow_inputs_returns_input_vertices(self):
        """Test that get_flow_inputs returns only input vertices."""
        mock_input1 = MagicMock()
        mock_input1.is_input = True

        mock_input2 = MagicMock()
        mock_input2.is_input = True

        mock_output = MagicMock()
        mock_output.is_input = False

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = [mock_input1, mock_output, mock_input2]

        result = get_flow_inputs(mock_graph)

        assert len(result) == 2
        assert mock_input1 in result
        assert mock_input2 in result
        assert mock_output not in result


class TestBuildSchemaFromInputs:
    """Test build_schema_from_inputs function."""

    def test_build_schema_creates_model_with_fields(self):
        """Test that build_schema_from_inputs creates a Pydantic model."""
        mock_input1 = MagicMock()
        mock_input1.display_name = "User Name"
        mock_input1.description = "The user's name"

        mock_input2 = MagicMock()
        mock_input2.display_name = "User Email"
        mock_input2.description = "The user's email"

        schema = build_schema_from_inputs("TestSchema", [mock_input1, mock_input2])

        assert schema.__name__ == "TestSchema"
        assert hasattr(schema, "model_fields")
        assert "user_name" in schema.model_fields
        assert "user_email" in schema.model_fields


class TestGetArgNames:
    """Test get_arg_names function."""

    def test_get_arg_names_returns_component_and_arg_names(self):
        """Test that get_arg_names returns list of component/arg name dicts."""
        mock_input1 = MagicMock()
        mock_input1.display_name = "User Name"

        mock_input2 = MagicMock()
        mock_input2.display_name = "User Email"

        result = get_arg_names([mock_input1, mock_input2])

        assert len(result) == 2
        assert result[0] == {"component_name": "User Name", "arg_name": "user_name"}
        assert result[1] == {"component_name": "User Email", "arg_name": "user_email"}


class TestListFlows:
    """Test list_flows function."""

    @pytest.mark.asyncio
    async def test_list_flows_raises_error_without_user_id(self):
        """Test that list_flows raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await list_flows(user_id=None)

    @pytest.mark.asyncio
    async def test_list_flows_returns_empty_list_in_lfx(self):
        """Test that list_flows returns empty list (stub implementation)."""
        result = await list_flows(user_id=str(uuid4()))

        assert result == []


class TestListFlowsByFlowFolder:
    """Test list_flows_by_flow_folder function."""

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_raises_error_without_user_id(self):
        """Test that function raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await list_flows_by_flow_folder(user_id=None, flow_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_raises_error_without_flow_id(self):
        """Test that function raises ValueError without flow_id."""
        with pytest.raises(ValueError, match="Flow ID is required"):
            await list_flows_by_flow_folder(user_id=str(uuid4()), flow_id=None)

    @pytest.mark.asyncio
    async def test_list_flows_by_flow_folder_returns_empty_list_in_lfx(self):
        """Test that function returns empty list (stub implementation)."""
        result = await list_flows_by_flow_folder(user_id=str(uuid4()), flow_id=str(uuid4()))

        assert result == []


class TestListFlowsByFolderId:
    """Test list_flows_by_folder_id function."""

    @pytest.mark.asyncio
    async def test_list_flows_by_folder_id_raises_error_without_user_id(self):
        """Test that function raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await list_flows_by_folder_id(user_id=None, folder_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_list_flows_by_folder_id_raises_error_without_folder_id(self):
        """Test that function raises ValueError without folder_id."""
        with pytest.raises(ValueError, match="Folder ID is required"):
            await list_flows_by_folder_id(user_id=str(uuid4()), folder_id=None)

    @pytest.mark.asyncio
    async def test_list_flows_by_folder_id_returns_empty_list_in_lfx(self):
        """Test that function returns empty list (stub implementation)."""
        result = await list_flows_by_folder_id(user_id=str(uuid4()), folder_id=str(uuid4()))

        assert result == []


class TestGetFlowByIdOrName:
    """Test get_flow_by_id_or_name function."""

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_raises_error_without_user_id(self):
        """Test that function raises ValueError without user_id."""
        with pytest.raises(ValueError, match="Session is invalid"):
            await get_flow_by_id_or_name(user_id="", flow_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_raises_error_without_id_or_name(self):
        """Test that function raises ValueError without flow_id or flow_name."""
        with pytest.raises(ValueError, match="Flow ID or Flow Name is required"):
            await get_flow_by_id_or_name(user_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_get_flow_by_id_or_name_returns_none_in_lfx(self):
        """Test that function returns None (stub implementation)."""
        result = await get_flow_by_id_or_name(user_id=str(uuid4()), flow_id=str(uuid4()))

        assert result is None


class TestLoadFlow:
    """Test load_flow function."""

    @pytest.mark.asyncio
    async def test_load_flow_raises_not_implemented_error(self):
        """Test that load_flow raises NotImplementedError in lfx."""
        with pytest.raises(NotImplementedError, match="load_flow not implemented"):
            await load_flow(user_id=str(uuid4()), flow_id=str(uuid4()))


class TestRunFlow:
    """Test run_flow function."""

    @pytest.mark.asyncio
    async def test_run_flow_raises_error_without_user_id(self):
        """Test that run_flow raises ValueError without user_id."""
        mock_graph = MagicMock(spec=Graph)

        with pytest.raises(ValueError, match="Session is invalid"):
            await run_flow(user_id=None, graph=mock_graph)

    @pytest.mark.asyncio
    async def test_run_flow_raises_error_without_graph(self):
        """Test that run_flow raises ValueError without graph in lfx."""
        with pytest.raises(ValueError, match="run_flow requires a graph parameter"):
            await run_flow(user_id=str(uuid4()), graph=None)

    @pytest.mark.asyncio
    async def test_run_flow_sets_graph_properties(self):
        """Test that run_flow sets graph properties correctly."""
        user_id = str(uuid4())
        run_id = str(uuid4())
        session_id = "test_session"

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []
        mock_graph.arun = AsyncMock(return_value=[])

        await run_flow(user_id=user_id, run_id=run_id, session_id=session_id, graph=mock_graph)

        mock_graph.set_run_id.assert_called_once_with(UUID(run_id))
        assert mock_graph.session_id == session_id
        assert mock_graph.user_id == user_id

    @pytest.mark.asyncio
    async def test_run_flow_calls_graph_arun_with_inputs(self):
        """Test that run_flow calls graph.arun with correct inputs."""
        user_id = str(uuid4())
        inputs = [
            {"components": ["comp1"], "input_value": "test1", "type": "chat"},
            {"components": ["comp2"], "input_value": "test2"},
        ]

        mock_output_vertex = MagicMock()
        mock_output_vertex.id = "output1"
        mock_output_vertex.is_output = True

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = [mock_output_vertex]
        mock_graph.arun = AsyncMock(return_value=[])

        await run_flow(user_id=user_id, inputs=inputs, graph=mock_graph, output_type="chat")

        mock_graph.arun.assert_called_once()
        call_args = mock_graph.arun.call_args

        # Check inputs_list
        assert len(call_args[0][0]) == 2
        assert INPUT_FIELD_NAME in call_args[0][0][0]
        assert call_args[0][0][0][INPUT_FIELD_NAME] == "test1"

        # Check inputs_components
        assert call_args[1]["inputs_components"] == [["comp1"], ["comp2"]]

        # Check types
        assert call_args[1]["types"] == ["chat", "chat"]

    @pytest.mark.asyncio
    async def test_run_flow_converts_dict_input_to_list(self):
        """Test that run_flow converts dict input to list."""
        user_id = str(uuid4())
        inputs = {"components": ["comp1"], "input_value": "test"}

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []
        mock_graph.arun = AsyncMock(return_value=[])

        await run_flow(user_id=user_id, inputs=inputs, graph=mock_graph)

        call_args = mock_graph.arun.call_args
        assert len(call_args[0][0]) == 1  # Converted to list with one element
