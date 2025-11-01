from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from lfx.components.logic.run_flow import RunFlowComponent
from lfx.graph.graph.base import Graph
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict


class TestRunFlowComponentInitialization:
    """Test RunFlowComponent initialization."""

    def test_component_has_correct_metadata(self):
        """Test that component has correct display name, description, etc."""
        assert RunFlowComponent.display_name == "Run Flow"
        assert "Executes another flow from within the same project." in RunFlowComponent.description
        assert RunFlowComponent.name == "RunFlow"
        assert RunFlowComponent.icon == "Workflow"
        assert RunFlowComponent.beta is True


class TestRunFlowComponentUpdateBuildConfig:
    """Test update_build_config method."""

    @pytest.mark.asyncio
    async def test_update_build_config_adds_missing_keys(self):
        """Test that update_build_config automatically adds missing required keys with defaults."""
        component = RunFlowComponent()
        build_config = dotdict({})  # Empty config

        result = await component.update_build_config(
            build_config=build_config,
            field_value=None,
            field_name="flow_name_selected"
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

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {"options": [], "options_metadata": []},
            "flow_id_selected": {},
            "session_id": {},
            "cache_flow": {},
        })

        mock_flows = [
            Data(data={"name": "Flow 1", "id": str(uuid4())}),
            Data(data={"name": "Flow 2", "id": str(uuid4())}),
        ]

        with patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_flows

            result = await component.update_build_config(
                build_config=build_config,
                field_value=None,  # Triggers refresh
                field_name="flow_name_selected"
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

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {"options": [], "options_metadata": []},
            "flow_id_selected": {},
            "session_id": {},
            "cache_flow": {},
            "is_refresh": True,
        })

        mock_flows = [
            Data(data={"name": "Flow 1", "id": str(uuid4())}),
            Data(data={"name": "Flow 2", "id": str(uuid4())}),
        ]

        with patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_flows

            result = await component.update_build_config(
                build_config=build_config,
                field_value=None,  # Change to None to test refresh path
                field_name="flow_name_selected"
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

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {
                "options": [flow_name],
                "options_metadata": [{"id": flow_id}],
                "selected_metadata": {"id": flow_id},
            },
            "flow_id_selected": {"value": None},
            "session_id": {},
            "cache_flow": {},
        })

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph, \
             patch.object(component, "update_build_config_from_graph") as mock_update:

            mock_get_graph.return_value = mock_graph

            result = await component.update_build_config(
                build_config=build_config,
                field_value=flow_name,
                field_name="flow_name_selected"
            )

            mock_get_graph.assert_called_once_with(
                flow_name_selected=flow_name,
                flow_id_selected=flow_id
            )
            mock_update.assert_called_once_with(build_config, mock_graph)
            assert result["flow_id_selected"]["value"] == flow_id

    @pytest.mark.asyncio
    async def test_update_build_config_handles_error_gracefully(self):
        """Test that update_build_config handles errors gracefully."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_name = "Test Flow"

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {
                "options": [flow_name],
                "selected_metadata": {"id": str(uuid4())},
            },
            "flow_id_selected": {"value": None},
            "session_id": {},
            "cache_flow": {},
        })

        with patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph:
            mock_get_graph.side_effect = Exception("Test error")

            with pytest.raises(RuntimeError, match="Error building graph for flow"):
                await component.update_build_config(
                    build_config=build_config,
                    field_value=flow_name,
                    field_name="flow_name_selected"
                )

    @pytest.mark.asyncio
    async def test_update_build_config_returns_unchanged_for_other_fields(self):
        """Test that update_build_config returns unchanged config for non-flow_name_selected fields."""
        component = RunFlowComponent()

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {},
            "flow_id_selected": {},
            "session_id": {},
            "cache_flow": {},
        })

        result = await component.update_build_config(
            build_config=build_config,
            field_value="some_value",
            field_name="session_id"
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

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {
                "options": ["Old Flow"],
                "options_metadata": [{"id": "old_id"}],
                "selected_metadata": {"id": flow_id},
            },
            "flow_id_selected": {"value": flow_id},
            "session_id": {},
            "cache_flow": {},
            "is_refresh": False,  # Not refreshing
        })

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "alist_flows_by_flow_folder", new_callable=AsyncMock) as mock_list, \
             patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph, \
             patch.object(component, "update_build_config_from_graph") as mock_update:

            mock_get_graph.return_value = mock_graph

            await component.update_build_config(
                build_config=build_config,
                field_value=flow_name,  # Non-None value
                field_name="flow_name_selected"
            )

            # Should NOT have called list flows (no refresh)
            mock_list.assert_not_called()

            # Should have called get_graph instead (normal flow selection)
            mock_get_graph.assert_called_once()
            mock_update.assert_called_once_with(build_config, mock_graph)

    @pytest.mark.asyncio
    async def test_update_build_config_handles_flow_id_selected_field(self):
        """Test that update_build_config handles flow_id_selected field changes."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {
                "options": [flow_name],
                "selected_metadata": {"id": flow_id},
            },
            "flow_id_selected": {"value": flow_id},
            "session_id": {},
            "cache_flow": {},
        })

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph, \
             patch.object(component, "update_build_config_from_graph") as mock_update:

            mock_get_graph.return_value = mock_graph

            await component.update_build_config(
                build_config=build_config,
                field_value=flow_id,
                field_name="flow_id_selected"
            )

            # Should call get_graph with the flow_id
            mock_get_graph.assert_called_once_with(
                flow_name_selected=flow_id,
                flow_id_selected=flow_id
            )
            mock_update.assert_called_once_with(build_config, mock_graph)

    @pytest.mark.asyncio
    async def test_update_build_config_derives_flow_id_from_metadata(self):
        """Test that flow_id is derived from selected_metadata when available."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        flow_id = str(uuid4())
        flow_name = "Test Flow"

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {
                "options": [flow_name],
                "selected_metadata": {"id": flow_id},
            },
            "flow_id_selected": {"value": None},  # No existing value
            "session_id": {},
            "cache_flow": {},
        })

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph, \
             patch.object(component, "update_build_config_from_graph") as mock_update:

            mock_get_graph.return_value = mock_graph

            result = await component.update_build_config(
                build_config=build_config,
                field_value=flow_name,
                field_name="flow_name_selected"
            )

            # Should have derived the flow_id from selected_metadata
            assert result["flow_id_selected"]["value"] == flow_id
            mock_get_graph.assert_called_once_with(
                flow_name_selected=flow_name,
                flow_id_selected=flow_id
            )
            mock_update.assert_called_once_with(build_config, mock_graph)

    @pytest.mark.asyncio
    async def test_update_build_config_uses_existing_flow_id_when_no_metadata(self):
        """Test that existing flow_id is used when selected_metadata is unavailable."""
        component = RunFlowComponent()
        component._user_id = str(uuid4())
        component._flow_id = str(uuid4())

        existing_flow_id = str(uuid4())
        flow_name = "Test Flow"

        build_config = dotdict({
            "code": {},
            "_type": {},
            "flow_name_selected": {
                "options": [flow_name],
                # No selected_metadata
            },
            "flow_id_selected": {"value": existing_flow_id},
            "session_id": {},
            "cache_flow": {},
        })

        mock_graph = MagicMock(spec=Graph)
        mock_graph.vertices = []

        with patch.object(component, "get_graph", new_callable=AsyncMock) as mock_get_graph, \
             patch.object(component, "update_build_config_from_graph") as mock_update:

            mock_get_graph.return_value = mock_graph

            result = await component.update_build_config(
                build_config=build_config,
                field_value=flow_name,
                field_name="flow_name_selected"
            )

            # Should have kept the existing flow_id
            assert result["flow_id_selected"]["value"] == existing_flow_id
            mock_get_graph.assert_called_once_with(
                flow_name_selected=flow_name,
                flow_id_selected=existing_flow_id
            )
            mock_update.assert_called_once_with(build_config, mock_graph)

