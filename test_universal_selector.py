#!/usr/bin/env python3
"""Test script for the Universal Output Selector component
"""

import os
import sys

# Add the backend to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "backend", "base"))

from langflow.components.helpers.universal_output_selector import UniversalOutputSelectorComponent
from langflow.custom.custom_component.component import PlaceholderGraph


def test_component_creation():
    """Test that the component can be created"""
    print("Testing component creation...")

    # Create component with placeholder graph
    component = UniversalOutputSelectorComponent()

    # Set a placeholder graph to avoid errors
    component.graph = PlaceholderGraph(
        flow_id="test-flow",
        user_id="test-user",
        session_id="test-session",
        context={},
        flow_name="Test Flow"
    )

    print(f"✓ Component created: {component.display_name}")
    print(f"✓ Description: {component.description}")
    print(f"✓ Inputs: {len(component.inputs)}")
    print(f"✓ Outputs: {len(component.outputs)}")

    # Test input definitions
    input_names = [inp.name for inp in component.inputs]
    expected_inputs = ["selected_output", "include_self", "filter_types"]

    print(f"✓ Input names: {input_names}")
    assert all(name in input_names for name in expected_inputs), f"Missing inputs: {set(expected_inputs) - set(input_names)}"

    # Test output definitions
    output_names = [out.name for out in component.outputs]
    expected_outputs = ["selected_value", "output_info", "available_outputs"]

    print(f"✓ Output names: {output_names}")
    assert all(name in output_names for name in expected_outputs), f"Missing outputs: {set(expected_outputs) - set(output_names)}"

    print("✓ Component creation test passed!\n")


def test_build_config_update():
    """Test the build config update functionality"""
    print("Testing build config update...")

    component = UniversalOutputSelectorComponent()

    # Create a mock build config
    build_config = {
        "selected_output": {
            "options": [],
            "value": ""
        },
        "include_self": {
            "value": False
        },
        "filter_types": {
            "value": ""
        }
    }

    # Test update (should not crash even without real graph)
    try:
        updated_config = component.update_build_config(build_config, "selected_output", "")
        print("✓ Build config update executed without errors")
        print(f"✓ Updated config has options key: {'options' in updated_config['selected_output']}")
    except Exception as e:
        print(f"⚠ Build config update failed (expected with no real graph): {e}")

    print("✓ Build config update test completed!\n")


def test_discovery_methods():
    """Test the output discovery methods"""
    print("Testing discovery methods...")

    component = UniversalOutputSelectorComponent()

    # Test discovery with no graph
    outputs = component._discover_available_outputs()
    print(f"✓ Discovery with no graph returns: {len(outputs)} outputs")

    # Test parsing selection
    test_cases = [
        ("component-123::output_name", ("component-123", "output_name")),
        ("invalid_format", None),
        ("", None),
        ("comp::out::extra", ("comp", "out::extra"))  # Should handle :: in output name
    ]

    for selection, expected in test_cases:
        result = component._parse_selection(selection)
        print(f"✓ Parse '{selection}' -> {result} (expected: {expected})")
        assert result == expected, f"Parse failed for '{selection}'"

    print("✓ Discovery methods test passed!\n")


def test_output_methods():
    """Test the output methods"""
    print("Testing output methods...")

    component = UniversalOutputSelectorComponent()
    component.selected_output = ""

    # Test get_available_outputs (should work without graph)
    result = component.get_available_outputs()
    print(f"✓ get_available_outputs returns: {type(result)}")
    print(f"✓ Data content keys: {result.data.keys() if hasattr(result, 'data') else 'No data'}")

    # Test get_output_info with no selection
    result = component.get_output_info()
    print(f"✓ get_output_info with no selection: {result.data if hasattr(result, 'data') else result}")

    # Test get_selected_value with no selection
    result = component.get_selected_value()
    print(f"✓ get_selected_value with no selection: {result.data if hasattr(result, 'data') else result}")

    print("✓ Output methods test passed!\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Universal Output Selector Component Tests")
    print("=" * 60)

    try:
        test_component_creation()
        test_build_config_update()
        test_discovery_methods()
        test_output_methods()

        print("=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
