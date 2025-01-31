import pytest
import uuid
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ChatMessage
from base.langflow.components.memories.gridgain import GridGainChatMemory

import asyncio

# Register the benchmark mark
def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: mark test to skip blockbuster checks")

@pytest.mark.benchmark
class TestGridGainChatMemory:
    @pytest.fixture(params=['pygridgain'])
    def gridgain_memory(self, request):
        """
        Fixture to create GridGainChatMemory instances for both client types
        """

        # Generate a unique session ID for each test
        session_id = str(uuid.uuid4())
        
        # Create an instance using the input parameters
        memory = GridGainChatMemory()
        memory.host = 'localhost'
        memory.port = '10800'
        memory.cache_name = 'test_langchain_message_store'
        memory.session_id = session_id
        memory.client_type = request.param
        
        yield memory
        
        # Cleanup: Clear the cache after each test
        try:
            import pygridgain
            
            if request.param == 'pyignite':
                client = pygridgain.Client()
            
            client.connect('localhost', 10800)
            client.cache_clear('test_langchain_message_store')
        except Exception as e:
            print(f"Cleanup failed: {e}")

    @pytest.mark.asyncio
    async def test_build_message_history_connection(self, gridgain_memory):
        """
        Test that a message history can be built successfully
        """
        try:
            message_history = await asyncio.to_thread(gridgain_memory.build_message_history)
            assert message_history is not None, "Message history should not be None"
        except Exception as e:
            pytest.fail(f"Failed to build message history: {e}")

    @pytest.mark.asyncio
    async def test_message_storage_and_retrieval(self, gridgain_memory):
        """
        Test storing and retrieving messages
        """
        # Build message history
        message_history = await asyncio.to_thread(gridgain_memory.build_message_history)
        
        # Add some messages
        test_messages = [
            HumanMessage(content="Hello, how are you?"),
            AIMessage(content="I'm doing well, thank you!"),
            HumanMessage(content="What's the weather like?")
        ]
        
        # Store messages
        for msg in test_messages:
            await asyncio.to_thread(message_history.add_message, msg)
        
        # Retrieve messages
        stored_messages = message_history.messages
        
        # Assertions
        assert len(stored_messages) == len(test_messages), "Number of stored messages should match"
        
        for original, stored in zip(test_messages, stored_messages):
            assert original.content == stored.content, "Message content should match"
            assert type(original) == type(stored), "Message type should match"

    @pytest.mark.asyncio
    async def test_different_session_ids(self):
        """
        Test that different session IDs create separate message histories
        """

        # Create two instances with different session IDs
        session_id1 = str(uuid.uuid4())
        session_id2 = str(uuid.uuid4())

        memory1 = GridGainChatMemory()
        memory1.host = 'localhost'
        memory1.port = '10800'
        memory1.cache_name = 'test_langchain_message_store'
        memory1.session_id = session_id1
        memory1.client_type = 'pyignite'

        memory2 = GridGainChatMemory()
        memory2.host = 'localhost'
        memory2.port = '10800'
        memory2.cache_name = 'test_langchain_message_store'
        memory2.session_id = session_id2
        memory2.client_type = 'pyignite'

        # Add messages to first session
        history1 = await asyncio.to_thread(memory1.build_message_history)
        await asyncio.to_thread(history1.add_message, HumanMessage(content="Session 1 message"))

        # Add messages to second session
        history2 = await asyncio.to_thread(memory2.build_message_history)
        await asyncio.to_thread(history2.add_message, HumanMessage(content="Session 2 message"))

        # Verify messages are separate
        assert len(history1.messages) == 1
        assert len(history2.messages) == 1
        assert history1.messages[0].content != history2.messages[0].content

    @pytest.mark.asyncio
    async def test_invalid_client_type(self):
        """
        Test that an invalid client type raises a ValueError
        """

        memory = GridGainChatMemory()
        memory.host = 'localhost'
        memory.port = '10800'
        memory.cache_name = 'test_langchain_message_store'
        memory.client_type = 'invalid_client'

        with pytest.raises(ValueError, match="Invalid client_type. Must be either 'pyignite' or 'pygridgain'."):
            await asyncio.to_thread(memory.build_message_history)


