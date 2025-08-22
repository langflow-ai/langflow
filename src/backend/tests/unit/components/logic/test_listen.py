from unittest.mock import patch

import pytest
from langflow.components.logic.listen import ListenComponent
from langflow.schema.data import Data


class TestListenComponent:
    """Test cases for ListenComponent."""

    @pytest.fixture
    def component(self):
        """Create a ListenComponent instance for testing."""
        return ListenComponent()

    def test_component_initialization(self, component):
        """Test proper initialization of ListenComponent."""
        assert component.display_name == "Listen"
        assert component.description == "A component to listen for a notification."
        assert component.name == "Listen"
        assert component.icon == "Radio"
        assert component.beta is True

    def test_inputs_configuration(self, component):
        """Test that inputs are properly configured."""
        assert len(component.inputs) == 1

        context_key_input = component.inputs[0]
        assert context_key_input.name == "context_key"
        assert context_key_input.display_name == "Context Key"
        assert context_key_input.required is True
        assert "Message" in context_key_input.input_types

    def test_outputs_configuration(self, component):
        """Test that outputs are properly configured."""
        assert len(component.outputs) == 1

        output = component.outputs[0]
        assert output.name == "data"
        assert output.display_name == "Data"
        assert output.method == "listen_for_data"
        assert output.cache is False

    def test_listen_for_data_key_exists(self, component):
        """Test listen_for_data when context key exists."""
        component.context_key = "test_key"
        expected_data = Data(text="Hello World")

        with patch.object(type(component), "ctx", new_callable=lambda: {"test_key": expected_data}):
            result = component.listen_for_data()

            assert result == expected_data

    def test_listen_for_data_key_does_not_exist(self, component):
        """Test listen_for_data when context key does not exist."""
        component.context_key = "nonexistent_key"

        with patch.object(type(component), "ctx", new_callable=lambda: {"other_key": Data(text="Other data")}):
            result = component.listen_for_data()

            assert isinstance(result, Data)
            assert result.text == ""

    def test_listen_for_data_empty_context(self, component):
        """Test listen_for_data with empty context."""
        component.context_key = "any_key"

        with patch.object(type(component), "ctx", new_callable=dict):
            result = component.listen_for_data()

            assert isinstance(result, Data)
            assert result.text == ""

    def test_listen_for_data_none_context(self, component):
        """Test listen_for_data with None context value."""
        component.context_key = "test_key"

        # When ctx contains the key but value is None, get() returns None
        with patch.object(type(component), "ctx", new_callable=lambda: {"test_key": None}):
            result = component.listen_for_data()

            assert result is None

    def test_listen_for_data_with_text_data(self, component):
        """Test listen_for_data with Data containing text."""
        component.context_key = "test_key"
        test_data = Data(text="String content")

        with patch.object(type(component), "ctx", new_callable=lambda: {"test_key": test_data}):
            result = component.listen_for_data()

            assert result == test_data
            assert result.text == "String content"

    def test_listen_for_data_with_dict_data(self, component):
        """Test listen_for_data with Data containing dict."""
        component.context_key = "test_key"
        test_data = Data(data={"key": "value"})

        with patch.object(type(component), "ctx", new_callable=lambda: {"test_key": test_data}):
            result = component.listen_for_data()

            assert result == test_data
            assert result.data == {"key": "value"}

    def test_listen_for_data_with_underscore_key(self, component):
        """Test listen_for_data with underscore key names."""
        component.context_key = "key_with_underscores"
        test_data = Data(text="Underscore data")

        with patch.object(type(component), "ctx", new_callable=lambda: {"key_with_underscores": test_data}):
            result = component.listen_for_data()

            assert result == test_data
            assert result.text == "Underscore data"

    def test_listen_for_data_with_dash_key(self, component):
        """Test listen_for_data with dash key names."""
        component.context_key = "key-with-dashes"
        test_data = Data(text="Dash data")

        with patch.object(type(component), "ctx", new_callable=lambda: {"key-with-dashes": test_data}):
            result = component.listen_for_data()

            assert result == test_data
            assert result.text == "Dash data"

    def test_listen_for_data_multiple_context_keys(self, component):
        """Test listen_for_data retrieves only the specified key."""
        mock_ctx = {
            "key1": Data(text="Data 1"),
            "key2": Data(text="Data 2"),
            "key3": Data(text="Data 3"),
        }

        component.context_key = "key2"  # Request specific key

        with patch.object(type(component), "ctx", new_callable=lambda: mock_ctx):
            result = component.listen_for_data()

            assert result == mock_ctx["key2"]
            assert result.text == "Data 2"

    def test_listen_for_data_method_signature(self, component):
        """Test that listen_for_data method has correct signature and docstring."""
        assert hasattr(component, "listen_for_data")
        assert callable(component.listen_for_data)

        # Check docstring exists and contains key information
        docstring = component.listen_for_data.__doc__
        assert docstring is not None
        assert "context key" in docstring.lower()
        assert "Data object" in docstring

    def test_component_beta_status(self, component):
        """Test that component is properly marked as beta."""
        assert hasattr(component, "beta")
        assert component.beta is True

    def test_component_inheritance(self, component):
        """Test that component properly inherits from Component base class."""
        from langflow.custom import Component

        assert isinstance(component, Component)

    def test_context_key_input_details(self, component):
        """Test detailed configuration of context_key input."""
        context_key_input = next(inp for inp in component.inputs if inp.name == "context_key")

        assert context_key_input.display_name == "Context Key"
        assert "key of the context to listen for" in context_key_input.info
        assert context_key_input.required is True
        assert context_key_input.input_types == ["Message"]

    def test_output_method_mapping(self, component):
        """Test that output is correctly mapped to listen_for_data method."""
        output = component.outputs[0]
        assert output.method == "listen_for_data"
        assert hasattr(component, output.method)
        assert callable(getattr(component, output.method))

    def test_empty_string_context_key(self, component):
        """Test behavior with empty string context key."""
        component.context_key = ""

        # Mock the ctx property
        with patch.object(type(component), "ctx", new_callable=lambda: {"": Data(text="Empty key data")}):
            result = component.listen_for_data()
            assert result.text == "Empty key data"

    def test_whitespace_context_key(self, component):
        """Test behavior with whitespace context key."""
        component.context_key = "   "

        # Mock the ctx property
        with patch.object(type(component), "ctx", new_callable=lambda: {"   ": Data(text="Whitespace key data")}):
            result = component.listen_for_data()
            assert result.text == "Whitespace key data"

    @pytest.mark.parametrize(
        "context_value",
        [
            Data(text=""),  # Empty Data object
            Data(data={}),  # Empty data dict
            Data(),  # Default Data object
        ],
    )
    def test_listen_for_data_empty_data_objects(self, component, context_value):
        """Test listen_for_data with various empty Data objects."""
        component.context_key = "test_key"

        # Mock the ctx property
        with patch.object(type(component), "ctx", new_callable=lambda: {"test_key": context_value}):
            result = component.listen_for_data()
            assert result == context_value
