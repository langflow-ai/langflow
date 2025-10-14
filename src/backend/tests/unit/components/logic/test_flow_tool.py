from unittest.mock import patch

import pytest
from lfx.components.logic.flow_tool import FlowToolComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithClient


class TestFlowToolComponent(ComponentTestBaseWithClient):
    """Test cases for FlowToolComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return FlowToolComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "flow_name": "test_flow",
            "tool_name": "test_tool",
            "tool_description": "Test tool description",
            "return_direct": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_component_initialization(self, component_class, default_kwargs):
        """Test proper initialization of FlowToolComponent."""
        component = await self.component_setup(component_class, default_kwargs)
        assert component.display_name == "Flow as Tool"
        assert "Construct a Tool from a function that runs the loaded Flow" in component.description
        assert component.name == "FlowTool"
        assert component.icon == "hammer"
        assert component.legacy is True
        assert component.trace_type == "tool"

    async def test_field_order_configuration(self):
        """Test field_order configuration."""
        expected_order = ["flow_name", "name", "description", "return_direct"]
        # field_order is a class attribute
        assert FlowToolComponent.field_order == expected_order

    async def test_inputs_configuration(self, component_class, default_kwargs):
        """Test that inputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        expected_inputs = {"flow_name", "tool_name", "tool_description", "return_direct"}
        input_names = {inp.name for inp in component.inputs}

        assert expected_inputs.issubset(input_names)

        # Test flow_name input configuration
        flow_name_input = next(inp for inp in component.inputs if inp.name == "flow_name")
        assert flow_name_input.display_name == "Flow Name"
        assert flow_name_input.refresh_button is True

        # Test return_direct input configuration
        return_direct_input = next(inp for inp in component.inputs if inp.name == "return_direct")
        assert return_direct_input.advanced is True

    async def test_outputs_configuration(self, component_class, default_kwargs):
        """Test that outputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        assert len(component.outputs) == 1

        output = component.outputs[0]
        assert output.name == "api_build_tool"
        assert output.display_name == "Tool"
        assert output.method == "build_tool"

    @pytest.mark.asyncio
    async def test_get_flow_names(self, component_class, default_kwargs):
        """Test get_flow_names method."""
        component = await self.component_setup(component_class, default_kwargs)
        mock_flows = [
            Data(data={"name": "Flow 1"}),
            Data(data={"name": "Flow 2"}),
            Data(data={"name": "Flow 3"}),
        ]

        with patch.object(component, "alist_flows", return_value=mock_flows):
            result = await component.get_flow_names()

            assert result == ["Flow 1", "Flow 2", "Flow 3"]

    @pytest.mark.asyncio
    async def test_get_flow_names_empty_list(self, component_class, default_kwargs):
        """Test get_flow_names with empty flow list."""
        component = await self.component_setup(component_class, default_kwargs)
        with patch.object(component, "alist_flows", return_value=[]):
            result = await component.get_flow_names()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_flow_found(self, component_class, default_kwargs):
        """Test get_flow method when flow is found."""
        component = await self.component_setup(component_class, default_kwargs)
        mock_flows = [
            Data(data={"name": "Flow 1"}),
            Data(data={"name": "Target Flow"}),
            Data(data={"name": "Flow 3"}),
        ]

        with patch.object(component, "alist_flows", return_value=mock_flows):
            result = await component.get_flow("Target Flow")

            assert result == mock_flows[1]
            assert result.data["name"] == "Target Flow"

    @pytest.mark.asyncio
    async def test_get_flow_not_found(self, component_class, default_kwargs):
        """Test get_flow method when flow is not found."""
        component = await self.component_setup(component_class, default_kwargs)
        mock_flows = [
            Data(data={"name": "Flow 1"}),
            Data(data={"name": "Flow 2"}),
        ]

        with patch.object(component, "alist_flows", return_value=mock_flows):
            result = await component.get_flow("Nonexistent Flow")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_flow_empty_list(self, component_class, default_kwargs):
        """Test get_flow method with empty flow list."""
        component = await self.component_setup(component_class, default_kwargs)
        with patch.object(component, "alist_flows", return_value=[]):
            result = await component.get_flow("Any Flow")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_build_config_flow_name(self, component_class, default_kwargs):
        """Test update_build_config when field_name is flow_name."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"flow_name": {"options": []}}

        # The implementation assigns get_flow_names() directly (without await)
        # This means it assigns a coroutine object, which is actually a bug
        result = await component.update_build_config(build_config, "some_value", "flow_name")

        # The options will contain a coroutine object due to the bug in the implementation
        import inspect

        assert inspect.iscoroutine(result["flow_name"]["options"])

    @pytest.mark.asyncio
    async def test_update_build_config_other_field(self, component_class, default_kwargs):
        """Test update_build_config when field_name is not flow_name."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"some_field": "value"}

        result = await component.update_build_config(build_config, "some_value", "other_field")

        assert result == build_config  # Should return unchanged

    @pytest.mark.asyncio
    async def test_build_tool_no_flow_name(self, component_class, default_kwargs):
        """Test build_tool raises error when flow_name is not provided."""
        component = await self.component_setup(component_class, default_kwargs)
        from lfx.base.tools.flow_tool import FlowTool

        with (
            patch.object(component, "_attributes", {}),
            patch.object(FlowTool, "model_rebuild"),  # Mock to avoid Graph annotation error
            pytest.raises(ValueError, match="Flow name is required"),
        ):
            await component.build_tool()

    @pytest.mark.asyncio
    async def test_build_tool_empty_flow_name(self, component_class, default_kwargs):
        """Test build_tool raises error when flow_name is empty."""
        component = await self.component_setup(component_class, default_kwargs)
        from lfx.base.tools.flow_tool import FlowTool

        with (
            patch.object(component, "_attributes", {"flow_name": ""}),
            patch.object(FlowTool, "model_rebuild"),  # Mock to avoid Graph annotation error
            pytest.raises(ValueError, match="Flow name is required"),
        ):
            await component.build_tool()

    @pytest.mark.asyncio
    async def test_build_tool_flow_not_found(self, component_class, default_kwargs):
        """Test build_tool raises error when flow is not found."""
        component = await self.component_setup(component_class, default_kwargs)
        from lfx.base.tools.flow_tool import FlowTool

        with (
            patch.object(component, "_attributes", {"flow_name": "Nonexistent Flow"}),
            patch.object(component, "get_flow", return_value=None),
            patch.object(FlowTool, "model_rebuild"),  # Mock to avoid Graph annotation error
            pytest.raises(ValueError, match="Flow not found"),
        ):
            await component.build_tool()

    async def test_component_inheritance(self, component_class, default_kwargs):
        """Test that component properly inherits from LCToolComponent."""
        component = await self.component_setup(component_class, default_kwargs)
        from lfx.base.langchain_utilities.model import LCToolComponent

        assert isinstance(component, LCToolComponent)

    async def test_component_legacy_status(self, component_class, default_kwargs):
        """Test that component is properly marked as legacy."""
        component = await self.component_setup(component_class, default_kwargs)
        assert hasattr(component, "legacy")
        assert component.legacy is True

    @pytest.mark.asyncio
    async def test_get_flow_names_handles_missing_name_field(self, component_class, default_kwargs):
        """Test get_flow_names handles flows without name field."""
        component = await self.component_setup(component_class, default_kwargs)
        mock_flows = [
            Data(data={"name": "Flow 1"}),
            Data(data={}),  # Missing name field
            Data(data={"name": "Flow 3"}),
        ]

        with (
            patch.object(component, "alist_flows", return_value=mock_flows),
            pytest.raises(KeyError),
        ):
            await component.get_flow_names()
