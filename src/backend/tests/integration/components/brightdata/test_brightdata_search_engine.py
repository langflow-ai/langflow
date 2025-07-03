"""Unit tests for BrightDataSearchEngineComponent"""
import pytest
from unittest.mock import Mock, patch
from langflow.components.brightdata import BrightDataSearchEngineComponent
from langflow.schema import Data
from langflow.schema.message import Message


def test_brightdata_search_engine_initialization():
    """Test that BrightDataSearchEngineComponent can be initialized correctly"""
    component = BrightDataSearchEngineComponent()
    
    # Test component attributes
    assert component.display_name == "Bright Data Search Engine"
    assert component.name == "BrightDataSearchEngine"
    assert component.icon == "BrightData"
    assert "search" in component.description.lower()
    
    # Test that inputs are defined
    assert hasattr(component, 'inputs')
    assert len(component.inputs) > 0
    
    # Check for required inputs
    input_names = [inp.name for inp in component.inputs]
    assert "api_token" in input_names
    assert "query_input" in input_names
    assert "engine" in input_names
    
    # Test that outputs are defined
    assert hasattr(component, 'outputs')
    assert len(component.outputs) > 0
    
    # Check for expected outputs
    output_names = [out.name for out in component.outputs]
    assert "results" in output_names


def test_get_query_from_input_string():
    """Test query extraction from string input"""
    component = BrightDataSearchEngineComponent()
    component.query_input = "artificial intelligence"
    
    query = component.get_query_from_input()
    assert query == "artificial intelligence"


def test_get_query_from_input_message():
    """Test query extraction from Message object"""
    component = BrightDataSearchEngineComponent()
    component.query_input = Message(text="machine learning")
    
    query = component.get_query_from_input()
    assert query == "machine learning"


def test_get_query_from_input_empty():
    """Test query extraction from empty input"""
    component = BrightDataSearchEngineComponent()
    component.query_input = ""
    
    query = component.get_query_from_input()
    assert query == ""


def test_get_query_from_input_none():
    """Test query extraction from None input"""
    component = BrightDataSearchEngineComponent()
    component.query_input = None
    
    query = component.get_query_from_input()
    assert query == ""


def test_build_search_url_google():
    """Test Google search URL building"""
    component = BrightDataSearchEngineComponent()
    
    url = component._build_search_url("google", "artificial intelligence")
    
    assert url == "https://www.google.com/search?q=artificial%20intelligence"


def test_build_search_url_bing():
    """Test Bing search URL building"""
    component = BrightDataSearchEngineComponent()
    
    url = component._build_search_url("bing", "machine learning")
    
    assert url == "https://www.bing.com/search?q=machine%20learning"


def test_build_search_url_yandex():
    """Test Yandex search URL building"""
    component = BrightDataSearchEngineComponent()
    
    url = component._build_search_url("yandex", "deep learning")
    
    assert url == "https://yandex.com/search/?text=deep%20learning"


def test_build_search_url_special_characters():
    """Test search URL building with special characters"""
    component = BrightDataSearchEngineComponent()
    
    url = component._build_search_url("google", "AI & ML research")
    
    assert url == "https://www.google.com/search?q=AI%20%26%20ML%20research"


def test_build_search_url_unicode():
    """Test search URL building with Unicode characters"""
    component = BrightDataSearchEngineComponent()
    
    url = component._build_search_url("google", "机器学习")
    
    assert url == "https://www.google.com/search?q=%E6%9C%BA%E5%99%A8%E5%AD%A6%E4%B9%A0"


@patch('langflow.components.brightdata.brightdata_search_engine.requests.post')
def test_search_web_success(mock_post):
    """Test successful search with mocked requests"""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "Search results content"
    mock_post.return_value = mock_response
    
    component = BrightDataSearchEngineComponent()
    component.api_token = "test_token"
    component.query_input = "artificial intelligence"
    component.engine = "google"
    
    result = component.search_web()
    
    assert isinstance(result, Data)
    assert result.text == "Search results content"
    assert result.data["status"] == "success"
    assert result.data["query"] == "artificial intelligence"
    assert result.data["engine"] == "google"
    assert "search_url" in result.data
    
    # Verify the API call was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "google.com" in call_args[1]['json']['url']


@patch('langflow.components.brightdata.brightdata_search_engine.requests.post')
def test_search_web_http_error(mock_post):
    """Test handling of HTTP errors"""
    # Mock error response
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_post.return_value = mock_response
    
    component = BrightDataSearchEngineComponent()
    component.api_token = "invalid_token"
    component.query_input = "test query"
    component.engine = "google"
    
    result = component.search_web()
    
    assert isinstance(result, Data)
    assert "Error searching: HTTP 401" in result.text
    assert result.data["status"] == "error"
    assert result.data["query"] == "test query"


def test_search_web_empty_query():
    """Test handling of empty search query"""
    component = BrightDataSearchEngineComponent()
    component.api_token = "test_token"
    component.query_input = ""
    component.engine = "google"
    
    result = component.search_web()
    
    assert isinstance(result, Data)
    assert result.text == "Search query is required"
    assert result.data["status"] == "error"


@patch('langflow.components.brightdata.brightdata_search_engine.requests.post')
def test_search_web_different_engines(mock_post):
    """Test search with different engines"""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "Search results"
    mock_post.return_value = mock_response
    
    component = BrightDataSearchEngineComponent()
    component.api_token = "test_token"
    component.query_input = "test query"
    
    engines = ["google", "bing", "yandex"]
    expected_domains = ["google.com", "bing.com", "yandex.com"]
    
    for engine, expected_domain in zip(engines, expected_domains):
        component.engine = engine
        result = component.search_web()
        
        assert isinstance(result, Data)
        assert result.data["engine"] == engine
        
        # Check that the correct search URL was built
        call_args = mock_post.call_args
        search_url = call_args[1]['json']['url']
        assert expected_domain in search_url


def test_build_search_url_defaults_to_google():
    """Test that unknown engine defaults to Google"""
    component = BrightDataSearchEngineComponent()
    
    url = component._build_search_url("unknown_engine", "test query")
    
    assert url == "https://www.google.com/search?q=test%20query"


@patch('langflow.components.brightdata.brightdata_search_engine.requests.post')
def test_search_web_payload_structure(mock_post):
    """Test that the API payload has the correct structure"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "Search results"
    mock_post.return_value = mock_response
    
    component = BrightDataSearchEngineComponent()
    component.api_token = "test_token"
    component.query_input = "artificial intelligence"
    component.engine = "google"
    
    result = component.search_web()
    
    # Verify the payload structure
    call_args = mock_post.call_args
    payload = call_args[1]['json']
    
    assert 'url' in payload
    assert 'zone' in payload
    assert 'format' in payload
    assert 'data_format' in payload
    
    assert payload['zone'] == 'mcp_unlocker'
    assert payload['format'] == 'raw'
    assert payload['data_format'] == 'markdown'
    
    # Verify headers
    headers = call_args[1]['headers']
    assert 'authorization' in headers
    assert headers['authorization'] == 'Bearer test_token'
    assert headers['Content-Type'] == 'application/json'


@patch('langflow.components.brightdata.brightdata_search_engine.requests.post')
def test_search_web_timeout_setting(mock_post):
    """Test that timeout is set correctly in the request"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "Search results"
    mock_post.return_value = mock_response
    
    component = BrightDataSearchEngineComponent()
    component.api_token = "test_token"
    component.query_input = "test query"
    component.engine = "google"
    
    result = component.search_web()
    
    # Verify timeout was set
    call_args = mock_post.call_args
    assert call_args[1]['timeout'] == 120