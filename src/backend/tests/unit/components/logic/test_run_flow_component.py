from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.graph.graph.base import Graph
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message


class TestRunFlowComponentInitialization:
    """Test RunFlowComponent initialization."""

    def test_component_has_correct_metadata(self):
        """Test that component has correct display name, description, etc."""
        assert RunFlowComponent.display_name == "Run Flow"
        assert "Executes another flow from within the same project." in RunFlowComponent.description
        assert RunFlowComponent.name == "RunFlow"
        assert RunFlowComponent.icon == "Workflow"
        assert RunFlowComponent.beta is True


class TestRunFlowComponentHelperMethods:
    """Test helper methods in RunFlowComponent."""

    def test_get_selected_flow_meta_returns_metadata_field(self):
        """Test that get_selected_flow_meta extracts the correct metadata field."""
        component = RunFlowComponent()

        flow_id = str(uuid4())
        updated_at = "2024-01-01T12:00:00Z"

        build_config = dotdict({"flow_name_selected": {"selected_metadata": {"id": flow_id, "updated_at": updated_at}}})

        result_id = component.get_selected_flow_meta(build_config, "id")
        result_updated_at = component.get_selected_flow_meta(build_config, "updated_at")

        assert result_id == flow_id
        assert result_updated_at == updated_at

    def test_get_selected_flow_meta_returns_none_when_missing(self):
        """Test that get_selected_flow_meta returns None for missing metadata."""
        component = RunFlowComponent()

        build_config = dotdict({"flow_name_selected": {"selected_metadata": {}}})

        result = component.get_selected_flow_meta(build_config, "nonexistent")

        assert result is None

    def test_get_selected_flow_meta_returns_none_when_no_metadata(self):
        """Test that get_selected_flow_meta returns None when no metadata exists."""
        component = RunFlowComponent()

        build_config = dotdict({})

        result = component.get_selected_flow_meta(build_config, "id")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_graph_and_update_cfg_loads_graph_and_updates_config(self):
        """Test that load_graph_and_update_cfg loads graph and updates build config."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())

        flow_id = str(uuid4())
        updated_at = "2024-01-01T12:00:00Z"
        build_config = dotdict({})

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with (
            patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph,
            patch.object(component, "update_build_config_from_graph") as mock_update_cfg,
        ):
            mock_get_graph.return_value = mock_graph

            await component.load_graph_and_update_cfg(build_config=build_config, flow_id=flow_id, updated_at=updated_at)

            mock_get_graph.assert_called_once_with(flow_id_selected=flow_id, updated_at=updated_at)
            mock_update_cfg.assert_called_once_with(build_config, mock_graph)

    @pytest.mark.asyncio
    async def test_load_graph_and_update_cfg_handles_datetime_object(self):
        """Test that load_graph_and_update_cfg handles datetime objects."""
        from datetime import datetime

        component = RunFlowComponent()
        component._user_id = str(uuid4())

        flow_id = str(uuid4())
        updated_at = datetime.fromisoformat("2024-01-01T12:00:00+00:00")
        build_config = dotdict({})

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with (
            patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph,
            patch.object(component, "update_build_config_from_graph") as mock_update_cfg,
        ):
            mock_get_graph.return_value = mock_graph

            await component.load_graph_and_update_cfg(build_config=build_config, flow_id=flow_id, updated_at=updated_at)

            # Should convert datetime to ISO format string
            mock_get_graph.assert_called_once_with(flow_id_selected=flow_id, updated_at=updated_at.isoformat())
            mock_update_cfg.assert_called_once_with(build_config, mock_graph)

    def test_should_update_stale_flow_returns_true_when_flow_is_stale(self):
        """Test that should_update_stale_flow returns True when flow is outdated."""
        component = RunFlowComponent()

        flow = Data(
            data={
                "id": str(uuid4()),
                "updated_at": "2024-01-02T12:00:00Z",  # Newer
            }
        )

        build_config = dotdict(
            {
                "flow_name_selected": {
                    "selected_metadata": {
                        "updated_at": "2024-01-01T12:00:00Z"  # Older
                    }
                }
            }
        )

        result = component.should_update_stale_flow(flow, build_config)

        assert result is True

    def test_should_update_stale_flow_returns_false_when_flow_is_current(self):
        """Test that should_update_stale_flow returns False when flow is current."""
        component = RunFlowComponent()

        flow = Data(
            data={
                "id": str(uuid4()),
                "updated_at": "2024-01-01T12:00:00Z",  # Same
            }
        )

        build_config = dotdict(
            {
                "flow_name_selected": {
                    "selected_metadata": {
                        "updated_at": "2024-01-01T12:00:00Z"  # Same
                    }
                }
            }
        )

        result = component.should_update_stale_flow(flow, build_config)

        assert result is False

    def test_should_update_stale_flow_returns_false_when_no_updated_at_in_flow(self):
        """Test that should_update_stale_flow returns falsey value when flow has no updated_at."""
        component = RunFlowComponent()

        flow = Data(data={"id": str(uuid4()), "updated_at": None})

        build_config = dotdict({"flow_name_selected": {"selected_metadata": {"updated_at": "2024-01-01T12:00:00Z"}}})

        result = component.should_update_stale_flow(flow, build_config)

        assert not result  # Should return falsey (None or False)

    def test_should_update_stale_flow_returns_false_when_no_metadata_updated_at(self):
        """Test that should_update_stale_flow returns falsey value when metadata has no updated_at."""
        component = RunFlowComponent()

        flow = Data(data={"id": str(uuid4()), "updated_at": "2024-01-01T12:00:00Z"})

        build_config = dotdict({"flow_name_selected": {"selected_metadata": {}}})

        result = component.should_update_stale_flow(flow, build_config)

        assert not result  # Should return falsey (None or False)

    @pytest.mark.asyncio
    async def test_check_and_update_stale_flow_updates_when_stale(self):
        """Test that check_and_update_stale_flow updates config when flow is stale."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())

        flow_id = str(uuid4())
        flow = Data(data={"id": flow_id, "updated_at": "2024-01-02T12:00:00Z"})

        build_config = dotdict({"flow_name_selected": {"selected_metadata": {"updated_at": "2024-01-01T12:00:00Z"}}})

        with (
            patch.object(component, "should_update_stale_flow", return_value=True),
            patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load,
        ):
            await component.check_and_update_stale_flow(flow, build_config)

            mock_load.assert_called_once_with(build_config, flow_id, "2024-01-02T12:00:00Z")

    @pytest.mark.asyncio
    async def test_check_and_update_stale_flow_does_nothing_when_current(self):
        """Test that check_and_update_stale_flow does nothing when flow is current."""
        component = RunFlowComponent()

        flow = Data(data={"id": str(uuid4()), "updated_at": "2024-01-01T12:00:00Z"})

        build_config = dotdict({})

        with (
            patch.object(component, "should_update_stale_flow", return_value=False),
            patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load,
        ):
            await component.check_and_update_stale_flow(flow, build_config)

            mock_load.assert_not_called()


