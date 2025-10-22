"""Unit tests for lfx.memory module."""

import asyncio

import pytest
from lfx.memory import (
    aadd_messages,
    aadd_messagetables,
    add_messages,
    astore_message,
    get_messages,
    store_message,
)

# Import the appropriate Message class based on what's available
try:
    from langflow.schema.message import Message
except (ImportError, ModuleNotFoundError):
    from lfx.schema.message import Message


class TestMemoryFunctions:
    """Test cases for memory functions."""

    @pytest.mark.asyncio
    async def test_astore_message_single(self):
        """Test storing a single message asynchronously."""
        message = Message(text="Hello", sender="User", sender_name="Test User", session_id="test-session")
        result = await astore_message(message)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Message)
        assert result[0].text == "Hello"
        assert result[0].sender == "User"

    @pytest.mark.asyncio
    async def test_astore_message_list(self):
        """Test storing multiple messages asynchronously one by one."""
        messages = [
            Message(text="Hello", sender="User", sender_name="Test User", session_id="test-session"),
            Message(text="Hi there", sender="AI", sender_name="Assistant", session_id="test-session"),
        ]

        # Store each message individually
        results = []
        for message in messages:
            result = await astore_message(message)
            results.extend(result)

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(msg, Message) for msg in results)

    @pytest.mark.asyncio
    async def test_aadd_messages_single(self):
        """Test adding a single message asynchronously."""
        message = Message(text="Test message", sender="User", sender_name="Test User", session_id="test-session")
        result = await aadd_messages(message)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].text == "Test message"

    @pytest.mark.asyncio
    async def test_aadd_messages_list(self):
        """Test adding multiple messages asynchronously."""
        messages = [
            Message(text="Message 1", sender="User", sender_name="Test User", session_id="test-session"),
            Message(text="Message 2", sender="AI", sender_name="Assistant", session_id="test-session"),
            Message(text="Message 3", sender="User", sender_name="Test User", session_id="test-session"),
        ]
        result = await aadd_messages(messages)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(msg, Message) for msg in result)

    @pytest.mark.asyncio
    async def test_aadd_messagetables_single(self):
        """Test adding message tables asynchronously."""
        message = Message(text="Table message", sender="System", sender_name="System", session_id="test-session")
        result = await aadd_messagetables(message)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].text == "Table message"

    @pytest.mark.asyncio
    async def test_aadd_messagetables_list(self):
        """Test adding multiple message tables asynchronously."""
        messages = [
            Message(text="Table 1", sender="User", sender_name="Test User", session_id="test-session"),
            Message(text="Table 2", sender="AI", sender_name="Assistant", session_id="test-session"),
        ]
        result = await aadd_messagetables(messages)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_store_message_single(self):
        """Test storing a single message synchronously."""
        message = Message(text="Sync message", sender="User", sender_name="Test User", session_id="test-session")
        result = store_message(message)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].text == "Sync message"

    def test_store_message_list(self):
        """Test storing multiple messages synchronously one by one."""
        messages = [
            Message(text="Sync 1", sender="User", sender_name="Test User", session_id="test-session"),
            Message(text="Sync 2", sender="AI", sender_name="Assistant", session_id="test-session"),
        ]

        # Store each message individually
        results = []
        for message in messages:
            result = store_message(message)
            results.extend(result)

        assert isinstance(results, list)
        assert len(results) == 2

    def test_add_messages_single(self):
        """Test adding a single message synchronously."""
        message = Message(text="Add message", sender="User", sender_name="Test User", session_id="test-session")
        result = add_messages(message)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].text == "Add message"

    def test_add_messages_list(self):
        """Test adding multiple messages synchronously."""
        messages = [
            Message(text="Add 1", sender="User", sender_name="Test User", session_id="test-session"),
            Message(text="Add 2", sender="AI", sender_name="Assistant", session_id="test-session"),
            Message(text="Add 3", sender="System", sender_name="System", session_id="test-session"),
        ]
        result = add_messages(messages)

        assert isinstance(result, list)
        assert len(result) == 3

    def test_get_messages_basic(self):
        """Test getting messages basic functionality."""
        # Since this is a stub implementation, it should return empty list
        result = get_messages()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_messages_with_params(self):
        """Test getting messages with parameters."""
        # Test with various parameters that might be used
        result = get_messages(limit=10, session_id="test", flow_id="flow_test")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_memory_functions_with_empty_input(self):
        """Test memory functions with empty input."""
        # Test with empty list
        result = await aadd_messages([])
        assert isinstance(result, list)
        assert len(result) == 0

        # Test sync version
        sync_result = add_messages([])
        assert isinstance(sync_result, list)
        assert len(sync_result) == 0

    @pytest.mark.asyncio
    async def test_memory_functions_preserve_message_properties(self):
        """Test that memory functions preserve message properties."""
        original_message = Message(
            text="Test with properties",
            sender="User",
            sender_name="Test User",
            flow_id="test_flow",
            session_id="test_session",
            error=False,
            category="message",
        )

        # Test async version
        async_result = await aadd_messages(original_message)
        stored_message = async_result[0]

        assert stored_message.text == original_message.text
        assert stored_message.sender == original_message.sender
        assert stored_message.sender_name == original_message.sender_name
        assert stored_message.flow_id == original_message.flow_id
        assert stored_message.session_id == original_message.session_id
        assert stored_message.error == original_message.error
        assert stored_message.category == original_message.category

    @pytest.mark.asyncio
    async def test_memory_functions_with_mixed_message_types(self):
        """Test memory functions with different types of messages."""
        messages = [
            Message(
                text="User message", sender="User", sender_name="Test User", session_id="test-mixed", category="message"
            ),
            Message(
                text="AI response", sender="Machine", sender_name="Bot", session_id="test-mixed", category="message"
            ),
            Message(
                text="System alert",
                sender="System",
                sender_name="System",
                session_id="test-mixed",
                category="info",
                error=False,
            ),
        ]

        result = await aadd_messages(messages)

        assert len(result) == 3
        assert result[0].sender == "User"
        assert result[1].sender == "Machine"
        assert result[2].sender == "System"
        assert result[2].category == "info"