@pytest.mark.benchmark
class TestGridGainChatMemory2:
    @pytest.fixture(scope="function")
    async def gridgain_server(self):  # Added self parameter
        """Fixture to ensure GridGain server is running."""
        import pygridgain
        client = pygridgain.Client()
        try:
            client.connect("localhost", 10800)
            yield client
        except Exception as e:
            pytest.skip(f"GridGain server not available: {str(e)}")
        finally:
            if client:
                client.close()

    @pytest.fixture(scope="function")
    def chat_memory(self, gridgain_server):
        """Fixture to create a fresh GridGainChatMemory instance for each test."""

        memory = GridGainChatMemory()
        memory.host = "localhost"
        memory.port = "10800"
        memory.cache_name = f"test_cache_{uuid.uuid4().hex}"
        memory.session_id = f"test_session_{uuid.uuid4().hex}"
        memory.client_type = "pygridgain"
        return memory

    @pytest.mark.asyncio
    async def test_initial_connection(self, chat_memory):
        """Test that the component can successfully connect to GridGain."""
        message_history = await asyncio.to_thread(chat_memory.build_message_history)
        assert message_history is not None
        assert message_history.messages == []

    @pytest.mark.asyncio
    async def test_add_and_retrieve_messages(self, chat_memory):
        """Test adding different types of messages and retrieving them."""
        message_history = await asyncio.to_thread(chat_memory.build_message_history)
        
        # Add different types of messages
        messages = [
            HumanMessage(content="Hello!"),
            AIMessage(content="Hi there!"),
            SystemMessage(content="System notification"),
            ChatMessage(content="Custom role message", role="custom")
        ]
        
        for message in messages:
            await asyncio.to_thread(message_history.add_message, message)
        
        # Verify messages were stored correctly
        stored_messages = message_history.messages
        assert len(stored_messages) == len(messages)
        
        for original, stored in zip(messages, stored_messages):
            assert stored.content == original.content
            assert type(stored) == type(original)
            if isinstance(original, ChatMessage):
                assert stored.role == original.role

    @pytest.mark.asyncio
    async def test_persistence_across_sessions(self, chat_memory):
        """Test that messages persist when creating new message history instances."""
        # First session
        message_history1 = await asyncio.to_thread(chat_memory.build_message_history)
        test_message = HumanMessage(content="Test persistence")
        await asyncio.to_thread(message_history1.add_message, test_message)
        
        # Second session with same settings
        message_history2 = await asyncio.to_thread(chat_memory.build_message_history)
        stored_messages = message_history2.messages
        
        assert len(stored_messages) == 1
        assert stored_messages[0].content == "Test persistence"
        assert isinstance(stored_messages[0], HumanMessage)

    @pytest.mark.asyncio
    async def test_additional_kwargs_preservation(self, chat_memory):
        """Test that additional kwargs are preserved in serialization."""
        message_history = await asyncio.to_thread(chat_memory.build_message_history)
        
        message = HumanMessage(
            content="Test with metadata",
            additional_kwargs={"metadata": {"timestamp": "2024-01-31", "user_id": "123"}}
        )
        
        await asyncio.to_thread(message_history.add_message, message)
        stored_messages = message_history.messages
        
        assert len(stored_messages) == 1
        assert stored_messages[0].additional_kwargs == message.additional_kwargs


    @pytest.mark.parametrize("message_content", [
        "Simple message",
        "Message with unicode: 你好",
        "Message with special chars: !@#$%^&*()",
        "Very long message: " + "x" * 1000
    ])
    @pytest.mark.asyncio
    async def test_message_content_handling(self, chat_memory, message_content):
        """Test handling of various message content types."""
        message_history = await asyncio.to_thread(chat_memory.build_message_history)
        message = HumanMessage(content=message_content)
        
        await asyncio.to_thread(message_history.add_message, message)
        stored_messages = message_history.messages
        
        assert len(stored_messages) == 1
        assert stored_messages[0].content == message_content