class TestRunFlowComponentUpdateBuildConfig:
    """Test update_build_config method."""

    @pytest.mark.asyncio
    async def test_update_build_config_adds_missing_keys(self):
        """Test that update_build_config automatically adds missing required keys with defaults."""
        component = RunFlowComponent()
        build_config = dotdict({})  # Empty config

        result = await component.update_build_config(
            build_config=build_config, field_value=None, field_name="flow_name_selected"
        )

        # Verify that all default keys are now present
        for key in component.default_keys:
            assert key in result, f"Expected key '{key}' to be added to build_config"

        # Verify specific default values
        assert result["flow_name_selected"]["options"] == []
        assert result["flow_name_selected"]["options_metadata"] == []
        assert result["flow_name_selected"]["value"] is None
        assert result["flow_id_selected"]["value"] is None
        assert result["cache_flow"]["value"] is False

    @pytest.mark.asyncio
    async def test_update_build_config_refreshes_flow_list_with_none_value(self):
        """Test that update_build_config refreshes flow list when field_value is None."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {"options": [], "options_metadata": []},
                "flow_id_selected": {},
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_flows = [
            Data(data={"name": "Flow 1", "id": str(uuid4()), "updated_at": "2024-01-01T12:00:00Z"}),
            Data(data={"name": "Flow 2", "id": str(uuid4()), "updated_at": "2024-01-01T12:00:00Z"}),
        ]

        with patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_flows

            result = await component.update_build_config(
                build_config=build_config,
                field_value=None,  # Triggers refresh
                field_name="flow_name_selected",
            )

            assert "Flow 1" in result["flow_name_selected"]["options"]
            assert "Flow 2" in result["flow_name_selected"]["options"]
            assert len(result["flow_name_selected"]["options_metadata"]) == 2

    @pytest.mark.asyncio
    async def test_update_build_config_refreshes_with_is_refresh_flag(self):
        """Test that update_build_config refreshes flow list when is_refresh is True."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {"options": [], "options_metadata": []},
                "flow_id_selected": {},
                "session_id": {},
                "cache_flow": {},
                "is_refresh": True,
            }
        )

        mock_flows = [
            Data(data={"name": "Flow 1", "id": str(uuid4()), "updated_at": "2024-01-01T12:00:00Z"}),
            Data(data={"name": "Flow 2", "id": str(uuid4()), "updated_at": "2024-01-01T12:00:00Z"}),
        ]

        with patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_flows

            result = await component.update_build_config(
                build_config=build_config,
                field_value=None,  # Change to None to test refresh path
                field_name="flow_name_selected",
            )

            assert "Flow 1" in result["flow_name_selected"]["options"]
            assert "Flow 2" in result["flow_name_selected"]["options"]
            assert len(result["flow_name_selected"]["options_metadata"]) == 2

    @pytest.mark.asyncio
    async def test_update_build_config_updates_graph_on_flow_selection(self):
        """Test that update_build_config updates graph when flow is selected."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"
        updated_at = "2024-01-01T12:00:00Z"

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": [flow_name],
                    "options_metadata": [{"id": flow_id}],
                    "selected_metadata": {"id": flow_id, "updated_at": updated_at},
                },
                "flow_id_selected": {"value": None},
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load:
            result = await component.update_build_config(
                build_config=build_config, field_value=flow_name, field_name="flow_name_selected"
            )

            mock_load.assert_called_once_with(build_config, flow_id, updated_at)
            assert result["flow_id_selected"]["value"] == flow_id

    @pytest.mark.asyncio
    async def test_update_build_config_handles_error_gracefully(self):
        """Test that update_build_config handles errors gracefully."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_name = "Test Flow"
        flow_id = str(uuid4())

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": [flow_name],
                    "selected_metadata": {"id": flow_id, "updated_at": "2024-01-01T12:00:00Z"},
                },
                "flow_id_selected": {"value": None},
                "session_id": {},
                "cache_flow": {},
            }
        )

        with patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = Exception("Test error")

            with pytest.raises(RuntimeError, match="Error building graph for flow"):
                await component.update_build_config(
                    build_config=build_config, field_value=flow_name, field_name="flow_name_selected"
                )

    @pytest.mark.asyncio
    async def test_update_build_config_returns_unchanged_for_other_fields(self):
        """Test that update_build_config returns unchanged config for non-flow_name_selected fields."""
        component = RunFlowComponent()

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {},
                "flow_id_selected": {},
                "session_id": {},
                "cache_flow": {},
            }
        )

        result = await component.update_build_config(
            build_config=build_config, field_value="some_value", field_name="session_id"
        )

        assert result == build_config

    @pytest.mark.asyncio
    async def test_update_build_config_does_not_refresh_without_conditions(self):
        """Test that update_build_config does NOT refresh when is_refresh is False and field_value is not None."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"
        updated_at = "2024-01-01T12:00:00Z"

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": ["Old Flow"],
                    "options_metadata": [{"id": "old_id"}],
                    "selected_metadata": {"id": flow_id, "updated_at": updated_at},
                },
                "flow_id_selected": {"value": flow_id},
                "session_id": {},
                "cache_flow": {},
                "is_refresh": False,  # Not refreshing
            }
        )

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with (
            patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list,
            patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load,
        ):
            await component.update_build_config(
                build_config=build_config,
                field_value=flow_name,  # Non-None value
                field_name="flow_name_selected",
            )

            # Should NOT have called list flows (no refresh)
            mock_list.assert_not_called()

            # Should have called load_graph_and_update_cfg instead (normal flow selection)
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_flow_runtime_uses_selected_metadata_updated_at(self):
        """Ensure runtime fetch passes cached metadata updated_at to get_graph."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Cached Flow"
        updated_at = "2024-10-01T12:34:56Z"

        component._inputs["cache_flow"].value = True
        component._inputs["flow_id_selected"].value = flow_id
        component._inputs["flow_name_selected"].value = flow_name
        component._inputs["session_id"].value = Message(text="session")

        component._vertex = SimpleNamespace(
            data={
                "node": {
                    "template": {
                        "flow_name_selected": {
                            "selected_metadata": {
                                "id": flow_id,
                                "updated_at": updated_at,
                            }
                        }
                    }
                }
            }
        )

        component._pre_run_setup()

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        component.get_graph = AsyncMock(return_value=mock_graph)

        with patch("lfx.base.tools.run_flow.run_flow", new=AsyncMock(return_value=[])) as mock_run_flow:
            await component._run_flow_with_cached_graph(
                user_id=component.user_id,
                tweaks=None,
                inputs=None,
                output_type="any",
            )

        component.get_graph.assert_awaited_once_with(
            flow_name_selected=flow_name,
            flow_id_selected=flow_id,
            updated_at=updated_at,
        )
        mock_run_flow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_build_config_handles_flow_id_selected_field(self):
        """Test that update_build_config handles flow_id_selected field changes."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"
        updated_at = "2024-01-01T12:00:00Z"

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": [flow_name],
                    "selected_metadata": {"id": flow_id, "updated_at": updated_at},
                },
                "flow_id_selected": {"value": flow_id},
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load:
            await component.update_build_config(
                build_config=build_config, field_value=flow_id, field_name="flow_id_selected"
            )

            # Should call load_graph_and_update_cfg with the flow_id
            mock_load.assert_called_once_with(build_config, flow_id, updated_at)

    @pytest.mark.asyncio
    async def test_update_build_config_derives_flow_id_from_metadata(self):
        """Test that flow_id is derived from selected_metadata when available."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"
        updated_at = "2024-01-01T12:00:00Z"

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": [flow_name],
                    "selected_metadata": {"id": flow_id, "updated_at": updated_at},
                },
                "flow_id_selected": {"value": None},  # No existing value
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load:
            result = await component.update_build_config(
                build_config=build_config, field_value=flow_name, field_name="flow_name_selected"
            )

            # Should have derived the flow_id from selected_metadata
            assert result["flow_id_selected"]["value"] == flow_id
            mock_load.assert_called_once_with(build_config, flow_id, updated_at)

    @pytest.mark.asyncio
    async def test_update_build_config_uses_existing_flow_id_when_no_metadata(self):
        """Test that existing flow_id is used when selected_metadata is unavailable."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        existing_flow_id = str(uuid4())
        flow_name = "Test Flow"

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": [flow_name],
                    # No selected_metadata
                },
                "flow_id_selected": {"value": existing_flow_id},
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load:
            result = await component.update_build_config(
                build_config=build_config, field_value=flow_name, field_name="flow_name_selected"
            )

            # Should have kept the existing flow_id
            assert result["flow_id_selected"]["value"] == existing_flow_id
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_build_config_checks_stale_flow_during_refresh(self):
        """Test that update_build_config checks and updates stale flows during refresh."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        component.flow_id_selected = flow_id

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {"options": [], "options_metadata": []},
                "flow_id_selected": {},
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_flows = [
            Data(data={"name": "Flow 1", "id": flow_id, "updated_at": "2024-01-02T12:00:00Z"}),
        ]

        with (
            patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list,
            patch.object(component, "check_and_update_stale_flow", new_callable=AsyncMock) as mock_check,
        ):
            mock_list.return_value = mock_flows

            await component.update_build_config(
                build_config=build_config, field_value=None, field_name="flow_name_selected"
            )

            # Should have checked if flow is stale
            mock_check.assert_called_once_with(mock_flows[0], build_config)

    @pytest.mark.asyncio
    async def test_update_build_config_uses_get_selected_flow_meta(self):
        """Test that update_build_config uses get_selected_flow_meta to derive flow_id."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"
        updated_at = "2024-01-01T12:00:00Z"

        build_config = dotdict(
            {
                "code": {},
                "_type": {},
                "flow_name_selected": {
                    "options": [flow_name],
                    "selected_metadata": {"id": flow_id, "updated_at": updated_at},
                },
                "flow_id_selected": {"value": None},
                "session_id": {},
                "cache_flow": {},
            }
        )

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "load_graph_and_update_cfg", new_callable=AsyncMock) as mock_load:
            result = await component.update_build_config(
                build_config=build_config, field_value=flow_name, field_name="flow_name_selected"
            )

            # Should have derived flow_id from metadata
            assert result["flow_id_selected"]["value"] == flow_id

            # Should have called load_graph_and_update_cfg with correct parameters
            mock_load.assert_called_once_with(build_config, flow_id, updated_at)
