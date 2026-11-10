"""Unit tests for conversation context ordering in agent components.

This test ensures that conversation context maintains proper chronological order
(oldest → newest → current input) rather than reverse ordering which breaks
SPARC tool validation and conversation flow understanding.
"""

from langchain_core.messages import AIMessage, HumanMessage
from lfx.base.agents.altk_base_agent import ALTKBaseAgentComponent
from lfx.schema.message import Message


class TestALTKAgentContextOrdering:
    """Test conversation context ordering in ALTK agent components."""

    def test_conversation_context_chronological_order(self):
        """Test that build_conversation_context maintains proper chronological order.

        This test validates the fix for the conversation ordering bug where
        current input was being prepended to chat history instead of appended,
        causing reverse chronological order that broke SPARC validation.
        """
        # Create test messages in chronological order
        chat_history = [
            Message(text="353454", sender="User", sender_name="User"),  # oldest message
            Message(text="plus", sender="AI", sender_name="Assistant"),  # middle message
            Message(text="confusion", sender="User", sender_name="User"),  # newest message
        ]
        current_input = Message(text="what?", sender="User", sender_name="User")  # current input

        # Create mock agent component
        class TestAgent(ALTKBaseAgentComponent):
            def __init__(self):
                self.input_value = current_input
                self.chat_history = chat_history

        agent = TestAgent()

        # Build conversation context
        context = agent.build_conversation_context()

        # Extract message contents for validation
        contents = [msg.content for msg in context]

        # Validate chronological order: oldest → middle → newest → current
        expected_order = ["353454", "plus", "confusion", "what?"]
        assert contents == expected_order, (
            f"Conversation context not in chronological order. Expected: {expected_order}, Got: {contents}"
        )

        # Verify all messages are present
        assert len(context) == 4, f"Expected 4 messages, got {len(context)}"

        # Verify message types based on original senders
        expected_types = [HumanMessage, AIMessage, HumanMessage, HumanMessage]  # User, AI, User, User
        for i, (msg, expected_type) in enumerate(zip(context, expected_types, strict=True)):
            assert isinstance(msg, expected_type), (
                f"Message {i} has wrong type. Expected {expected_type.__name__}, got {type(msg).__name__}"
            )

    def test_conversation_context_empty_history(self):
        """Test conversation context with empty chat history."""
        current_input = Message(text="hello", sender="User", sender_name="User")

        class TestAgent(ALTKBaseAgentComponent):
            def __init__(self):
                self.input_value = current_input
                self.chat_history = []

        agent = TestAgent()
        context = agent.build_conversation_context()

        # Should only contain current input
        assert len(context) == 1
        assert context[0].content == "hello"

    def test_conversation_context_no_current_input(self):
        """Test conversation context with no current input."""
        chat_history = [Message(text="old message", sender="User", sender_name="User")]

        class TestAgent(ALTKBaseAgentComponent):
            def __init__(self):
                self.input_value = None
                self.chat_history = chat_history

        agent = TestAgent()
        context = agent.build_conversation_context()

        # Should only contain chat history
        assert len(context) == 1
        assert context[0].content == "old message"

    def test_conversation_context_single_turn(self):
        """Test conversation context in single-turn scenario."""
        current_input = Message(text="single question", sender="User", sender_name="User")

        class TestAgent(ALTKBaseAgentComponent):
            def __init__(self):
                self.input_value = current_input
                self.chat_history = None

        agent = TestAgent()
        context = agent.build_conversation_context()

        # Should only contain current input
        assert len(context) == 1
        assert context[0].content == "single question"

    def test_conversation_context_multi_turn_regression(self):
        """Regression test for multi-turn conversation ordering bug.

        This test specifically validates that the bug where SPARC validation
        received messages in [newest, oldest, middle] order is fixed.
        """
        # Simulate the exact scenario that was failing
        chat_history = [
            Message(text="353454", sender="User", sender_name="User"),
            Message(text="plus", sender="AI", sender_name="Assistant"),
            Message(text="confusion", sender="User", sender_name="User"),
        ]
        current_input = Message(text="what?", sender="User", sender_name="User")

        class TestAgent(ALTKBaseAgentComponent):
            def __init__(self):
                self.input_value = current_input
                self.chat_history = chat_history

        agent = TestAgent()
        context = agent.build_conversation_context()
        contents = [msg.content for msg in context]

        # Verify the bug is fixed - should NOT be in reverse order
        buggy_order = ["what?", "353454", "plus", "confusion"]  # Old buggy behavior
        correct_order = ["353454", "plus", "confusion", "what?"]  # Expected behavior

        assert contents != buggy_order, "Bug regression: context in reverse order!"
        assert contents == correct_order, f"Expected {correct_order}, got {contents}"
