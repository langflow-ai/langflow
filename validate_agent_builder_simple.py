#!/usr/bin/env python3
"""Simple validation of the Agent Builder specification"""

import yaml
import sys

def validate_spec_structure(spec_dict):
    """Validate basic specification structure"""
    errors = []
    warnings = []

    # Required fields
    required_fields = ["name", "description", "agentGoal", "components"]
    for field in required_fields:
        if field not in spec_dict:
            errors.append(f"Missing required field: {field}")

    # Validate components structure
    if "components" in spec_dict:
        components = spec_dict["components"]
        if isinstance(components, list):
            if not components:
                errors.append("At least one component is required")
            else:
                for i, comp in enumerate(components):
                    if not isinstance(comp, dict):
                        errors.append(f"Component {i} must be an object")
                        continue

                    # Required component fields
                    comp_required = ["id", "type"]
                    for field in comp_required:
                        if field not in comp:
                            errors.append(f"Component {i} missing required field: {field}")
        else:
            errors.append("Components must be a list")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

def validate_agent_builder_spec():
    """Validate the Agent Builder specification"""

    spec_path = '/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/agents/ai-studio/agent-builder.yaml'

    try:
        with open(spec_path, 'r') as f:
            spec_yaml = f.read()

        print("🔍 Validating Agent Builder specification...")
        print(f"📁 File: {spec_path}")
        print()

        # Parse YAML
        try:
            spec_dict = yaml.safe_load(spec_yaml)
            if not spec_dict:
                print("❌ Empty or invalid YAML specification")
                return False
        except yaml.YAMLError as e:
            print(f"❌ Invalid YAML format: {e}")
            return False

        # Validate structure
        validation = validate_spec_structure(spec_dict)

        # Additional validation checks
        components = spec_dict.get("components", [])

        # Check for specific Agent Builder components
        expected_tools = [
            "genesis:agent_builder:intent_analyzer",
            "genesis:agent_builder:requirements_gatherer",
            "genesis:agent_builder:specification_search",
            "genesis:agent_builder:component_recommender",
            "genesis:agent_builder:mcp_tool_discovery",
            "genesis:agent_builder:specification_builder",
            "genesis:agent_builder:specification_validator",
            "genesis:agent_builder:flow_visualizer",
            "genesis:agent_builder:test_executor",
            "genesis:agent_builder:deployment_guidance"
        ]

        found_tools = []
        for comp in components:
            comp_type = comp.get("type", "")
            if comp_type in expected_tools:
                found_tools.append(comp_type)

        missing_tools = set(expected_tools) - set(found_tools)
        if missing_tools:
            for tool in missing_tools:
                validation["warnings"].append(f"Expected tool component not found: {tool}")

        # Check for required component types
        component_types = [comp.get("type", "") for comp in components]

        required_types = ["genesis:chat_input", "genesis:chat_output", "genesis:agent", "Memory"]
        for req_type in required_types:
            if req_type not in component_types:
                validation["warnings"].append(f"Missing recommended component type: {req_type}")

        # Validate provides relationships
        for i, comp in enumerate(components):
            provides = comp.get("provides", [])
            for provide in provides:
                if not isinstance(provide, dict):
                    validation["errors"].append(f"Invalid provides declaration in component {i}")
                    continue

                if "useAs" not in provide or "in" not in provide:
                    validation["errors"].append(f"Provides declaration missing useAs or in field in component {i}")

        # Display results
        print("=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)

        validation["valid"] = len(validation["errors"]) == 0

        if validation["valid"]:
            print("✅ VALIDATION PASSED")
            print("   The Agent Builder specification is structurally valid!")
        else:
            print("❌ VALIDATION FAILED")
            print("   The specification has errors that need to be fixed.")

        print()

        # Show errors
        if validation["errors"]:
            print("🚨 ERRORS:")
            for i, error in enumerate(validation["errors"], 1):
                print(f"   {i}. {error}")
            print()

        # Show warnings
        if validation["warnings"]:
            print("⚠️  WARNINGS:")
            for i, warning in enumerate(validation["warnings"], 1):
                print(f"   {i}. {warning}")
            print()

        # Summary
        print("📊 SUMMARY:")
        print(f"   • Valid: {validation['valid']}")
        print(f"   • Errors: {len(validation['errors'])}")
        print(f"   • Warnings: {len(validation['warnings'])}")
        print(f"   • Total Components: {len(components)}")
        print(f"   • Agent Builder Tools Found: {len(found_tools)}/10")

        # Component breakdown
        print()
        print("🔧 COMPONENT ANALYSIS:")
        for comp in components:
            comp_id = comp.get("id", "unknown")
            comp_type = comp.get("type", "unknown")
            comp_name = comp.get("name", "unnamed")
            print(f"   • {comp_id}: {comp_type} ({comp_name})")

        if validation["valid"]:
            print()
            print("🎉 The Agent Builder specification is ready for the next phase!")
            print("   Next steps:")
            print("   1. Create system prompt with CLAUDE.md integration")
            print("   2. Test the Agent Builder with sample conversations")
            print("   3. Deploy to development environment")
        else:
            print()
            print("🔧 Please fix the errors above before proceeding.")

        return validation["valid"]

    except FileNotFoundError:
        print(f"❌ Error: Specification file not found at {spec_path}")
        return False
    except Exception as e:
        print(f"❌ Error validating specification: {str(e)}")
        return False

if __name__ == "__main__":
    success = validate_agent_builder_spec()
    sys.exit(0 if success else 1)