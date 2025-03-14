import time

import pygridgain
import pytest
from base.langflow.components.memories.gridgain import GridGainChatMemory
from langchain_gridgain.chat_message_histories import GridGainChatMessageHistory


class TestGridGainChatMemoryReal:
    @pytest.fixture(scope="class")
    def gridgain_server(self):
        """Fixture to ensure GridGain server is available."""
        client = pygridgain.Client()
        try:
            client.connect("localhost", 10800)
            yield client
            client.close()
        except Exception as e:
            pytest.skip(f"GridGain server not available: {e}")
            raise

    @pytest.fixture
    def test_cache_name(self):
        """Generate unique cache name for each test."""
        return f"test_cache_{int(time.time())}"

    def test_basic_connection(self, test_cache_name):
        """Test basic connection and component creation."""
        # Arrange
        component = GridGainChatMemory(
            host="localhost",
            port="10800",
            cache_name=test_cache_name,
            session_id="test_session_1",
            client_type="pygridgain"
        )

        # Act
        memory = component.build_message_history()

        # Assert
        assert isinstance(memory, GridGainChatMessageHistory)
        assert memory.cache_name == test_cache_name
        assert memory.session_id == "test_session_1"

    def test_multiple_sessions(self, test_cache_name):
        """Test handling multiple chat sessions."""
        # Arrange
        session_ids = ["session_1", "session_2", "session_3"]
        memories = []

        # Act
        for session_id in session_ids:
            component = GridGainChatMemory(
                host="localhost",
                port="10800",
                cache_name=test_cache_name,
                session_id=session_id,
                client_type="pygridgain"
            )
            memories.append(component.build_message_history())

        # Assert - Each session should be independent
        for i, memory in enumerate(memories):
            assert memory.session_id == session_ids[i]
            assert memory.cache_name == test_cache_name

    def test_message_persistence(self, test_cache_name):
        """Test that messages are properly stored and retrieved."""
        # Arrange
        component = GridGainChatMemory(
            host="localhost",
            port="10800",
            cache_name=test_cache_name,
            session_id="persistence_test",
            client_type="pygridgain"
        )
        memory = component.build_message_history()

        # Act - Add messages
        test_messages = [
            ("human", "Hello, how are you?"),
            ("ai", "I'm doing well, thank you!"),
            ("human", "What's the weather like?"),
            ("ai", "I don't have access to current weather information.")
        ]

        for role, content in test_messages:
            if role == "human":
                memory.add_user_message(content)
            else:
                memory.add_ai_message(content)

        # Assert - Verify messages are stored
        messages = memory.messages
        assert len(messages) == len(test_messages)
        for i, (role, content) in enumerate(test_messages):
            assert messages[i].content == content
            assert messages[i].type.lower() == role

    def test_cache_isolation(self):
        """Test that different caches don't interfere with each other."""
        # Arrange
        cache1_name = f"test_cache_1_{int(time.time())}"
        cache2_name = f"test_cache_2_{int(time.time())}"

        component1 = GridGainChatMemory(
            host="localhost",
            port="10800",
            cache_name=cache1_name,
            session_id="isolation_test",
            client_type="pygridgain"
        )

        component2 = GridGainChatMemory(
            host="localhost",
            port="10800",
            cache_name=cache2_name,
            session_id="isolation_test",
            client_type="pygridgain"
        )

        # Act
        memory1 = component1.build_message_history()
        memory2 = component2.build_message_history()

        # Add messages to first cache
        memory1.add_user_message("Message in cache 1")

        # Add different message to second cache
        memory2.add_user_message("Message in cache 2")

        # Assert
        assert len(memory1.messages) == 1
        assert len(memory2.messages) == 1
        assert memory1.messages[0].content == "Message in cache 1"
        assert memory2.messages[0].content == "Message in cache 2"

    def test_error_handling(self):
        """Test error handling with invalid connection parameters."""
        # Arrange
        component = GridGainChatMemory(
            host="invalid_host",
            port="12345",
            cache_name="test_cache",
            session_id="error_test",
            client_type="pygridgain"
        )

        # Act & Assert
        with pytest.raises(ConnectionError) as exc_info:
            component.build_message_history()
        assert "Failed to connect to GridGain server" in str(exc_info.value)

    def test_large_message_handling(self, test_cache_name):
        """Test handling of large messages."""
        # Arrange
        component = GridGainChatMemory(
            host="localhost",
            port="10800",
            cache_name=test_cache_name,
            session_id="large_message_test",
            client_type="pygridgain"
        )
        memory = component.build_message_history()

        # Create a large message (1MB)
        large_message = "x" * (1024 * 1024)

        # Act
        memory.add_user_message(large_message)

        # Assert
        assert len(memory.messages) == 1
        assert len(memory.messages[0].content) == len(large_message)

    def test_concurrent_sessions(self, test_cache_name):
        """Test concurrent session handling."""
        import queue
        import threading

        def run_session(session_id, message, results):
            try:
                component = GridGainChatMemory(
                    host="localhost",
                    port="10800",
                    cache_name=test_cache_name,
                    session_id=session_id,
                    client_type="pygridgain"
                )
                memory = component.build_message_history()
                memory.add_user_message(message)
                results.put((session_id, len(memory.messages)))
            except Exception as e:
                results.put((session_id, str(e)))
                raise

        # Arrange
        sessions = [
            ("concurrent_1", "Message 1"),
            ("concurrent_2", "Message 2"),
            ("concurrent_3", "Message 3")
        ]
        results = queue.Queue()
        threads = []

        # Act
        for session_id, message in sessions:
            thread = threading.Thread(
                target=run_session,
                args=(session_id, message, results)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Assert
        result_dict = {}
        while not results.empty():
            session_id, result = results.get()
            result_dict[session_id] = result

        assert len(result_dict) == len(sessions)
        for session_id, _ in sessions:
            assert result_dict[session_id] == 1
