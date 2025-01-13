from unittest.mock import MagicMock

import pytest
from langflow.components.helpers.notepad import NotepadComponent
from langflow.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestNotepadComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return NotepadComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_value": "Test Value",
            "operation": "add",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def _add_mock_vertex(self, component: NotepadComponent):
        mock_vertex = MagicMock()
        mock_vertex.graph = MagicMock()
        mock_vertex.graph.context = {}
        component._vertex = mock_vertex

    async def test_latest_version(self, component_class):
        """Test that the component works with the latest version."""
        component = component_class(input_value="Test Value", operation="add")
        self._add_mock_vertex(component)
        result = await component.process_and_get_notepad()
        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["value"] == "Test Value"

    async def test_add_value_default_position(self, component_class):
        # Create component with default settings
        component: NotepadComponent = component_class(input_value="First Value", operation="add")
        self._add_mock_vertex(component)
        # Add value and verify result
        result = await component.process_and_get_notepad()
        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["value"] == "First Value"

    async def test_add_value_specific_position(self, component_class):
        component: NotepadComponent = component_class(input_value="First Value", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Add second value at position 0
        component = component.set(input_value="Second Value", operation="add", position=0)
        result = await component.process_and_get_notepad()

        assert len(result) == 2
        assert result.iloc[0]["value"] == "Second Value"
        assert result.iloc[1]["value"] == "First Value"

    async def test_remove_value_by_position(self, component_class):
        """Test removing a value by specifying its position in the notepad.

        Steps:
        1) Create a notepad with "Value 1"
        2) Append "Value 2"
        3) Remove the value at position 0
        4) Assert only "Value 2" remains
        """
        # Step 1: Setup initial data with the first value
        component: NotepadComponent = component_class(input_value="Value 1", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Step 2: Append the second value
        component = component.set(input_value="Value 2", operation="add")
        await component.process_and_get_notepad()

        # Step 3: Remove value at position 0
        component = component.set(operation="remove", position=0)
        result = await component.process_and_get_notepad()

        # Step 4: Assert that only "Value 2" remains
        assert len(result) == 1
        assert result.iloc[0]["value"] == "Value 2"

    async def test_remove_value_by_value(self, component_class):
        """Test removing a value by specifying its value in the notepad.

        Steps:
        1) Create a notepad with "Value 1"
        2) Append "Value 2"
        3) Remove "Value 1" by specifying its value
        4) Assert only "Value 2" remains
        """
        # Step 1: Setup initial data with the first value
        component: NotepadComponent = component_class(input_value="Value 1", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Step 2: Append the second value
        component = component.set(input_value="Value 2", operation="add")
        await component.process_and_get_notepad()

        # Step 3: Remove "Value 1" by specifying the value
        component = component.set(operation="remove", input_value="Value 1")
        result = await component.process_and_get_notepad()

        # Step 4: Assert that only "Value 2" remains
        assert len(result) == 1
        assert result.iloc[0]["value"] == "Value 2"

    async def test_edit_value(self, component_class):
        """Test editing a value in the notepad.

        Steps:
        1) Create a notepad with an original value
        2) Edit that value at position 0 to "Modified"
        3) Assert that the updated value is "Modified"
        """
        # Step 1: Setup initial data with the original value
        component: NotepadComponent = component_class(input_value="Original", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Step 2: Edit the value to "Modified"
        component = component.set(operation="edit", input_value="Modified", position=0)
        result = await component.process_and_get_notepad()

        # Step 3: Assert that the updated value matches "Modified"
        assert len(result) == 1
        assert result.iloc[0]["value"] == "Modified"

    async def test_edit_empty_notepad(self, component_class):
        """Test editing a value on an empty notepad. The notepad remains empty.

        since there's nothing to edit.
        """
        # Step 1: Create a component configured to edit, but the notepad is empty
        component: NotepadComponent = component_class(input_value="Test", operation="edit")
        self._add_mock_vertex(component)
        result = await component.process_and_get_notepad()

        # Step 2: Verify the notepad remains empty
        assert isinstance(result, DataFrame)
        assert len(result) == 0

    async def test_persistence_between_operations(self, component_class):
        """Test that the notepad persists between multiple operations.

        Steps:
        1) Add "Value 1"
        2) Add "Value 2"
        3) Remove the first value
        4) Verify the final state is that "Value 2" remains
        """
        # Step 1: Add "Value 1"
        component: NotepadComponent = component_class(input_value="Value 1", operation="add")
        self._add_mock_vertex(component)
        result1 = await component.process_and_get_notepad()
        assert len(result1) == 1

        # Step 2: Add "Value 2"
        component = component.set(input_value="Value 2", operation="add")
        result2 = await component.process_and_get_notepad()
        assert len(result2) == 2

        # Step 3: Remove the first value
        component = component.set(operation="remove", position=0)
        result3 = await component.process_and_get_notepad()

        # Step 4: Verify only "Value 2" remains
        assert len(result3) == 1
        assert result3.iloc[0]["value"] == "Value 2"

    async def test_add_value_out_of_range_position(self, component_class):
        """Test adding values with out-of-range positions.

        Values should be appended at the end when position is:
        - Negative
        - Beyond the notepad length
        """
        component: NotepadComponent = component_class(input_value="First Value", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Test negative position
        component = component.set(input_value="Second Value", operation="add", position=-1)
        result = await component.process_and_get_notepad()
        assert len(result) == 2
        assert result.iloc[-1]["value"] == "Second Value"

        # Test position beyond length
        component = component.set(input_value="Third Value", operation="add", position=10)
        result = await component.process_and_get_notepad()
        assert len(result) == 3
        assert result.iloc[-1]["value"] == "Third Value"

    async def test_remove_value_invalid_cases(self, component_class):
        """Test removing values with invalid inputs.

        Tests:
        - Removing with invalid positions raises ValueError
        - Removing non-existent values leaves notepad unchanged
        - Removing from empty notepad leaves notepad unchanged
        """
        # Setup initial data
        component: NotepadComponent = component_class(input_value="Value 1", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Test removing with invalid position (negative)
        component = component.set(operation="remove", position=-1)
        with pytest.raises(
            ValueError, match="Error performing operation remove on notepad: Position -1 is out of bounds"
        ):
            await component.process_and_get_notepad()

        # Test removing with position beyond length
        component = component.set(operation="remove", position=10)
        with pytest.raises(
            ValueError, match="Error performing operation remove on notepad: Position 10 is out of bounds"
        ):
            await component.process_and_get_notepad()

        # Test removing non-existent value (should leave notepad unchanged)
        # Reset position to None for value-based removal
        component = component.set(operation="remove", input_value="Non-existent Value", position=None)
        result = await component.process_and_get_notepad()
        assert len(result) == 1  # Notepad should remain unchanged

        # Create empty notepad for empty notepad test
        empty_component: NotepadComponent = component_class(operation="remove")
        self._add_mock_vertex(empty_component)
        result = await empty_component.process_and_get_notepad()
        assert len(result) == 0  # Should handle empty notepad gracefully

    async def test_edit_value_edge_cases(self, component_class):
        """Test editing values with edge cases.

        Tests:
        - Editing with invalid positions
        - Editing the last row when position is beyond length
        """
        # Setup initial data
        component: NotepadComponent = component_class(input_value="Original", operation="add")
        self._add_mock_vertex(component)
        await component.process_and_get_notepad()

        # Add second value
        component = component.set(input_value="Second", operation="add")
        await component.process_and_get_notepad()

        # Test editing with negative position (should edit last row)
        component = component.set(operation="edit", input_value="Modified Last", position=-1)
        result = await component.process_and_get_notepad()
        assert result.iloc[-1]["value"] == "Modified Last"

        # Test editing with position beyond length (should edit last row)
        component = component.set(operation="edit", input_value="Modified Beyond", position=10)
        result = await component.process_and_get_notepad()
        assert result.iloc[-1]["value"] == "Modified Beyond"

    async def test_invalid_operation(self, component_class):
        """Test that invalid operations raise appropriate errors."""
        component: NotepadComponent = component_class(input_value="Test", operation="invalid_op")
        self._add_mock_vertex(component)

        with pytest.raises(ValueError, match="Invalid operation: invalid_op"):
            await component.process_and_get_notepad()

    async def test_multiple_notepad_instances(self, component_class):
        """Test that multiple notepads can be managed using different notepad names."""
        # Create first notepad
        component1: NotepadComponent = component_class(input_value="Value 1", operation="add", notepad_name="notepad1")
        self._add_mock_vertex(component1)
        result1 = await component1.process_and_get_notepad()

        # Create second notepad
        component2: NotepadComponent = component_class(input_value="Value 2", operation="add", notepad_name="notepad2")
        self._add_mock_vertex(component2)
        result2 = await component2.process_and_get_notepad()

        # Verify each notepad has its own content
        assert len(result1) == 1
        assert len(result2) == 1
        assert result1.iloc[0]["value"] == "Value 1"
        assert result2.iloc[0]["value"] == "Value 2"
