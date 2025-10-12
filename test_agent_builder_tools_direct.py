#!/usr/bin/env python3
"""Direct test script to validate Agent Builder component tool mode functionality"""

import sys
import traceback
import importlib.util
from pathlib import Path

def test_component_syntax_and_structure():
    """Test that all Agent Builder components have correct syntax and tool structure"""

    results = {}

    # Component files to test
    base_path = Path("/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/components/agents/builder")

    components_to_test = [
        ("intent_analyzer.py", "IntentAnalyzerComponent"),
        ("requirements_gatherer.py", "RequirementsGathererComponent"),
        ("specification_search.py", "SpecificationSearchComponent"),
        ("component_recommender.py", "ComponentRecommenderComponent"),
        ("mcp_tool_discovery.py", "MCPToolDiscoveryComponent"),
        ("specification_builder.py", "SpecificationBuilderComponent"),
        ("specification_validator.py", "SpecificationValidatorComponent"),
        ("flow_visualizer.py", "FlowVisualizerComponent"),
        ("test_executor.py", "TestExecutorComponent"),
        ("deployment_guidance.py", "DeploymentGuidanceComponent"),
    ]

    print("🔧 Testing Agent Builder Component Tool Mode Structure")
    print("=" * 60)

    for file_name, component_name in components_to_test:
        try:
            file_path = base_path / file_name

            if not file_path.exists():
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": f"File not found: {file_path}"
                }
                continue

            # Read file content
            with open(file_path, 'r') as f:
                content = f.read()

            # Check for required imports
            required_imports = [
                "from langchain.tools import StructuredTool",
                "from pydantic import BaseModel, Field",
                "from langflow.base.langchain_utilities.model import LCToolComponent"
            ]

            missing_imports = []
            for import_stmt in required_imports:
                if import_stmt not in content:
                    missing_imports.append(import_stmt)

            if missing_imports:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": f"Missing imports: {missing_imports}"
                }
                continue

            # Check for class inheritance
            if f"class {component_name}(LCToolComponent):" not in content:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Class does not inherit from LCToolComponent"
                }
                continue

            # Check for required outputs
            if 'Output(name="api_run_model"' not in content or 'Output(name="api_build_tool"' not in content:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing required api_run_model or api_build_tool outputs"
                }
                continue

            # Check for build_tool method
            if "def build_tool(self) -> Tool:" not in content:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing build_tool method with proper signature"
                }
                continue

            # Check for run_model method
            if "def run_model(self) -> List[Data]:" not in content:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing run_model method with proper signature"
                }
                continue

            # Check for Pydantic schema (flexible pattern matching)
            has_schema = False
            schema_patterns = [
                "(BaseModel):",  # Any schema class
                "Schema(BaseModel):"  # Specific schema pattern
            ]

            for pattern in schema_patterns:
                if pattern in content:
                    has_schema = True
                    break

            if not has_schema:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing Pydantic schema class (BaseModel)"
                }
                continue

            # Check for StructuredTool.from_function
            if "StructuredTool.from_function" not in content:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": "Missing StructuredTool.from_function call"
                }
                continue

            # Try to compile the file
            try:
                compile(content, file_path, 'exec')
                syntax_valid = True
            except SyntaxError as e:
                syntax_valid = False
                syntax_error = str(e)

            if not syntax_valid:
                results[component_name] = {
                    "status": "❌ FAILED",
                    "error": f"Syntax error: {syntax_error}"
                }
                continue

            results[component_name] = {
                "status": "✅ PASSED",
                "has_all_required_elements": True,
                "syntax_valid": True
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
            print(f"   ✓ All required elements present")
            print(f"   ✓ Syntax validation passed")
        else:
            failed += 1
            print(f"   Error: {result['error']}")

    print(f"\n📊 SUMMARY:")
    print(f"   • Total components tested: {len(components_to_test)}")
    print(f"   • Passed: {passed}")
    print(f"   • Failed: {failed}")

    if failed == 0:
        print(f"\n🎉 ALL STRUCTURAL TESTS PASSED!")
        print(f"All Agent Builder components have the correct tool mode structure:")
        print(f"✓ Proper imports (LangChain, Pydantic, LCToolComponent)")
        print(f"✓ LCToolComponent inheritance")
        print(f"✓ Standard outputs (api_run_model, api_build_tool)")
        print(f"✓ build_tool() method with proper signature")
        print(f"✓ run_model() method with proper signature")
        print(f"✓ Pydantic schema classes")
        print(f"✓ StructuredTool.from_function usage")
        print(f"✓ Valid Python syntax")
        return True
    else:
        print(f"\n⚠️  {failed} components failed structural validation.")
        return False

if __name__ == "__main__":
    test_component_syntax_and_structure()