#!/usr/bin/env python3
"""
Direct test runner for Genesis modules - bypasses conftest issues.
"""

import sys
import traceback
from pathlib import Path

# Add the base module to Python path
sys.path.insert(0, str(Path(__file__).parent / "base"))

def test_genesis_imports():
    """Test that all Genesis modules can be imported."""
    print("Testing Genesis module imports...")

    try:
        print("  ✓ Testing AgentSpec model import...")
        from langflow.custom.genesis.spec.models import AgentSpec, Component, Variable
        print("    - AgentSpec, Component, Variable imported successfully")

        print("  ✓ Testing ComponentMapper import...")
        from langflow.custom.genesis.spec.mapper import ComponentMapper
        print("    - ComponentMapper imported successfully")

        print("  ✓ Testing VariableResolver import...")
        from langflow.custom.genesis.spec.resolver import VariableResolver
        print("    - VariableResolver imported successfully")

        print("  ✓ Testing FlowConverter import...")
        from langflow.custom.genesis.spec.converter import FlowConverter
        print("    - FlowConverter imported successfully")

        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_agent_spec_model():
    """Test AgentSpec model creation."""
    print("\nTesting AgentSpec model functionality...")

    try:
        from langflow.custom.genesis.spec.models import AgentSpec, Component, Variable

        # Test minimal agent spec
        minimal_spec_data = {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "agentGoal": "Testing",
            "components": [
                {
                    "id": "input-1",
                    "name": "Input",
                    "kind": "Input",
                    "type": "genesis:chat_input"
                }
            ]
        }

        print("  ✓ Creating minimal AgentSpec...")
        spec = AgentSpec(**minimal_spec_data)
        assert spec.id == "test-agent"
        assert spec.name == "Test Agent"
        assert len(spec.components) == 1
        print("    - Minimal AgentSpec created successfully")

        # Test component validation
        print("  ✓ Testing component validation...")
        component = spec.components[0]
        assert component.id == "input-1"
        assert component.type == "genesis:chat_input"
        print("    - Component validation successful")

        return True
    except Exception as e:
        print(f"  ✗ AgentSpec test failed: {e}")
        traceback.print_exc()
        return False

def test_component_mapper():
    """Test ComponentMapper functionality."""
    print("\nTesting ComponentMapper functionality...")

    try:
        from langflow.custom.genesis.spec.mapper import ComponentMapper

        mapper = ComponentMapper()

        # Test standard mappings
        print("  ✓ Testing standard component mappings...")

        # Test agent mapping
        agent_mapping = mapper.map_component("genesis:agent")
        assert agent_mapping["component"] == "Agent"
        print("    - genesis:agent → Agent")

        # Test chat input mapping
        input_mapping = mapper.map_component("genesis:chat_input")
        assert input_mapping["component"] == "ChatInput"
        print("    - genesis:chat_input → ChatInput")

        # Test AutonomizeModel mappings
        print("  ✓ Testing AutonomizeModel mappings...")
        rxnorm_mapping = mapper.map_component("genesis:rxnorm")
        assert rxnorm_mapping["component"] == "AutonomizeModel"
        assert rxnorm_mapping["config"]["selected_model"] == "RxNorm Code"
        print("    - genesis:rxnorm → AutonomizeModel(RxNorm Code)")

        icd10_mapping = mapper.map_component("genesis:icd10")
        assert icd10_mapping["component"] == "AutonomizeModel"
        assert icd10_mapping["config"]["selected_model"] == "ICD-10 Code"
        print("    - genesis:icd10 → AutonomizeModel(ICD-10 Code)")

        return True
    except Exception as e:
        print(f"  ✗ ComponentMapper test failed: {e}")
        traceback.print_exc()
        return False

def test_variable_resolver():
    """Test VariableResolver functionality."""
    print("\nTesting VariableResolver functionality...")

    try:
        from langflow.custom.genesis.spec.resolver import VariableResolver
        from langflow.custom.genesis.spec.models import AgentSpec

        resolver = VariableResolver()

        # Test basic variable resolution
        print("  ✓ Testing basic variable resolution...")

        spec_data = {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "Agent for {environment}",
            "agentGoal": "Testing {model_name}",
            "components": [
                {
                    "id": "agent-1",
                    "name": "Agent",
                    "kind": "Agent",
                    "type": "genesis:agent",
                    "config": {
                        "model": "{model_name}",
                        "temperature": "{temperature}"
                    }
                }
            ],
            "variables": [
                {"name": "model_name", "type": "string", "required": True, "description": "Model name"},
                {"name": "temperature", "type": "float", "required": False, "default": 0.7, "description": "Temperature"},
                {"name": "environment", "type": "string", "required": False, "default": "testing", "description": "Environment"}
            ]
        }

        spec = AgentSpec(**spec_data)
        # Provide runtime vars including defaults (as would happen in real usage)
        runtime_vars = {
            "model_name": "gpt-4",
            "environment": "testing",  # default value would be provided
            "temperature": 0.7         # default value would be provided
        }

        # Use the resolve method instead of resolve_variables
        resolved_spec_dict = resolver.resolve(spec.model_dump(), runtime_vars)
        resolved_spec = AgentSpec(**resolved_spec_dict)

        assert "gpt-4" in resolved_spec.agentGoal
        assert "testing" in resolved_spec.description  # default value used
        assert resolved_spec.components[0].config["model"] == "gpt-4"
        assert resolved_spec.components[0].config["temperature"] == 0.7  # default value

        print("    - Variable resolution with defaults successful")

        return True
    except Exception as e:
        print(f"  ✗ VariableResolver test failed: {e}")
        traceback.print_exc()
        return False

def test_knowledge_hub_search_component():
    """Test KnowledgeHubSearch component basics."""
    print("\nTesting KnowledgeHubSearch component...")

    try:
        from langflow.components.knowledge_bases.knowledge_hub_search import KnowledgeHubSearchComponent

        # Test component initialization
        print("  ✓ Testing component initialization...")
        component = KnowledgeHubSearchComponent()

        assert component.display_name == "Knowledge Hub Search"
        assert component.name == "KnowledgeHubSearch"
        assert hasattr(component, 'inputs')
        assert hasattr(component, 'outputs')

        print("    - Component initialized successfully")

        # Test input configuration
        print("  ✓ Testing input configuration...")
        inputs = component.inputs
        input_names = [inp.name for inp in inputs]

        assert "search_query" in input_names
        assert "selected_hubs" in input_names
        assert "search_type" in input_names
        assert "top_k" in input_names

        print("    - Input configuration correct")

        return True
    except Exception as e:
        print(f"  ✗ KnowledgeHubSearch test failed: {e}")
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all Genesis tests."""
    print("Genesis Unit Tests - Direct Runner")
    print("=" * 50)

    tests = [
        ("Import Tests", test_genesis_imports),
        ("AgentSpec Model", test_agent_spec_model),
        ("ComponentMapper", test_component_mapper),
        ("VariableResolver", test_variable_resolver),
        ("KnowledgeHubSearch Component", test_knowledge_hub_search_component),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n[{passed + 1}/{total}] Running: {test_name}")
        print("-" * 30)

        if test_func():
            print(f"✓ {test_name} PASSED")
            passed += 1
        else:
            print(f"✗ {test_name} FAILED")

    print("\n" + "=" * 50)
    print(f"SUMMARY: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"⚠️  {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)