import pytest
from unittest.mock import Mock, patch
from langflow.base.memory.model import LCChatMemoryComponent
from base.langflow.components.memories.gridgain import GridGainChatMemory


# Test component class
def test_gridgain_chat_memory_initialization():
    """Test the basic initialization of GridGainChatMemory component."""
    memory = GridGainChatMemory()
    assert memory.name == "GridGainChatMemory"
    assert memory.display_name == "GridGain Chat Memory"
    assert isinstance(memory, LCChatMemoryComponent)
    
    # Verify default values
    assert memory.host == "localhost"
    assert memory.port == "10800"
    assert memory.cache_name == "langchain_message_store"
    assert memory.client_type == "pygridgain"

@pytest.mark.parametrize(
    "client_type,expected_module",
    [
        ("pyignite", "pyignite"),
        ("pygridgain", "pygridgain"),
    ],
)
def test_client_creation_with_different_types(client_type, expected_module):
    """Test creation of different client types."""
    memory = GridGainChatMemory()
    memory.client_type = client_type
    
    with patch(f"{expected_module}.Client") as mock_client:
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        
        with patch("langchain_gridgain.chat_message_histories.GridGainChatMessageHistory"):
            memory.build_message_history()
            
        mock_client.assert_called_once()
        mock_client_instance.connect.assert_called_once_with(
            memory.host, 
            int(memory.port)
        )

def test_invalid_client_type():
    """Test handling of invalid client type."""
    memory = GridGainChatMemory()
    memory.client_type = "invalid_client"
    
    with pytest.raises(ValueError) as exc_info:
        memory.build_message_history()
    
    assert "Invalid client_type" in str(exc_info.value)
    assert "Must be either 'pyignite' or 'pygridgain'" in str(exc_info.value)

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
            history = memory.build_message_history()
            
            # Verify GridGainChatMessageHistory was created with correct parameters
            mock_history.assert_called_once_with(
                session_id="test_session",
                cache_name="test_cache",
                client=mock_client_instance
            )

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

def test_input_validation():
    """Test validation of required input parameters."""
    memory = GridGainChatMemory()
    
    # Verify required inputs are present
    required_inputs = ["host", "port", "cache_name", "client_type"]
    for input_field in memory.inputs:
        if input_field.name in required_inputs:
            assert input_field.required is True
