"""
Test file to verify that all Bright Data components can be imported correctly.
This ensures the __init__.py file is properly configured.
"""

import pytest


def test_brightdata_components_import():
    """Test that all Bright Data components can be imported from the brightdata module"""
    try:
        from langflow.components.brightdata import (
            BrightDataSearchEngineComponent,
            BrightDataStructuredDataEnhancedComponent,
            BrightDataWebScraperComponent,
        )
        
        # Verify all components are classes
        assert isinstance(BrightDataSearchEngineComponent, type)
        assert isinstance(BrightDataStructuredDataEnhancedComponent, type)
        assert isinstance(BrightDataWebScraperComponent, type)
        
        # Verify display names are set correctly
        assert hasattr(BrightDataSearchEngineComponent, 'display_name')
        assert hasattr(BrightDataStructuredDataEnhancedComponent, 'display_name')
        assert hasattr(BrightDataWebScraperComponent, 'display_name')
        
        # Verify icons are set
        assert hasattr(BrightDataSearchEngineComponent, 'icon')
        assert hasattr(BrightDataStructuredDataEnhancedComponent, 'icon')
        assert hasattr(BrightDataWebScraperComponent, 'icon')
        
        assert BrightDataSearchEngineComponent.icon == "BrightData"
        assert BrightDataStructuredDataEnhancedComponent.icon == "BrightData"
        assert BrightDataWebScraperComponent.icon == "BrightData"
        
    except ImportError as e:
        pytest.fail(f"Failed to import Bright Data components: {e}")


def test_brightdata_components_directory_structure():
    """Test that Bright Data components directory structure is correct"""
    import os
    
    # Check that the brightdata directory exists
    brightdata_dir = "src/backend/base/langflow/components/brightdata"
    assert os.path.exists(brightdata_dir), f"Bright Data components directory {brightdata_dir} does not exist"
    
    # Check that component files exist
    expected_files = [
        "__init__.py",
        "brightdata_search_engine.py", 
        "brightdata_structured_data.py",
        "brightdata_web_scraper.py"
    ]
    
    for file_name in expected_files:
        file_path = os.path.join(brightdata_dir, file_name)
        assert os.path.exists(file_path), f"Expected file {file_path} does not exist"


def test_brightdata_component_names():
    """Test that component names are correctly set"""
    from langflow.components.brightdata import (
        BrightDataSearchEngineComponent,
        BrightDataStructuredDataEnhancedComponent,
        BrightDataWebScraperComponent,
    )
    
    assert BrightDataSearchEngineComponent.name == "BrightDataSearchEngine"
    assert BrightDataStructuredDataEnhancedComponent.name == "BrightDataStructuredData"
    assert BrightDataWebScraperComponent.name == "BrightDataWebScraper"


def test_brightdata_component_descriptions():
    """Test that components have appropriate descriptions"""
    from langflow.components.brightdata import (
        BrightDataSearchEngineComponent,
        BrightDataStructuredDataEnhancedComponent,
        BrightDataWebScraperComponent,
    )
    
    # Verify descriptions exist and are meaningful
    assert len(BrightDataSearchEngineComponent.description) > 10
    assert len(BrightDataStructuredDataEnhancedComponent.description) > 10
    assert len(BrightDataWebScraperComponent.description) > 10
    
    # Verify they contain relevant keywords
    assert "search" in BrightDataSearchEngineComponent.description.lower()
    assert "structured" in BrightDataStructuredDataEnhancedComponent.description.lower()
    assert "scrap" in BrightDataWebScraperComponent.description.lower()


def test_brightdata_component_inputs():
    """Test that components have required inputs defined"""
    from langflow.components.brightdata import (
        BrightDataSearchEngineComponent,
        BrightDataStructuredDataEnhancedComponent,
        BrightDataWebScraperComponent,
    )
    
    # All components should have api_token input
    for component_class in [
        BrightDataSearchEngineComponent,
        BrightDataStructuredDataEnhancedComponent,
        BrightDataWebScraperComponent,
    ]:
        assert hasattr(component_class, 'inputs')
        assert len(component_class.inputs) > 0
        
        # Check if api_token input exists
        api_token_input = next((inp for inp in component_class.inputs if inp.name == "api_token"), None)
        assert api_token_input is not None, f"api_token input not found in {component_class.__name__}"


def test_brightdata_component_outputs():
    """Test that components have outputs defined"""
    from langflow.components.brightdata import (
        BrightDataSearchEngineComponent,
        BrightDataStructuredDataEnhancedComponent,
        BrightDataWebScraperComponent,
    )
    
    # All components should have outputs
    for component_class in [
        BrightDataSearchEngineComponent,
        BrightDataStructuredDataEnhancedComponent,
        BrightDataWebScraperComponent,
    ]:
        assert hasattr(component_class, 'outputs')
        assert len(component_class.outputs) > 0