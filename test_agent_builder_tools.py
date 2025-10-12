#!/usr/bin/env python3
"""Test script to validate Agent Builder component tool mode functionality"""

import sys
import traceback
from pathlib import Path

# Add the langflow path to sys.path
sys.path.insert(0, "/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base")

def test_component_tool_creation():
    """Test that all Agent Builder components can create valid StructuredTool objects"""

    results = {}

    # Component classes to test
    components_to_test = [
        ("IntentAnalyzerComponent", "langflow.components.agents.builder.intent_analyzer"),
        ("RequirementsGathererComponent", "langflow.components.agents.builder.requirements_gatherer"),
        ("SpecificationSearchComponent", "langflow.components.agents.builder.specification_search"),
        ("ComponentRecommenderComponent", "langflow.components.agents.builder.component_recommender"),
        ("MCPToolDiscoveryComponent", "langflow.components.agents.builder.mcp_tool_discovery"),
        ("SpecificationBuilderComponent", "langflow.components.agents.builder.specification_builder"),
        ("SpecificationValidatorComponent", "langflow.components.agents.builder.specification_validator"),
        ("FlowVisualizerComponent", "langflow.components.agents.builder.flow_visualizer"),
        ("TestExecutorComponent", "langflow.components.agents.builder.test_executor"),
        ("DeploymentGuidanceComponent", "langflow.components.agents.builder.deployment_guidance"),
    ]

    print("🔧 Testing Agent Builder Component Tool Mode Functionality")
    print("=" * 60)

    for component_name, module_path in components_to_test:
        try:
            # Import the component
            module = __import__(module_path, fromlist=[component_name])
            ComponentClass = getattr(module, component_name)

            # Create component instance
            component = ComponentClass()

            # Test build_tool method exists
            if not hasattr(component, 'build_tool'):
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing build_tool method"
                }
                continue

            # Test tool creation
            tool = component.build_tool()

            # Validate tool properties
            if not hasattr(tool, 'name'):
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Tool missing name attribute"
                }
                continue

            if not hasattr(tool, 'description'):
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Tool missing description attribute"
                }
                continue

            if not hasattr(tool, 'func'):
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Tool missing func attribute"
                }
                continue

            # Test run_model method exists
            if not hasattr(component, 'run_model'):
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing run_model method"
                }
                continue

            results[component_name] = {
                "status": "✅ PASSED",
                "tool_name": tool.name,
                "description": tool.description[:80] + "..." if len(tool.description) > 80 else tool.description,
                "has_schema": hasattr(tool, 'args_schema') and tool.args_schema is not None
            }

        except Exception as e:
            results[component_name] = {
                "status": "❌ FAILED",
                "error": f"Exception: {str(e)}"
            }
            print(f"Error with {component_name}: {traceback.format_exc()}")

    # Print results
    passed = 0
    failed = 0

    for component_name, result in results.items():
        print(f"\n{result['status']} {component_name}")

        if result['status'] == "✅ PASSED":
            passed += 1
            print(f"   Tool Name: {result['tool_name']}")
            print(f"   Description: {result['description']}")
            print(f"   Has Schema: {result['has_schema']}")
        else:
            failed += 1
            print(f"   Error: {result['error']}")

    print(f"\n📊 SUMMARY:")
    print(f"   • Total components tested: {len(components_to_test)}")
    print(f"   • Passed: {passed}")
    print(f"   • Failed: {failed}")

    if failed == 0:
        print(f"\n🎉 ALL TESTS PASSED! Agent Builder components are ready for tool mode!")
        return True
    else:
        print(f"\n⚠️  {failed} components failed. Need to fix issues before tool mode is ready.")
        return False

if __name__ == "__main__":
    test_component_tool_creation()