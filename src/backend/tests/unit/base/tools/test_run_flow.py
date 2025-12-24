from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch
from uuid import uuid4

import pytest
from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.graph.graph.base import Graph
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.services.cache.utils import CacheMiss
from lfx.template.field.base import Output


@pytest.fixture
def mock_shared_cache():
    """Mock the shared component cache service."""
    with patch("lfx.base.tools.run_flow.get_shared_component_cache_service") as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock()
        mock_cache.set = AsyncMock()
        mock_cache.delete = AsyncMock()
        mock_get_cache.return_value = mock_cache
        yield mock_cache


class TestRunFlowBaseComponentInitialization:
    """Test RunFlowBaseComponent initialization."""

    def test_init_creates_cache_service(self):
        """Test that __init__ creates the shared component cache service."""
        with patch("lfx.base.tools.run_flow.get_shared_component_cache_service") as mock_get_cache:
            mock_cache = MagicMock()
            mock_get_cache.return_value = mock_cache

            component = RunFlowBaseComponent()

            assert hasattr(component, "_shared_component_cache")
            assert component._shared_component_cache is not None
            assert component._shared_component_cache == mock_cache

    def test_init_creates_cache_dispatcher(self):
        """Test that __init__ creates the cache flow dispatcher."""
        component = RunFlowBaseComponent()

        assert hasattr(component, "_cache_flow_dispatcher")
        assert isinstance(component._cache_flow_dispatcher, dict)
        assert "get" in component._cache_flow_dispatcher
        assert "set" in component._cache_flow_dispatcher
        assert "delete" in component._cache_flow_dispatcher
        assert "_build_key" in component._cache_flow_dispatcher
        assert "_build_graph" in component._cache_flow_dispatcher

    def test_init_sets_last_run_outputs_to_none(self):
        """Test that __init__ sets _last_run_outputs to None."""
        component = RunFlowBaseComponent()

        assert hasattr(component, "_last_run_outputs")
        assert component._last_run_outputs is None

    def test_init_sets_add_tool_output_flag(self):
        """Test that __init__ sets add_tool_output to True."""
        component = RunFlowBaseComponent()

        assert component.add_tool_output is True


