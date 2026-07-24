"""Tests for Component developer experience (DX) features.

Tests for __dir__, describe(), and set() signature features.
"""

from __future__ import annotations

import inspect

from lfx.components.input_output.chat import ChatInput
from lfx.components.input_output.chat_output import ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output


class SimpleTestComponent(Component):
    """A simple component for testing DX features."""

    display_name = "Simple Test"
    description = "A test component"

    inputs = [
        MessageTextInput(name="text_input", display_name="Text", info="Input text"),
        MessageTextInput(name="prefix", display_name="Prefix", value="Hello"),
    ]
    outputs = [
        Output(display_name="Result", name="result", method="process_text"),
    ]

    def process_text(self) -> str:
        return f"{self.prefix} {self.text_input}"


class TestComponentDir:
    """Tests for __dir__ method."""

    def test_dir_includes_input_names(self):
        """__dir__ includes input names for autocomplete."""
        comp = SimpleTestComponent()
        dir_items = dir(comp)

        assert "text_input" in dir_items
        assert "prefix" in dir_items

    def test_dir_includes_output_methods(self):
        """__dir__ includes output method names for connection."""
        comp = SimpleTestComponent()
        dir_items = dir(comp)

        assert "process_text" in dir_items

    def test_dir_includes_standard_attributes(self):
        """__dir__ still includes standard class attributes."""
        comp = SimpleTestComponent()
        dir_items = dir(comp)

        # Should include standard methods
        assert "set" in dir_items
        assert "describe" in dir_items
        assert "list_inputs" in dir_items
        assert "list_outputs" in dir_items

    def test_dir_with_chat_input(self):
        """__dir__ works with built-in ChatInput component."""
        chat_input = ChatInput()
        dir_items = dir(chat_input)

        # Should include the output method
        assert "message_response" in dir_items
        # Should include input names
        assert "input_value" in dir_items

    def test_dir_with_chat_output(self):
        """__dir__ works with built-in ChatOutput component."""
        chat_output = ChatOutput()
        dir_items = dir(chat_output)

        # Should include input names
        assert "input_value" in dir_items


class TestSetSignature:
    """Tests for dynamic set() method signature."""

    def test_set_signature_shows_inputs(self):
        """set() signature includes input parameter names."""
        comp = SimpleTestComponent()
        sig = inspect.signature(comp.set)
        param_names = list(sig.parameters.keys())

        # Should include input names (self is not shown for bound methods)
        assert "text_input" in param_names
        assert "prefix" in param_names

    def test_set_signature_shows_defaults(self):
        """set() signature includes default values."""
        comp = SimpleTestComponent()
        sig = inspect.signature(comp.set)

        # prefix has default "Hello"
        prefix_param = sig.parameters["prefix"]
        assert prefix_param.default == "Hello"

    def test_set_signature_keyword_only(self):
        """set() parameters are keyword-only."""
        comp = SimpleTestComponent()
        sig = inspect.signature(comp.set)

        for name, param in sig.parameters.items():
            if name != "self":
                assert param.kind == inspect.Parameter.KEYWORD_ONLY

    def test_set_signature_with_chat_input(self):
        """set() signature works with ChatInput."""
        chat_input = ChatInput()
        sig = inspect.signature(chat_input.set)
        param_names = list(sig.parameters.keys())

        assert "input_value" in param_names
        assert "session_id" in param_names


class TestDescribe:
    """Tests for describe() method."""

    def test_describe_returns_string(self):
        """describe() returns a string."""
        comp = SimpleTestComponent()
        result = comp.describe()

        assert isinstance(result, str)

    def test_describe_includes_class_name(self):
        """describe() includes the class name."""
        comp = SimpleTestComponent()
        result = comp.describe()

        assert "SimpleTestComponent" in result

    def test_describe_includes_display_name(self):
        """describe() includes the display name."""
        comp = SimpleTestComponent()
        result = comp.describe()

        assert "Simple Test" in result

    def test_describe_lists_inputs(self):
        """describe() lists input names."""
        comp = SimpleTestComponent()
        result = comp.describe()

        assert "Inputs:" in result
        assert "text_input" in result
        assert "prefix" in result

    def test_describe_lists_outputs(self):
        """describe() lists outputs with method names."""
        comp = SimpleTestComponent()
        result = comp.describe()

        assert "Outputs:" in result
        assert "result" in result
        assert "process_text" in result

    def test_describe_shows_output_types(self):
        """describe() shows output types."""
        chat_input = ChatInput()
        result = chat_input.describe()

        assert "Message" in result

    def test_describe_with_chat_input(self):
        """describe() works with ChatInput."""
        chat_input = ChatInput()
        result = chat_input.describe()

        assert "ChatInput" in result
        assert "Chat Input" in result
        assert "input_value" in result
        assert "message_response" in result
