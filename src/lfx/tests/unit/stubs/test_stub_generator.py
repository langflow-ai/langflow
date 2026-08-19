"""Tests for stub generator."""

from __future__ import annotations

from lfx.components.input_output.chat import ChatInput
from lfx.components.input_output.chat_output import ChatOutput
from lfx.stubs.generator import generate_stubs_for_component


class TestGenerateStubsForComponent:
    """Tests for generate_stubs_for_component."""

    def test_generates_set_method(self):
        """Generated stub includes set() method."""
        stub = generate_stubs_for_component(ChatOutput)

        assert "def set(" in stub
        assert "self," in stub

    def test_includes_input_parameters(self):
        """Generated stub includes input parameter names."""
        stub = generate_stubs_for_component(ChatOutput)

        assert "input_value:" in stub
        assert "should_store_message:" in stub
        assert "sender:" in stub

    def test_includes_output_methods(self):
        """Generated stub includes output method signatures."""
        stub = generate_stubs_for_component(ChatOutput)

        assert "def message_response(self)" in stub

    def test_set_returns_self(self):
        """set() method returns Self for chaining."""
        stub = generate_stubs_for_component(ChatOutput)

        assert ") -> Self:" in stub

    def test_chat_input_stub(self):
        """ChatInput generates valid stub."""
        stub = generate_stubs_for_component(ChatInput)

        assert "class ChatInput" in stub
        assert "def set(" in stub
        assert "input_value:" in stub

    def test_includes_type_annotations(self):
        """Generated stub includes type annotations."""
        stub = generate_stubs_for_component(ChatOutput)

        # Bool inputs should have bool type
        assert "bool" in stub
        # String inputs should have str type
        assert "str" in stub

    def test_includes_default_values(self):
        """Generated stub includes default values."""
        stub = generate_stubs_for_component(ChatOutput)

        # should_store_message has default True
        assert "= True" in stub
