import pytest
from lfx.base.tools.constants import TOOL_OUTPUT_DISPLAY_NAME, TOOL_OUTPUT_NAME
from lfx.custom.custom_component.component import Component


class TestComponentOutputs:
    @pytest.mark.asyncio
    async def test_run_and_validate_update_outputs_tool_mode(self):
        """Test run_and_validate_update_outputs with tool_mode field."""

        class TestComponent(Component):
            def build(self) -> None:
                pass

        component = TestComponent()

        # Create a frontend node with regular outputs
        original_outputs = [
            {
                "name": "regular_output",
                "type": "str",
                "display_name": "Regular Output",
                "method": "get_output",
                "types": ["Any"],
                "selected": "Any",
                "value": "__UNDEFINED__",
                "cache": True,
                "required_inputs": None,
                "hidden": None,
            }
        ]
        frontend_node = {
            "outputs": original_outputs.copy()  # Make a copy to preserve original
        }

        # Test enabling tool mode
        updated_node = await component.run_and_validate_update_outputs(
            frontend_node=frontend_node.copy(),  # Use a copy to avoid modifying original
            field_name="tool_mode",
            field_value=True,
        )

        # Verify tool output is added and regular output is removed
        assert len(updated_node["outputs"]) == 1
        assert updated_node["outputs"][0]["name"] == TOOL_OUTPUT_NAME
        assert updated_node["outputs"][0]["display_name"] == TOOL_OUTPUT_DISPLAY_NAME

        # Test disabling tool mode - use the original frontend node
        updated_node = await component.run_and_validate_update_outputs(
            frontend_node={"outputs": original_outputs.copy()},  # Use original outputs
            field_name="tool_mode",
            field_value=False,
        )

        # Verify original outputs are restored
        assert len(updated_node["outputs"]) == 1
        # Compare only essential fields instead of the entire dict
        assert updated_node["outputs"][0]["name"] == original_outputs[0]["name"]
        assert updated_node["outputs"][0]["display_name"] == original_outputs[0]["display_name"]
        assert updated_node["outputs"][0]["method"] == original_outputs[0]["method"]
        assert "types" in updated_node["outputs"][0]
        assert "selected" in updated_node["outputs"][0]

    @pytest.mark.asyncio
    async def test_run_and_validate_update_outputs_invalid_output(self):
        """Test run_and_validate_update_outputs with invalid output structure."""

        class TestComponent(Component):
            def build(self) -> None:
                pass

        component = TestComponent()

        # Create a frontend node with invalid output structure
        frontend_node = {"outputs": [{"invalid_field": "value"}]}

        # Test validation fails for invalid output
        with pytest.raises(ValueError, match="Invalid output: 1 validation error for Output"):
            await component.run_and_validate_update_outputs(
                frontend_node=frontend_node, field_name="some_field", field_value="some_value"
            )

    @pytest.mark.asyncio
    async def test_run_and_validate_update_outputs_custom_update(self):
        """Test run_and_validate_update_outputs with custom update logic."""

        class CustomComponent(Component):
            def build(self) -> None:
                pass

            def get_custom(self) -> str:
                """Method that returns a string."""
                return "custom output"

            def update_outputs(self, frontend_node, field_name, field_value):  # noqa: ARG002
                if field_name == "custom_field":
                    frontend_node["outputs"].append(
                        {
                            "name": "custom_output",
                            "type": "str",
                            "display_name": "Custom Output",
                            "method": "get_custom",
                            "types": ["Any"],
                            "selected": "Any",
                            "value": "__UNDEFINED__",
                            "cache": True,
                            "required_inputs": None,
                            "hidden": None,
                        }
                    )
                return frontend_node

        component = CustomComponent()
        frontend_node = {"outputs": []}

        # Test custom update logic
        updated_node = await component.run_and_validate_update_outputs(
            frontend_node=frontend_node, field_name="custom_field", field_value="custom_value"
        )

        assert len(updated_node["outputs"]) == 1
        assert updated_node["outputs"][0]["name"] == "custom_output"
        assert updated_node["outputs"][0]["display_name"] == "Custom Output"
        assert updated_node["outputs"][0]["method"] == "get_custom"
        assert "types" in updated_node["outputs"][0]
        assert "selected" in updated_node["outputs"][0]

    @pytest.mark.asyncio
    async def test_run_and_validate_update_outputs_with_existing_tool_output(self):
        """Test run_and_validate_update_outputs when tool output already exists."""

        class TestComponent(Component):
            def build(self) -> None:
                pass

            async def to_toolkit(self) -> list:
                """Method that returns a list of tools."""
                return []

        component = TestComponent()

        # Create a frontend node with tool output already present
        frontend_node = {
            "outputs": [
                {
                    "name": TOOL_OUTPUT_NAME,  # Use constant instead of hardcoded string
                    "type": "Tool",
                    "display_name": TOOL_OUTPUT_DISPLAY_NAME,  # Use constant
                    "method": "to_toolkit",
                    "types": ["Tool"],
                    "selected": "Tool",
                    "value": "__UNDEFINED__",
                    "cache": True,
                    "required_inputs": None,
                    "hidden": None,
                }
            ]
        }

        # Test enabling tool mode doesn't duplicate tool output
        updated_node = await component.run_and_validate_update_outputs(
            frontend_node=frontend_node, field_name="tool_mode", field_value=True
        )

        assert len(updated_node["outputs"]) == 1
        assert updated_node["outputs"][0]["name"] == TOOL_OUTPUT_NAME  # Use constant
        assert updated_node["outputs"][0]["display_name"] == TOOL_OUTPUT_DISPLAY_NAME  # Use constant
        assert "types" in updated_node["outputs"][0]
        assert "selected" in updated_node["outputs"][0]

    @pytest.mark.asyncio
    async def test_run_and_validate_update_outputs_with_multiple_outputs(self):
        """Test run_and_validate_update_outputs with multiple outputs."""

        class TestComponent(Component):
            def build(self) -> None:
                pass

            def get_output1(self) -> str:
                """Method that returns a string."""
                return "output1"

            def get_output2(self) -> str:
                """Method that returns a string."""
                return "output2"

            def update_outputs(self, frontend_node, field_name, field_value):  # noqa: ARG002
                if field_name == "add_output":
                    frontend_node["outputs"].extend(
                        [
                            {
                                "name": "output1",
                                "type": "str",
                                "display_name": "Output 1",
                                "method": "get_output1",
                            },
                            {
                                "name": "output2",
                                "type": "str",
                                "display_name": "Output 2",
                                "method": "get_output2",
                            },
                        ]
                    )
                return frontend_node

        component = TestComponent()
        frontend_node = {"outputs": []}

        # Test adding multiple outputs
        updated_node = await component.run_and_validate_update_outputs(
            frontend_node=frontend_node, field_name="add_output", field_value=True
        )

        assert len(updated_node["outputs"]) == 2
        assert updated_node["outputs"][0]["name"] == "output1"
        assert updated_node["outputs"][1]["name"] == "output2"
        for output in updated_node["outputs"]:
            assert "types" in output
            assert "selected" in output
            # The component adds only 'Text' type for string outputs
            assert set(output["types"]) == {"Text"}
            assert output["selected"] == "Text"

    @pytest.mark.asyncio
    async def test_run_and_validate_update_outputs_output_validation(self):
        """Test output validation in run_and_validate_update_outputs."""

        class TestComponent(Component):
            def build(self) -> None:
                pass

            def get_test(self) -> str:
                """Test method."""
                return "test"

        component = TestComponent()

        # Test invalid method name case
        invalid_node = {
            "outputs": [{"name": "test", "type": "str", "method": "nonexistent_method", "display_name": "Test"}]
        }

        with pytest.raises(AttributeError, match="nonexistent_method not found in TestComponent"):
            await component.run_and_validate_update_outputs(
                frontend_node=invalid_node, field_name="test", field_value=True
            )

        # Test missing method case
        invalid_node = {"outputs": [{"name": "test", "type": "str", "display_name": "Test"}]}

        with pytest.raises(ValueError, match="Output test does not have a method"):
            await component.run_and_validate_update_outputs(
                frontend_node=invalid_node, field_name="test", field_value=True
            )
