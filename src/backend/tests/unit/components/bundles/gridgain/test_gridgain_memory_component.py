from unittest.mock import Mock, patch

import pytest
from base.langflow.components.gridgain import GridGainChatMemory
from langflow.base.memory.model import LCChatMemoryComponent
from langflow.inputs import MessageTextInput


# Test component class
def test_gridgain_chat_memory_initialization():
    """Test the basic initialization of GridGainChatMemory component."""
    memory = GridGainChatMemory()
    assert memory.name == "GridGainChatMemory"
    assert memory.display_name == "GridGain Chat Memory"
    assert isinstance(memory, LCChatMemoryComponent)

    # Verify default values
    assert memory.host == "localhost"
    assert memory.port == 10800
    assert memory.cache_name == "langchain_message_store"
    assert memory.client_type == "pygridgain"
    assert memory.icon == "GridGain"


def test_input_configuration():
    """Test the input field configuration of the component."""
    memory = GridGainChatMemory()

    # Test required inputs
    required_inputs = ["host", "port", "cache_name", "client_type"]
    for input_field in memory.inputs:
        if input_field.name in required_inputs:
            assert input_field.required is True

    # Test session_id configuration
    session_id_input = next(i for i in memory.inputs if i.name == "session_id")
    assert session_id_input.advanced is True
    assert isinstance(session_id_input, MessageTextInput)


def test_connection_error_handling():
    """Test handling of connection errors."""
    memory = GridGainChatMemory()

    with patch("pygridgain.Client") as mock_client:
        mock_client_instance = Mock()
        mock_client_instance.connect.side_effect = Exception("Connection failed")
        mock_client.return_value = mock_client_instance

        with pytest.raises(ConnectionError) as exc_info:
            memory.build_message_history()

        assert "Failed to connect to GridGain server" in str(exc_info.value)


def test_successful_message_history_creation():
    """Test successful creation of GridGainChatMessageHistory."""
    memory = GridGainChatMemory()
    memory.session_id = "test_session"
    memory.cache_name = "test_cache"

    with patch("pygridgain.Client") as mock_client:
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance

        with patch("langchain_gridgain.chat_message_histories.GridGainChatMessageHistory") as mock_history:
            # Verify GridGainChatMessageHistory was created with correct parameters
            assert mock_history(session_id="test_session", cache_name="test_cache", client=mock_client_instance)


@pytest.fixture
def mock_client():
    """Fixture for mocked GridGain client."""
    with patch("pygridgain.Client") as mock:
        client_instance = Mock()
        mock.return_value = client_instance
        yield client_instance


def test_custom_connection_parameters(mock_client):
    """Test connection with custom host and port."""
    memory = GridGainChatMemory()
    memory.host = "custom_host"
    memory.port = "12345"

    with patch("langchain_gridgain.chat_message_histories.GridGainChatMessageHistory"):
        memory.build_message_history()

    mock_client.connect.assert_called_once_with("custom_host", 12345)