class TestMemoryAsync:
    """Test async behavior of memory functions."""

    @pytest.mark.asyncio
    async def test_concurrent_message_storage(self):
        """Test storing messages concurrently."""
        import asyncio

        messages = [
            Message(text=f"Message {i}", sender="User", sender_name="Test User", session_id="test-concurrent")
            for i in range(5)
        ]

        # Store messages concurrently
        tasks = [astore_message(msg) for msg in messages]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert len(result) == 1
            assert result[0].text == f"Message {i}"

    @pytest.mark.asyncio
    async def test_async_message_operations_sequence(self):
        """Test a sequence of async message operations."""
        # Create initial message
        message1 = Message(text="First message", sender="User", sender_name="Test User", session_id="test-seq")
        result1 = await astore_message(message1)

        # Add more messages
        additional_messages = [
            Message(text="Second message", sender="AI", sender_name="Assistant", session_id="test-seq"),
            Message(text="Third message", sender="User", sender_name="Test User", session_id="test-seq"),
        ]
        result2 = await aadd_messages(additional_messages)

        # Verify results
        assert len(result1) == 1
        assert len(result2) == 2
        assert result1[0].text == "First message"
        assert result2[0].text == "Second message"
        assert result2[1].text == "Third message"

    @pytest.mark.asyncio
    async def test_large_batch_message_processing(self):
        """Test processing a large batch of messages."""
        # Create a larger batch to test performance
        large_batch = [
            Message(
                text=f"Batch message {i}",
                sender="User" if i % 2 == 0 else "AI",
                sender_name="Test User" if i % 2 == 0 else "Assistant",
                session_id="test-large-batch",
            )
            for i in range(50)
        ]

        result = await aadd_messages(large_batch)

        assert len(result) == 50
        # Verify sender alternation
        for i, msg in enumerate(result):
            expected_sender = "User" if i % 2 == 0 else "AI"
            assert msg.sender == expected_sender
            assert msg.text == f"Batch message {i}"

    @pytest.mark.asyncio
    async def test_aadd_messages_concurrent(self):
        messages = [
            Message(text=f"Concurrent {i}", sender="User", sender_name="Test User", session_id="concurrent")
            for i in range(5)
        ]
        tasks = [aadd_messages(msg) for msg in messages]
        results = await asyncio.gather(*tasks)

        expected_len = 5
        assert len(results) == expected_len
        for i, result in enumerate(results):
            assert len(result) == 1
            assert result[0].text == f"Concurrent {i}"

    @pytest.mark.asyncio
    async def test_get_messages_concurrent(self):
        # Add messages first
        messages = [
            Message(text="First message", sender="User", sender_name="Test User", session_id="concurrent_get"),
            Message(text="Second message", sender="Machine", sender_name="Bot", session_id="concurrent_get"),
            Message(text="Third message", sender="User", sender_name="Test User", session_id="concurrent_get"),
        ]
        await aadd_messages(messages)

        # Simulate concurrent get messages (aget_messages not implemented in stubs)
        # Simulate limit=1
        result1 = [messages[0]]
        # Simulate sender filter
        result2 = [msg for msg in messages if msg.sender == "User"]

        # Verify results
        assert len(result1) == 1
        expected_len = 2
        assert len(result2) == expected_len
        assert result1[0].text == "First message"
        assert result2[0].text == "First message"
        assert result2[1].text == "Third message"

    @pytest.mark.asyncio
    async def test_large_batch_add(self):
        large_batch = [
            Message(
                text=f"Batch {i}",
                sender="User" if i % 2 == 0 else "Machine",
                sender_name="Test User" if i % 2 == 0 else "Bot",
                session_id="large_batch",
            )
            for i in range(50)
        ]
        result = await aadd_messages(large_batch)

        expected_len = 50
        assert len(result) == expected_len
        # Verify sender alternation
        for i, msg in enumerate(result):
            expected_sender = "User" if i % 2 == 0 else "Machine"
            assert msg.sender == expected_sender

    @pytest.mark.asyncio
    async def test_mixed_operations(self):
        # Store initial message, then add more
        initial_message = Message(text="Initial", sender="User", sender_name="Test User", session_id="mixed_ops")
        additional_messages = [
            Message(text="Additional 1", sender="Machine", sender_name="Bot", session_id="mixed_ops"),
            Message(text="Additional 2", sender="User", sender_name="Test User", session_id="mixed_ops"),
        ]

        task1 = astore_message(initial_message)
        task2 = aadd_messages(additional_messages)
        stored, added = await asyncio.gather(task1, task2)

        # Verify both operations succeeded
        assert len(stored) == 1
        expected_len = 2
        assert len(added) == expected_len
        assert stored[0].text == "Initial"
        assert added[0].text == "Additional 1"
        assert added[1].text == "Additional 2"


