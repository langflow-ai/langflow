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
