"""Integration tests for Bright Data components"""
import pytest
from langflow.components.brightdata import (
    BrightDataSearchEngineComponent,
    BrightDataStructuredDataEnhancedComponent,
    BrightDataWebScraperComponent,
)
from langflow.schema import Data
from langflow.schema.message import Message

from tests.integration.utils import run_single_component


async def test_brightdata_web_scraper_basic_integration():
    """Test basic web scraper integration without requiring real API"""
    outputs = await run_single_component(
        BrightDataWebScraperComponent,
        inputs={
            "api_token": "test_api_key",
            "url_input": "https://example.com",
            "output_format": "markdown",
            "zone_name": "mcp_unlocker",
            "timeout": "120",
        },
    )
    
    # Verify that we get the expected output structure
    assert "content" in outputs
    assert isinstance(outputs["content"], Data)
    
    assert "url" in outputs
    assert isinstance(outputs["url"], Data)
    
    assert "metadata" in outputs
    assert isinstance(outputs["metadata"], Data)


async def test_brightdata_web_scraper_message_input():
    """Test web scraper with Message object as input"""
    message_input = Message(text="https://example.com")
    
    outputs = await run_single_component(
        BrightDataWebScraperComponent,
        inputs={
            "api_token": "test_api_key",
            "url_input": message_input,
            "output_format": "html",
            "zone_name": "mcp_unlocker",
            "timeout": "60",
        },
    )
    
    assert "content" in outputs
    assert isinstance(outputs["content"], Data)
    assert "url" in outputs
    assert isinstance(outputs["url"], Data)


async def test_brightdata_web_scraper_empty_url():
    """Test web scraper error handling with empty URL"""
    outputs = await run_single_component(
        BrightDataWebScraperComponent,
        inputs={
            "api_token": "test_api_key",
            "url_input": "",
            "output_format": "markdown",
            "zone_name": "mcp_unlocker",
            "timeout": "120",
        },
    )
    
    # Should handle empty URL gracefully
    assert "content" in outputs
    assert isinstance(outputs["content"], Data)
    # Error should be in the data or text
    content_data = outputs["content"]
    assert ("No URL provided" in content_data.text or 
            (content_data.data and "error" in str(content_data.data).lower()))


async def test_brightdata_search_engine_basic_integration():
    """Test basic search engine integration without requiring real API"""
    outputs = await run_single_component(
        BrightDataSearchEngineComponent,
        inputs={
            "api_token": "test_api_key",
            "query_input": "artificial intelligence",
            "engine": "google",
        },
    )
    
    # Verify that we get the expected output structure
    assert "results" in outputs
    assert isinstance(outputs["results"], Data)


async def test_brightdata_search_engine_message_input():
    """Test search engine with Message object as input"""
    message_input = Message(text="machine learning")
    
    outputs = await run_single_component(
        BrightDataSearchEngineComponent,
        inputs={
            "api_token": "test_api_key",
            "query_input": message_input,
            "engine": "bing",
        },
    )
    
    assert "results" in outputs
    assert isinstance(outputs["results"], Data)


async def test_brightdata_search_engine_empty_query():
    """Test search engine error handling with empty query"""
    outputs = await run_single_component(
        BrightDataSearchEngineComponent,
        inputs={
            "api_token": "test_api_key",
            "query_input": "",
            "engine": "google",
        },
    )
    
    # Should handle empty query gracefully
    assert "results" in outputs
    assert isinstance(outputs["results"], Data)
    # Error should be in the data
    results_data = outputs["results"]
    assert ("Search query is required" in results_data.text or
            (results_data.data and "error" in str(results_data.data).lower()))


async def test_brightdata_search_engine_different_engines():
    """Test search engine with different engines"""
    engines = ["google", "bing", "yandex"]
    
    for engine in engines:
        outputs = await run_single_component(
            BrightDataSearchEngineComponent,
            inputs={
                "api_token": "test_api_key",
                "query_input": "test query",
                "engine": engine,
            },
        )
        
        assert "results" in outputs
        assert isinstance(outputs["results"], Data)
        # Verify engine is set correctly in data if available
        if outputs["results"].data:
            assert outputs["results"].data.get("engine") == engine


async def test_all_components_have_required_attributes():
    """Test that all components have the required attributes"""
    components = [
        BrightDataWebScraperComponent,
        BrightDataSearchEngineComponent, 
        BrightDataStructuredDataEnhancedComponent,
    ]
    
    for component_class in components:
        # Test that components can be instantiated
        component = component_class()
        
        # Check required attributes
        assert hasattr(component, 'display_name')
        assert hasattr(component, 'name')
        assert hasattr(component, 'icon')
        assert hasattr(component, 'description')
        assert hasattr(component, 'inputs')
        assert hasattr(component, 'outputs')
        
        # Check that icon is set to BrightData
        assert component.icon == "BrightData"
        
        # Check that inputs and outputs are lists
        assert isinstance(component.inputs, list)
        assert isinstance(component.outputs, list)
        assert len(component.inputs) > 0
        assert len(component.outputs) > 0


async def test_component_error_handling():
    """Test error handling across all components"""
    # Test web scraper with missing API token
    outputs = await run_single_component(
        BrightDataWebScraperComponent,
        inputs={
            "api_token": "",
            "url_input": "https://example.com",
            "output_format": "markdown",
            "zone_name": "mcp_unlocker",
            "timeout": "120",
        },
    )
    assert "content" in outputs
    
    # Test search engine with missing API token
    outputs = await run_single_component(
        BrightDataSearchEngineComponent,
        inputs={
            "api_token": "",
            "query_input": "test query",
            "engine": "google",
        },
    )
    assert "results" in outputs