import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from lfx.graph.graph.base import Graph
from lfx.helpers.flow import (
    _find_flow_in_project,
    _load_flow_from_file,
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
    async def test_should_allow_none_user_id_when_graph_provided(self):
        """Test that run_flow allows None user_id when graph is provided (lfx mode).

        In lfx standalone mode, user_id is optional when a graph is provided directly,
        since lfx doesn't require database authentication.
        """
        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []
        mock_graph.arun = AsyncMock(return_value=[])

        # Should NOT raise "Session is invalid" - user_id is optional with direct graph
        result = await run_flow(user_id=None, graph=mock_graph)
        assert result is not None

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


class TestLoadFlowFromFile:
    """Test _load_flow_from_file function for local file loading."""

    def test_should_return_none_when_file_does_not_exist(self):
        """Test that function returns None for non-existent file."""
        non_existent_path = Path("/non/existent/path/flow.json")

        result = _load_flow_from_file(non_existent_path)

        assert result is None

    def test_should_return_data_when_valid_json_flow_provided(self):
        """Test that function returns Data object for valid JSON flow."""
        flow_content = {
            "id": "test-flow-id",
            "name": "Test Flow",
            "description": "A test flow",
            "data": {"nodes": [], "edges": []},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(flow_content, f)
            temp_path = Path(f.name)

        try:
            result = _load_flow_from_file(temp_path)

            assert result is not None
            assert result.data["id"] == "test-flow-id"
            assert result.data["name"] == "Test Flow"
            assert result.data["description"] == "A test flow"
        finally:
            temp_path.unlink()

    def test_should_use_filename_as_id_when_id_not_in_json(self):
        """Test that function uses filename as ID when not provided in JSON."""
        flow_content = {"data": {"nodes": []}}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="my_flow_"
        ) as f:
            json.dump(flow_content, f)
            temp_path = Path(f.name)

        try:
            result = _load_flow_from_file(temp_path)

            assert result is not None
            assert result.data["id"] == temp_path.stem
            assert result.data["name"] == temp_path.stem
        finally:
            temp_path.unlink()

    def test_should_return_none_when_invalid_json_provided(self):
        """Test that function returns None for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            temp_path = Path(f.name)

        try:
            result = _load_flow_from_file(temp_path)

            assert result is None
        finally:
            temp_path.unlink()


class TestFindFlowInProject:
    """Test _find_flow_in_project function for project directory search."""

    def test_should_return_none_when_project_path_not_directory(self):
        """Test that function returns None when project_path is not a directory."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_file = Path(f.name)

        try:
            result = _find_flow_in_project(temp_file, flow_name="test")

            assert result is None
        finally:
            temp_file.unlink()

    def test_should_find_flow_when_filename_matches_flow_name(self):
        """Test that function finds flow by direct filename match."""
        flow_content = {
            "id": "flow-123",
            "name": "MyTestFlow",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "MyTestFlow.json"
            flow_path.write_text(json.dumps(flow_content))

            result = _find_flow_in_project(Path(temp_dir), flow_name="MyTestFlow")

            assert result is not None
            assert result.data["name"] == "MyTestFlow"

    def test_should_find_flow_when_filename_matches_flow_id(self):
        """Test that function finds flow by ID filename match."""
        flow_id = str(uuid4())
        flow_content = {
            "id": flow_id,
            "name": "Some Flow",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / f"{flow_id}.json"
            flow_path.write_text(json.dumps(flow_content))

            result = _find_flow_in_project(Path(temp_dir), flow_id=flow_id)

            assert result is not None
            assert result.data["id"] == flow_id

    def test_should_find_flow_when_content_matches_flow_name(self):
        """Test that function finds flow by searching JSON content for name."""
        flow_content = {
            "id": "flow-abc",
            "name": "HiddenFlow",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            # File has different name than flow name inside
            flow_path = Path(temp_dir) / "different_filename.json"
            flow_path.write_text(json.dumps(flow_content))

            result = _find_flow_in_project(Path(temp_dir), flow_name="HiddenFlow")

            assert result is not None
            assert result.data["name"] == "HiddenFlow"

    def test_should_find_flow_when_content_matches_flow_id(self):
        """Test that function finds flow by searching JSON content for ID."""
        flow_id = "unique-flow-id-123"
        flow_content = {
            "id": flow_id,
            "name": "Some Flow",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "random_name.json"
            flow_path.write_text(json.dumps(flow_content))

            result = _find_flow_in_project(Path(temp_dir), flow_id=flow_id)

            assert result is not None
            assert result.data["id"] == flow_id

    def test_should_return_none_when_flow_not_found(self):
        """Test that function returns None when flow not found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some flows but not the one we're looking for
            other_flow = Path(temp_dir) / "other_flow.json"
            other_flow.write_text(json.dumps({"id": "other", "name": "Other"}))

            result = _find_flow_in_project(Path(temp_dir), flow_name="NonExistent")

            assert result is None


class TestGetFlowByIdOrNameWithProjectPath:
    """Test get_flow_by_id_or_name with project_path parameter (lfx local mode)."""

    @pytest.mark.asyncio
    async def test_should_find_flow_when_project_path_provided(self):
        """Test that function finds flow in local project directory."""
        flow_content = {
            "id": "local-flow-id",
            "name": "LocalFlow",
            "description": "A local flow",
            "data": {"nodes": [], "edges": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "LocalFlow.json"
            flow_path.write_text(json.dumps(flow_content))

            result = await get_flow_by_id_or_name(
                flow_name="LocalFlow",
                project_path=Path(temp_dir),
            )

            assert result is not None
            assert result.data["name"] == "LocalFlow"
            assert result.data["id"] == "local-flow-id"

    @pytest.mark.asyncio
    async def test_should_accept_string_project_path(self):
        """Test that function accepts string project_path and converts to Path."""
        flow_content = {
            "id": "string-path-flow",
            "name": "StringPathFlow",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "StringPathFlow.json"
            flow_path.write_text(json.dumps(flow_content))

            # Pass as string instead of Path
            result = await get_flow_by_id_or_name(
                flow_name="StringPathFlow",
                project_path=temp_dir,  # String path
            )

            assert result is not None
            assert result.data["name"] == "StringPathFlow"

    @pytest.mark.asyncio
    async def test_should_return_none_when_flow_not_found_in_project(self):
        """Test that function returns None when flow not in project directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await get_flow_by_id_or_name(
                flow_name="NonExistentFlow",
                project_path=Path(temp_dir),
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_should_not_require_user_id_when_project_path_provided(self):
        """Test that user_id is not required when using project_path."""
        flow_content = {
            "id": "no-user-flow",
            "name": "NoUserFlow",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / "NoUserFlow.json"
            flow_path.write_text(json.dumps(flow_content))

            # Should not raise "Session is invalid" error
            result = await get_flow_by_id_or_name(
                user_id=None,  # No user_id
                flow_name="NoUserFlow",
                project_path=Path(temp_dir),
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_should_find_flow_by_id_when_project_path_provided(self):
        """Test that function finds flow by ID in local project directory."""
        flow_id = str(uuid4())
        flow_content = {
            "id": flow_id,
            "name": "FlowById",
            "data": {"nodes": []},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            flow_path = Path(temp_dir) / f"{flow_id}.json"
            flow_path.write_text(json.dumps(flow_content))

            result = await get_flow_by_id_or_name(
                flow_id=flow_id,
                project_path=Path(temp_dir),
            )

            assert result is not None
            assert result.data["id"] == flow_id
