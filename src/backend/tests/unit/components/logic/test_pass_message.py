import pytest
from langflow.components.logic.pass_message import PassMessageComponent
from langflow.schema.message import Message


class TestPassMessageComponent:
    """Test cases for PassMessageComponent."""

    @pytest.fixture
    def component(self):
        """Create a PassMessageComponent instance for testing."""
        return PassMessageComponent()

    def test_component_initialization(self, component):
        """Test proper initialization of PassMessageComponent."""
        assert component.display_name == "Pass"
        assert component.description == "Forwards the input message, unchanged."
        assert component.name == "Pass"
        assert component.icon == "arrow-right"
        assert component.legacy is True

    def test_inputs_configuration(self, component):
        """Test that inputs are properly configured."""
        assert len(component.inputs) == 2

        input_names = [inp.name for inp in component.inputs]
        assert "input_message" in input_names
        assert "ignored_message" in input_names

        # Test input_message configuration
        input_message = next(inp for inp in component.inputs if inp.name == "input_message")
        assert input_message.display_name == "Input Message"
        assert input_message.required is True
        assert "message to be passed forward" in input_message.info

        # Test ignored_message configuration
        ignored_message = next(inp for inp in component.inputs if inp.name == "ignored_message")
        assert ignored_message.display_name == "Ignored Message"
        assert ignored_message.advanced is True
        assert "workaround for continuity" in ignored_message.info

    def test_outputs_configuration(self, component):
        """Test that outputs are properly configured."""
        assert len(component.outputs) == 1

        output = component.outputs[0]
        assert output.name == "output_message"
        assert output.display_name == "Output Message"
        assert output.method == "pass_message"

    def test_pass_message_basic_functionality(self, component):
        """Test pass_message method basic functionality."""
        # Setup
        test_message = Message(content="Hello World")
        component.input_message = test_message

        # Execute
        result = component.pass_message()

        # Assert
        assert result == test_message
        assert result is test_message  # Should be the same object, not a copy
        assert component.status == test_message

    def test_pass_message_different_message_types(self, component):
        """Test pass_message with different message content types."""
        test_cases = [
            Message(content="Simple text"),
            Message(content=""),  # Empty content
            Message(content="Multi\nline\ntext"),
            Message(content="Special chars: !@#$%^&*()"),
            Message(content="Unicode: 你好世界 🌍"),
            Message(content=None),  # None content
        ]

        for test_message in test_cases:
            component.input_message = test_message

            result = component.pass_message()

            assert result == test_message
            assert result.content == test_message.content
            assert component.status == test_message

    def test_pass_message_with_ignored_message(self, component):
        """Test that ignored_message parameter is truly ignored."""
        # Setup
        input_msg = Message(content="This should be returned")
        ignored_msg = Message(content="This should be ignored")

        component.input_message = input_msg
        component.ignored_message = ignored_msg

        # Execute
        result = component.pass_message()

        # Assert - only input_message should be returned, ignored_message should not affect result
        assert result == input_msg
        assert result != ignored_msg
        assert component.status == input_msg

    def test_pass_message_status_assignment(self, component):
        """Test that status is properly assigned."""
        test_message = Message(content="Status test")
        component.input_message = test_message

        # Initially status might be different

        result = component.pass_message()

        # After calling pass_message, status should be set to input_message
        assert component.status == test_message
        assert component.status == result

    def test_pass_message_no_side_effects(self, component):
        """Test that pass_message doesn't modify the input message."""
        original_content = "Original content"
        test_message = Message(content=original_content)
        component.input_message = test_message

        # Store original properties
        original_id = test_message.id if hasattr(test_message, "id") else None

        result = component.pass_message()

        # Message should be unchanged
        assert test_message.content == original_content
        if original_id is not None and hasattr(test_message, "id"):
            assert test_message.id == original_id

        # Result should be identical
        assert result == test_message

    def test_pass_message_method_signature(self, component):
        """Test that pass_message method has correct signature."""
        import inspect

        sig = inspect.signature(component.pass_message)

        # Should have no parameters except self
        assert len(sig.parameters) == 0

        # Should have Message return annotation
        assert (
            sig.return_annotation == Message
            or str(sig.return_annotation) == "<class 'langflow.schema.message.Message'>"
        )

    def test_component_legacy_status(self, component):
        """Test that component is properly marked as legacy."""
        assert hasattr(component, "legacy")
        assert component.legacy is True

    def test_component_inheritance(self, component):
        """Test that component properly inherits from Component base class."""
        from langflow.custom.custom_component.component import Component

        assert isinstance(component, Component)

    def test_output_method_mapping(self, component):
        """Test that output is correctly mapped to pass_message method."""
        output = component.outputs[0]
        assert hasattr(component, output.method)
        assert callable(getattr(component, output.method))

    def test_message_attributes_preservation(self, component):
        """Test that all message attributes are preserved through pass_message."""
        # Create a message with various attributes
        test_message = Message(
            content="Test content", sender="Test Sender", sender_name="Test Name", session_id="test_session"
        )

        component.input_message = test_message
        result = component.pass_message()

        # All attributes should be preserved
        assert result.content == test_message.content
        assert result.sender == test_message.sender
        assert result.sender_name == test_message.sender_name
        assert result.session_id == test_message.session_id

    def test_pass_message_multiple_calls(self, component):
        """Test calling pass_message multiple times with different inputs."""
        messages = [
            Message(content="First message"),
            Message(content="Second message"),
            Message(content="Third message"),
        ]

        results = []
        for msg in messages:
            component.input_message = msg
            result = component.pass_message()
            results.append(result)

            # Each call should return the correct message
            assert result == msg
            assert component.status == msg

        # All results should be different and correct
        for i, (msg, result) in enumerate(zip(messages, results, strict=False)):
            assert result == msg
            assert result.content == f"{['First', 'Second', 'Third'][i]} message"

    def test_pass_message_with_none_input(self, component):
        """Test pass_message behavior with None input."""
        component.input_message = None

        result = component.pass_message()

        assert result is None
        assert component.status is None

    def test_ignored_message_truly_ignored(self, component):
        """Test that ignored_message has no impact on the result regardless of its value."""
        input_msg = Message(content="Input")

        # Test with different ignored message values
        ignored_values = [
            Message(content="Ignored"),
            None,
            Message(content="Different ignored content"),
        ]

        for ignored_value in ignored_values:
            component.input_message = input_msg
            component.ignored_message = ignored_value

            result = component.pass_message()

            # Result should always be the input_message, regardless of ignored_message
            assert result == input_msg
            assert result.content == "Input"
            assert component.status == input_msg