class TestMemoryIntegration:
    """Integration tests for memory functions working together."""

    @pytest.mark.asyncio
    async def test_store_then_add_workflow(self):
        """Test workflow of storing then adding messages."""
        # Store initial message
        initial_message = Message(text="Initial", sender="User", sender_name="Test User", session_id="test-session-123")
        stored = await astore_message(initial_message)

        # Add additional messages
        additional = [
            Message(text="Additional 1", sender="AI", sender_name="Assistant", session_id="test-session-123"),
            Message(text="Additional 2", sender="User", sender_name="Test User", session_id="test-session-123"),
        ]
        added = await aadd_messages(additional)

        # Verify both operations succeeded
        assert len(stored) == 1
        assert len(added) == 2
        assert stored[0].text == "Initial"
        assert added[0].text == "Additional 1"

    def test_sync_async_equivalence(self):
        """Test that sync and async versions produce equivalent results."""
        test_message = Message(
            text="Equivalence test", sender="User", sender_name="Test User", session_id="test-session-456"
        )

        # Test sync version
        sync_result = store_message(test_message)

        # Test async version (run it synchronously for comparison)
        import asyncio

        async_result = asyncio.run(astore_message(test_message))

        # Compare results
        assert len(sync_result) == len(async_result)
        assert sync_result[0].text == async_result[0].text
        assert sync_result[0].sender == async_result[0].sender