class TestRunFlowBaseComponentFlowRetrieval:
    """Test flow retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_flow_with_id(self):
        """Test getting a flow by ID."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        flow_id = str(uuid4())
        expected_flow = Data(data={"name": "test_flow"})

        with patch("lfx.base.tools.run_flow.get_flow_by_id_or_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = expected_flow

            result = await component.get_flow(flow_id_selected=flow_id)

            assert result == expected_flow
            mock_get.assert_called_once_with(
                user_id=component._user_id,
                flow_id=flow_id,
                flow_name=None,
            )

    @pytest.mark.asyncio
    async def test_get_flow_with_name(self):
        """Test getting a flow by name."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        flow_name = "test_flow"
        expected_flow = Data(data={"name": flow_name})

        with patch("lfx.base.tools.run_flow.get_flow_by_id_or_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = expected_flow

            result = await component.get_flow(flow_name_selected=flow_name)

            assert result == expected_flow
            mock_get.assert_called_once_with(
                user_id=component._user_id,
                flow_id=None,
                flow_name=flow_name,
            )

    @pytest.mark.asyncio
    async def test_get_flow_returns_empty_data_when_none(self):
        """Test that get_flow returns empty Data when flow is not found."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())

        with patch("lfx.base.tools.run_flow.get_flow_by_id_or_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await component.get_flow(flow_id_selected=str(uuid4()))

            assert isinstance(result, Data)
            assert result.data == {}

    @pytest.mark.asyncio
    async def test_get_graph_raises_error_without_id_or_name(self):
        """Test that get_graph raises ValueError when neither ID nor name is provided."""
        component = RunFlowBaseComponent()

        with pytest.raises(ValueError, match="Flow name or id is required"):
            await component.get_graph()

    @pytest.mark.asyncio
    async def test_get_graph_uses_cache_when_available_and_up_to_date(self):
        """Test that get_graph returns cached graph when available and up-to-date."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.cache_flow = True
        flow_id = str(uuid4())
        updated_at = "2024-01-01T00:00:00Z"

        mock_graph = MagicMock(spec=Graph)
        mock_graph.updated_at = updated_at

        with (
            patch.object(component, "_flow_cache_call") as mock_cache_call,
            patch.object(component, "_is_cached_flow_up_to_date") as mock_is_up_to_date,
        ):
            mock_cache_call.return_value = mock_graph
            mock_is_up_to_date.return_value = True

            result = await component.get_graph(flow_id_selected=flow_id, updated_at=updated_at)

            assert result == mock_graph
            mock_cache_call.assert_called_once_with("get", flow_id=flow_id)
            mock_is_up_to_date.assert_called_once_with(mock_graph, updated_at)

    @pytest.mark.asyncio
    async def test_get_graph_fetches_and_caches_when_not_cached(self):
        """Test that get_graph fetches flow and caches it when not in cache."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.cache_flow = True
        flow_name = "test_flow"
        flow_id = str(uuid4())

        flow_data = Data(data={"data": {"nodes": [], "edges": []}, "description": "Test flow"})

        mock_graph = MagicMock(spec=Graph)

        with (
            patch.object(component, "_flow_cache_call") as mock_cache_call,
            patch.object(component, "get_flow", new_callable=AsyncMock) as mock_get_flow,
            patch("lfx.base.tools.run_flow.Graph.from_payload") as mock_from_payload,
        ):
            mock_cache_call.return_value = None  # Not in cache
            mock_get_flow.return_value = flow_data
            mock_from_payload.return_value = mock_graph

            result = await component.get_graph(flow_name_selected=flow_name, flow_id_selected=flow_id)

            assert result == mock_graph
            mock_get_flow.assert_called_once_with(flow_name_selected=flow_name, flow_id_selected=flow_id)
            mock_from_payload.assert_called_once()
            # Verify cache set was called
            assert mock_cache_call.call_count == 2  # get and set

    @pytest.mark.asyncio
    async def test_get_graph_deletes_stale_cache_and_refetches(self):
        """Test that get_graph deletes stale cached graph and fetches fresh one."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.cache_flow = True
        flow_id = str(uuid4())
        old_updated_at = "2024-01-01T00:00:00Z"
        new_updated_at = "2024-01-02T00:00:00Z"

        stale_graph = MagicMock(spec=Graph)
        stale_graph.updated_at = old_updated_at

        flow_data = Data(
            data={"data": {"nodes": [], "edges": []}, "description": "Test flow", "updated_at": new_updated_at}
        )

        fresh_graph = MagicMock(spec=Graph)
        fresh_graph.updated_at = new_updated_at

        with (
            patch.object(component, "_flow_cache_call") as mock_cache_call,
            patch.object(component, "_is_cached_flow_up_to_date") as mock_is_up_to_date,
            patch.object(component, "get_flow", new_callable=AsyncMock) as mock_get_flow,
            patch("lfx.base.tools.run_flow.Graph.from_payload") as mock_from_payload,
        ):
            # First call returns stale graph, second call is delete, third call is set
            mock_cache_call.side_effect = [stale_graph, None, None]
            mock_is_up_to_date.return_value = False  # Cache is stale
            mock_get_flow.return_value = flow_data
            mock_from_payload.return_value = fresh_graph

            result = await component.get_graph(flow_id_selected=flow_id, updated_at=new_updated_at)

            assert result == fresh_graph
            # Should have called cache "get", "delete", and "set"
            assert mock_cache_call.call_count == 3


class TestRunFlowBaseComponentFlowCaching:
    """Test flow caching methods."""

    def test_build_flow_cache_key_with_flow_id(self):
        """Test building cache key with flow ID."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        flow_id = str(uuid4())

        key = component._build_flow_cache_key(flow_id=flow_id)

        assert f"run_flow:{component._user_id}:{flow_id}" == key

    @patch.object(RunFlowBaseComponent, "user_id", new_callable=PropertyMock, return_value=None)
    def test_build_flow_cache_key_without_user_id_raises_error(self, mock_user_id):  # noqa: ARG002
        """Test that building cache key without user_id raises ValueError."""
        component = RunFlowBaseComponent()

        with pytest.raises(ValueError, match="Flow ID and user ID are required"):
            component._build_flow_cache_key(flow_id=str(uuid4()))

    def test_build_flow_cache_key_without_flow_id_raises_error(self):
        """Test that building cache key without flow_id raises ValueError."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())

        with pytest.raises(ValueError, match="Flow ID and user ID are required"):
            component._build_flow_cache_key(flow_id=None)

    def test_flow_cache_call_returns_none_when_cache_disabled(self):
        """Test that _flow_cache_call returns None when cache_flow is False."""
        component = RunFlowBaseComponent()
        component.cache_flow = False

        result = component._flow_cache_call("get", flow_name="test")

        assert result is None

    def test_flow_cache_call_returns_none_when_cache_service_unavailable(self):
        """Test that _flow_cache_call returns None when cache service is None."""
        component = RunFlowBaseComponent()
        component.cache_flow = True
        component._shared_component_cache = None

        result = component._flow_cache_call("get", flow_name="test")

        assert result is None

    def test_flow_cache_call_raises_error_for_unknown_action(self):
        """Test that _flow_cache_call raises ValueError for unknown action."""
        component = RunFlowBaseComponent()
        component.cache_flow = True

        with pytest.raises(ValueError, match="Unknown cache action"):
            component._flow_cache_call("invalid_action")

    def test_get_cached_flow_returns_none_on_cache_miss(self):
        """Test that _get_cached_flow returns None on cache miss."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.cache_flow = True
        flow_id = str(uuid4())

        mock_cache_miss = MagicMock(spec=CacheMiss)
        component._shared_component_cache = MagicMock()
        component._shared_component_cache.get = Mock(return_value=mock_cache_miss)

        with patch.object(component, "_build_flow_cache_key") as mock_build_key:
            mock_build_key.return_value = "test_key"

            result = component._get_cached_flow(flow_id=flow_id)

            assert result is None

    def test_set_cached_flow_stores_graph_data(self):
        """Test that _set_cached_flow stores graph data in cache."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.cache_flow = True

        mock_graph = MagicMock(spec=Graph)
        mock_graph.flow_name = "test_flow"
        mock_graph.flow_id = str(uuid4())
        mock_graph.description = "Test description"
        mock_graph.updated_at = "2024-01-01T12:00:00Z"
        mock_graph.dump = Mock(return_value={"name": "test_flow"})

        component._shared_component_cache = MagicMock()
        component._shared_component_cache.set = Mock()

        with patch.object(component, "_build_flow_cache_key") as mock_build_key:
            mock_build_key.return_value = "test_key"

            component._set_cached_flow(flow=mock_graph)

            component._shared_component_cache.set.assert_called_once()
            args = component._shared_component_cache.set.call_args[0]
            assert args[0] == "test_key"
            assert "graph_dump" in args[1]
            assert "flow_id" in args[1]
            assert "user_id" in args[1]

    def test_is_cached_flow_up_to_date_returns_true_for_same_timestamp(self):
        """Test that cached flow is considered up-to-date with same timestamp."""
        component = RunFlowBaseComponent()

        cached_graph = MagicMock(spec=Graph)
        cached_graph.updated_at = "2024-01-01T12:00:00Z"

        updated_at = "2024-01-01T12:00:00Z"

        result = component._is_cached_flow_up_to_date(cached_graph, updated_at)

        assert result is True

    def test_is_cached_flow_up_to_date_returns_true_for_newer_cache(self):
        """Test that cached flow is considered up-to-date when cache is newer."""
        component = RunFlowBaseComponent()

        cached_graph = MagicMock(spec=Graph)
        cached_graph.updated_at = "2024-01-02T12:00:00Z"

        updated_at = "2024-01-01T12:00:00Z"

        result = component._is_cached_flow_up_to_date(cached_graph, updated_at)

        assert result is True

    def test_is_cached_flow_up_to_date_returns_false_for_older_cache(self):
        """Test that cached flow is considered stale when cache is older."""
        component = RunFlowBaseComponent()

        cached_graph = MagicMock(spec=Graph)
        cached_graph.updated_at = "2024-01-01T12:00:00Z"

        updated_at = "2024-01-02T12:00:00Z"

        result = component._is_cached_flow_up_to_date(cached_graph, updated_at)

        assert result is False

    def test_is_cached_flow_up_to_date_returns_false_when_updated_at_missing(self):
        """Test that cached flow is considered stale when updated_at is None."""
        component = RunFlowBaseComponent()

        cached_graph = MagicMock(spec=Graph)
        cached_graph.updated_at = "2024-01-01T12:00:00Z"

        result = component._is_cached_flow_up_to_date(cached_graph, None)

        assert result is False

    def test_is_cached_flow_up_to_date_returns_false_when_cached_timestamp_missing(self):
        """Test that cached flow is considered stale when cached updated_at is None."""
        component = RunFlowBaseComponent()

        cached_graph = MagicMock(spec=Graph)
        cached_graph.updated_at = None

        updated_at = "2024-01-01T12:00:00Z"

        result = component._is_cached_flow_up_to_date(cached_graph, updated_at)

        assert result is False

    def test_parse_timestamp_parses_iso_format(self):
        """Test parsing ISO format timestamp."""
        timestamp_str = "2024-01-01T12:34:56Z"

        result = RunFlowBaseComponent._parse_timestamp(timestamp_str)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 34
        assert result.second == 56
        assert result.microsecond == 0  # Should normalize microseconds

    def test_parse_timestamp_parses_iso_with_offset(self):
        """Test parsing ISO format timestamp with timezone offset."""
        timestamp_str = "2024-01-01T12:34:56+05:00"

        result = RunFlowBaseComponent._parse_timestamp(timestamp_str)

        assert result is not None
        assert result.year == 2024

    def test_parse_timestamp_returns_none_for_none(self):
        """Test that None input returns None."""
        result = RunFlowBaseComponent._parse_timestamp(None)

        assert result is None

    def test_parse_timestamp_returns_none_for_invalid_format(self):
        """Test that invalid timestamp format returns None."""
        result = RunFlowBaseComponent._parse_timestamp("invalid-timestamp")

        assert result is None


class TestRunFlowBaseComponentInputOutputHandling:
    """Test input/output handling methods."""

    def test_get_ioput_name_creates_unique_name(self):
        """Test that _get_ioput_name creates unique input/output name."""
        component = RunFlowBaseComponent()
        vertex_id = "vertex_123"
        ioput_name = "input_1"

        result = component._get_ioput_name(vertex_id, ioput_name)

        assert result == f"{vertex_id}{component.IOPUT_SEP}{ioput_name}"

    def test_get_ioput_name_raises_error_without_vertex_id(self):
        """Test that _get_ioput_name raises ValueError without vertex_id."""
        component = RunFlowBaseComponent()

        with pytest.raises(ValueError, match="Vertex ID and input/output name are required"):
            component._get_ioput_name("", "input_1")

    def test_get_ioput_name_raises_error_without_ioput_name(self):
        """Test that _get_ioput_name raises ValueError without ioput_name."""
        component = RunFlowBaseComponent()

        with pytest.raises(ValueError, match="Vertex ID and input/output name are required"):
            component._get_ioput_name("vertex_123", "")

    def test_extract_tweaks_from_keyed_values(self):
        """Test extracting tweaks from keyed values."""
        component = RunFlowBaseComponent()

        values = {
            "vertex1~param1": "value1",
            "vertex1~param2": "value2",
            "vertex2~param1": "value3",
            "invalid_key": "should_be_ignored",
        }

        tweaks = component._extract_tweaks_from_keyed_values(values)

        assert "vertex1" in tweaks
        assert tweaks["vertex1"]["param1"] == "value1"
        assert tweaks["vertex1"]["param2"] == "value2"
        assert "vertex2" in tweaks
        assert tweaks["vertex2"]["param1"] == "value3"
        assert "invalid_key" not in tweaks

    def test_build_inputs_from_tweaks(self):
        """Test building inputs from tweaks."""
        component = RunFlowBaseComponent()

        tweaks = {
            "vertex1": {"input_value": "test_input", "type": "chat"},
            "vertex2": {"input_value": "another_input"},
            "vertex3": {"other_param": "value"},  # Should be skipped
        }

        inputs = component._build_inputs_from_tweaks(tweaks)

        assert len(inputs) == 2
        assert inputs[0]["components"] == ["vertex1"]
        assert inputs[0]["input_value"] == "test_input"
        assert inputs[0]["type"] == "chat"
        assert inputs[1]["components"] == ["vertex2"]
        assert inputs[1]["input_value"] == "another_input"

    def test_format_flow_outputs_creates_output_objects(self):
        """Test that _format_flow_outputs creates Output objects from graph."""
        component = RunFlowBaseComponent()

        mock_vertex = MagicMock()
        mock_vertex.id = "vertex_123"
        mock_vertex.is_output = True
        mock_vertex.outputs = [
            {"name": "output1", "display_name": "Output 1"},
            {"name": "output2", "display_name": "Output 2"},
        ]

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = [mock_vertex]

        outputs = component._format_flow_outputs(mock_graph)

        assert len(outputs) == 2
        assert all(isinstance(output, Output) for output in outputs)
        assert outputs[0].name == f"vertex_123{component.IOPUT_SEP}output1"
        # The method name is dynamically generated with sanitized vertex and output names
        assert outputs[0].method == "_resolve_flow_output__vertex_123__output1"
        assert outputs[1].name == f"vertex_123{component.IOPUT_SEP}output2"
        assert outputs[1].method == "_resolve_flow_output__vertex_123__output2"

    def test_delete_fields_with_list(self):
        """Test deleting fields from build_config with list."""
        component = RunFlowBaseComponent()
        build_config = dotdict({"field1": "value1", "field2": "value2", "field3": "value3"})

        component.delete_fields(build_config, ["field1", "field3"])

        assert "field1" not in build_config
        assert "field2" in build_config
        assert "field3" not in build_config

    def test_delete_fields_with_dict(self):
        """Test deleting fields from build_config with dict."""
        component = RunFlowBaseComponent()
        build_config = dotdict({"field1": "value1", "field2": "value2"})

        component.delete_fields(build_config, {"field1": {}, "field2": {}})

        assert "field1" not in build_config
        assert "field2" not in build_config

    def test_update_input_types_sets_empty_list_for_none(self):
        """Test that update_input_types sets empty list for None or missing input_types."""
        component = RunFlowBaseComponent()

        fields = [
            dotdict({"name": "field1", "input_types": None}),
            dotdict({"name": "field2", "input_types": ["str"]}),
            dotdict({"name": "field3"}),  # No input_types key
        ]

        updated = component.update_input_types(fields)

        assert updated[0]["input_types"] == []
        assert updated[1]["input_types"] == ["str"]
        assert updated[2]["input_types"] == []  # Should be added as empty list


class TestRunFlowBaseComponentPreRunSetup:
    """Test pre-run setup methods."""

    def test_pre_run_setup_resets_last_run_outputs(self):
        """Test that _pre_run_setup resets _last_run_outputs."""
        from types import SimpleNamespace

        component = RunFlowBaseComponent()
        component._last_run_outputs = [MagicMock()]
        component._attributes = {}
        component._vertex = SimpleNamespace(data={"node": {}})

        component._pre_run_setup()

        assert component._last_run_outputs is None

    def test_pre_run_setup_builds_flow_tweak_data(self):
        """Test that _pre_run_setup builds flow_tweak_data."""
        from types import SimpleNamespace

        component = RunFlowBaseComponent()
        component._attributes = {
            "vertex1~param1": "value1",
            "vertex1~param2": "value2",
        }
        component._vertex = SimpleNamespace(data={"node": {}})

        component._pre_run_setup()

        assert hasattr(component, "flow_tweak_data")
        assert "vertex1" in component.flow_tweak_data
        assert component.flow_tweak_data["vertex1"]["param1"] == "value1"

    def test_pre_run_setup_builds_flow_run_inputs(self):
        """Test that _pre_run_setup builds _flow_run_inputs."""
        from types import SimpleNamespace

        component = RunFlowBaseComponent()
        component._attributes = {
            "vertex1~input_value": "test_input",
        }
        component._vertex = SimpleNamespace(data={"node": {}})

        component._pre_run_setup()

        assert hasattr(component, "_flow_run_inputs")
        assert len(component._flow_run_inputs) == 1
        assert component._flow_run_inputs[0]["components"] == ["vertex1"]


class TestRunFlowBaseComponentOutputMethods:
    """Test output methods."""

    @pytest.mark.asyncio
    async def test_resolve_flow_output_finds_correct_output(self):
        """Test that _resolve_flow_output finds the correct output."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.session_id = None
        component.flow_tweak_data = {}

        vertex_id = "vertex_123"
        output_name = "output1"
        expected_value = "test_value"

        mock_result = MagicMock()
        mock_result.component_id = vertex_id
        mock_result.results = {output_name: expected_value}

        mock_run_output = MagicMock()
        mock_run_output.outputs = [mock_result]

        with patch.object(component, "_get_cached_run_outputs", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [mock_run_output]

            result = await component._resolve_flow_output(vertex_id=vertex_id, output_name=output_name)

            assert result == expected_value


class TestRunFlowBaseComponentToolGeneration:
    """Test tool generation methods."""

    @pytest.mark.asyncio
    async def test_get_required_data_returns_description_and_fields(self):
        """Test that get_required_data returns flow description and tool-mode fields."""
        component = RunFlowBaseComponent()
        component._user_id = str(uuid4())
        component.flow_name_selected = "test_flow"
        component.flow_id_selected = str(uuid4())

        mock_graph = MagicMock(spec=Graph)
        mock_graph.description = "Test flow description"

        mock_vertex = MagicMock()
        mock_vertex.id = "vertex_1"
        mock_vertex.data = {
            "node": {
                "template": {
                    "input1": {"name": "input1", "display_name": "Input 1", "advanced": False},
                },
                "field_order": ["input1"],
            }
        }
        mock_graph.vertices = [mock_vertex]

        with patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph:
            mock_get_graph.return_value = mock_graph

            with patch.object(component, "get_new_fields_from_graph") as mock_get_fields:
                mock_get_fields.return_value = [dotdict({"name": "input1", "tool_mode": True, "input_types": None})]

                description, fields = await component.get_required_data()

                assert description == "Test flow description"
                assert len(fields) == 1
                assert fields[0]["name"] == "input1"
