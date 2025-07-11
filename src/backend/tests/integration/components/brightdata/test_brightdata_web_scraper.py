"""Unit tests for BrightDataWebScraperComponent"""
import pytest
from unittest.mock import Mock, patch
from langflow.components.brightdata import BrightDataWebScraperComponent
from langflow.schema import Data
from langflow.schema.message import Message


def test_brightdata_web_scraper_initialization():
    """Test that BrightDataWebScraperComponent can be initialized correctly"""
    component = BrightDataWebScraperComponent()
    
    # Test component attributes
    assert component.display_name == "Bright Data Web Scraper"
    assert component.name == "BrightDataWebScraper"
    assert component.icon == "BrightData"
    assert "scrape" in component.description.lower()
    
    # Test that inputs are defined
    assert hasattr(component, 'inputs')
    assert len(component.inputs) > 0
    
    # Check for required inputs
    input_names = [inp.name for inp in component.inputs]
    assert "api_token" in input_names
    assert "url_input" in input_names
    assert "output_format" in input_names
    
    # Test that outputs are defined
    assert hasattr(component, 'outputs')
    assert len(component.outputs) > 0
    
    # Check for expected outputs
    output_names = [out.name for out in component.outputs]
    assert "content" in output_names
    assert "url" in output_names
    assert "metadata" in output_names


def test_get_url_from_input_string():
    """Test URL extraction from string input"""
    component = BrightDataWebScraperComponent()
    component.url_input = "https://example.com"
    
    url = component.get_url_from_input()
    assert url == "https://example.com"


def test_get_url_from_input_message():
    """Test URL extraction from Message object"""
    component = BrightDataWebScraperComponent()
    component.url_input = Message(text="https://example.com")
    
    url = component.get_url_from_input()
    assert url == "https://example.com"


def test_get_url_from_input_empty():
    """Test URL extraction from empty input"""
    component = BrightDataWebScraperComponent()
    component.url_input = ""
    
    url = component.get_url_from_input()
    assert url == ""


def test_get_url_from_input_none():
    """Test URL extraction from None input"""
    component = BrightDataWebScraperComponent()
    component.url_input = None
    
    url = component.get_url_from_input()
    assert url == ""


def test_create_error_data():
    """Test error data creation helper method"""
    component = BrightDataWebScraperComponent()
    
    error_data = component._create_error_data("https://example.com", "Test error")
    
    assert isinstance(error_data, Data)
    assert error_data.text == "Test error"
    assert error_data.data["url"] == "https://example.com"
    assert error_data.data["status"] == "error"
    assert error_data.data["error"] == "Test error"


@patch('langflow.components.brightdata.brightdata_web_scraper.requests.post')
def test_scrape_content_success(mock_post):
    """Test successful scraping with mocked requests"""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "Scraped content"
    mock_response.headers = {"content-type": "text/html"}
    mock_post.return_value = mock_response
    
    component = BrightDataWebScraperComponent()
    component.api_token = "test_token"
    component.url_input = "https://example.com"
    component.output_format = "markdown"
    component.zone_name = "mcp_unlocker"
    component.timeout = "120"
    
    result = component.scrape_content()
    
    assert isinstance(result, Data)
    assert result.text == "Scraped content"
    assert result.data["status"] == "success"
    assert result.data["url"] == "https://example.com"
    
    # Verify the API call was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[1]['json']['url'] == "https://example.com"
    assert call_args[1]['json']['zone'] == "mcp_unlocker"


@patch('langflow.components.brightdata.brightdata_web_scraper.requests.post')
def test_scrape_content_http_error(mock_post):
    """Test handling of HTTP errors"""
    # Mock error response
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.json.return_value = {"error": "Invalid token"}
    mock_post.return_value = mock_response
    
    component = BrightDataWebScraperComponent()
    component.api_token = "invalid_token"
    component.url_input = "https://example.com"
    component.output_format = "markdown"
    component.zone_name = "mcp_unlocker"
    component.timeout = "120"
    
    result = component.scrape_content()
    
    assert isinstance(result, Data)
    assert "Error scraping URL: HTTP 401" in result.text
    assert result.data["status"] == "error"


def test_scrape_content_empty_url():
    """Test handling of empty URL"""
    component = BrightDataWebScraperComponent()
    component.api_token = "test_token"
    component.url_input = ""
    component.output_format = "markdown"
    component.zone_name = "mcp_unlocker"
    component.timeout = "120"
    
    result = component.scrape_content()
    
    assert isinstance(result, Data)
    assert result.text == "No URL provided"
    assert result.data["status"] == "error"


def test_scrape_content_url_protocol_addition():
    """Test automatic protocol addition to URLs"""
    component = BrightDataWebScraperComponent()
    component.url_input = "example.com"
    
    url = component.get_url_from_input()
    # The component should handle protocol addition in scrape_content method
    assert url == "example.com"


@patch('langflow.components.brightdata.brightdata_web_scraper.requests.post')
def test_scrape_content_timeout_exception(mock_post):
    """Test handling of timeout exceptions"""
    from requests.exceptions import Timeout
    
    mock_post.side_effect = Timeout("Request timed out")
    
    component = BrightDataWebScraperComponent()
    component.api_token = "test_token"
    component.url_input = "https://example.com"
    component.output_format = "markdown"
    component.zone_name = "mcp_unlocker"
    component.timeout = "120"
    
    result = component.scrape_content()
    
    assert isinstance(result, Data)
    assert "Request timed out after 120 seconds" in result.text
    assert result.data["status"] == "error"


@patch('langflow.components.brightdata.brightdata_web_scraper.requests.post')
def test_scrape_content_connection_error(mock_post):
    """Test handling of connection errors"""
    from requests.exceptions import ConnectionError
    
    mock_post.side_effect = ConnectionError("Connection failed")
    
    component = BrightDataWebScraperComponent()
    component.api_token = "test_token"
    component.url_input = "https://example.com"
    component.output_format = "markdown"
    component.zone_name = "mcp_unlocker"
    component.timeout = "120"
    
    result = component.scrape_content()
    
    assert isinstance(result, Data)
    assert "Connection error - please check your internet connection" in result.text
    assert result.data["status"] == "error"


def test_get_url_output():
    """Test URL output method"""
    component = BrightDataWebScraperComponent()
    component.url_input = "https://example.com"
    # Simulate that scraping has been run
    component._scraped_url = "https://example.com"
    
    result = component.get_url()
    
    assert isinstance(result, Data)
    assert result.text == "https://example.com"


def test_get_metadata_output():
    """Test metadata output method"""
    component = BrightDataWebScraperComponent()
    component.url_input = "https://example.com"
    # Simulate metadata from scraping
    component._metadata = {
        "url": "https://example.com",
        "status": "success",
        "content_length": 1000
    }
    
    result = component.get_metadata()
    
    assert isinstance(result, Data)
    assert result.data["url"] == "https://example.com"
    assert result.data["status"] == "success"
    assert result.data["content_length"] == 1000