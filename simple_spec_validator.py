#!/usr/bin/env python3
"""
Simple specification validator that checks basic structure and common issues.
"""
import yaml
import os
from pathlib import Path
import re

def validate_spec_structure(spec_data, file_path):
    """Validate basic specification structure."""
    errors = []
    warnings = []

    # Check required fields
    required_fields = ["name", "description", "agentGoal", "components"]
    for field in required_fields:
        if field not in spec_data:
            errors.append(f"Missing required field: {field}")

    # Check ID format if present
    if "id" in spec_data:
        id_val = spec_data["id"]
        if not re.match(r"urn:agent:genesis:[^:]+:[^:]+:[^:]+", id_val):
            errors.append(f"Invalid URN format for id: {id_val}")
    else:
        warnings.append("Missing 'id' field - should follow URN format")

    # Check components structure
    if "components" in spec_data:
        components = spec_data["components"]
        if isinstance(components, list):
            for i, comp in enumerate(components):
                if not isinstance(comp, dict):
                    errors.append(f"Component {i} is not an object")
                    continue

                # Check required component fields
                if "type" not in comp:
                    errors.append(f"Component {i} missing 'type' field")
                if "id" not in comp:
                    errors.append(f"Component {i} missing 'id' field")

                # Check provides structure
                if "provides" in comp:
                    provides = comp["provides"]
                    if isinstance(provides, list):
                        for j, provide in enumerate(provides):
                            if not isinstance(provide, dict):
                                errors.append(f"Component {i} provides[{j}] is not an object")
                            elif "useAs" not in provide or "in" not in provide:
                                errors.append(f"Component {i} provides[{j}] missing 'useAs' or 'in'")
        elif isinstance(components, dict):
            # Dict format validation
            for comp_id, comp_data in components.items():
                if not isinstance(comp_data, dict):
                    errors.append(f"Component '{comp_id}' is not an object")
                    continue

                if "type" not in comp_data:
                    errors.append(f"Component '{comp_id}' missing 'type' field")
        else:
            errors.append("Components must be a list or dictionary")

    return {"errors": errors, "warnings": warnings}

def check_component_types(spec_data):
    """Check for known component type issues."""
    warnings = []
    errors = []

    components = spec_data.get("components", [])
    if isinstance(components, dict):
        components = list(components.values())

    known_genesis_types = {
        "genesis:chat_input", "genesis:chat_output", "genesis:agent",
        "genesis:prompt_template", "genesis:knowledge_hub_search", "genesis:mcp_tool",
        "genesis:crewai_agent", "genesis:crewai_sequential_task", "genesis:crewai_sequential_crew",
        "genesis:api_request", "genesis:autonomize_model", "genesis:form_recognizer", "genesis:file"
    }

    for comp in components:
        if isinstance(comp, dict):
            comp_type = comp.get("type", "")
            if comp_type.startswith("genesis:") and comp_type not in known_genesis_types:
                warnings.append(f"Unknown genesis component type: {comp_type}")

    return {"errors": errors, "warnings": warnings}

def validate_single_spec(file_path):
    """Validate a single specification file."""
    try:
        with open(file_path, 'r') as f:
            spec_data = yaml.safe_load(f)

        if not spec_data:
            return {"valid": False, "errors": ["Empty YAML file"], "warnings": []}

        # Basic structure validation
        structure_result = validate_spec_structure(spec_data, file_path)

        # Component type validation
        type_result = check_component_types(spec_data)

        # Combine results
        all_errors = structure_result["errors"] + type_result["errors"]
        all_warnings = structure_result["warnings"] + type_result["warnings"]

        return {
            "valid": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "spec_data": spec_data
        }

    except yaml.YAMLError as e:
        return {"valid": False, "errors": [f"YAML parse error: {e}"], "warnings": []}
    except Exception as e:
        return {"valid": False, "errors": [f"Validation error: {e}"], "warnings": []}

def main():
    """Validate all specifications."""
    specs_dir = Path("src/backend/base/langflow/specifications_library/agents")
    # Include both old and new directory structures during migration
    yaml_files = []

    # New categorized structure
    healthcare_dir = specs_dir / "healthcare"
    operations_dir = specs_dir / "operations"

    if healthcare_dir.exists():
        yaml_files.extend(list(healthcare_dir.rglob("*.yaml")))
    if operations_dir.exists():
        yaml_files.extend(list(operations_dir.rglob("*.yaml")))

    # Old structure (if any files remain)
    for old_dir in ["multi-tool", "patient-experience", "prompted", "provider-enablement", "simple", "single-tool", "utilization-management"]:
        old_path = specs_dir / old_dir
        if old_path.exists():
            yaml_files.extend(list(old_path.rglob("*.yaml")))

    print(f"Found {len(yaml_files)} specification files\n")

    total_errors = 0
    total_warnings = 0
    failed_specs = []
    passed_specs = []

    validation_results = {}

    for yaml_file in yaml_files:
        relative_path = str(yaml_file.relative_to(specs_dir))
        result = validate_single_spec(yaml_file)

        validation_results[relative_path] = result

        status = "✅ PASS" if result["valid"] else "❌ FAIL"
        error_count = len(result["errors"])
        warning_count = len(result["warnings"])

        print(f"{status} {relative_path}")
        print(f"   Errors: {error_count}, Warnings: {warning_count}")

        if result["valid"]:
            passed_specs.append(relative_path)
        else:
            failed_specs.append(relative_path)
            # Show errors
            for error in result["errors"][:3]:  # Show first 3 errors
                print(f"   ❌ {error}")

        # Show warnings
        for warning in result["warnings"][:2]:  # Show first 2 warnings
            print(f"   ⚠️ {warning}")

        total_errors += error_count
        total_warnings += warning_count
        print()

    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total specifications: {len(yaml_files)}")
    print(f"Passed: {len(passed_specs)}")
    print(f"Failed: {len(failed_specs)}")
    print(f"Total errors: {total_errors}")
    print(f"Total warnings: {total_warnings}")

    if failed_specs:
        print(f"\n❌ Failed specifications:")
        for spec in failed_specs:
            print(f"  - {spec}")

    if passed_specs:
        print(f"\n✅ Passed specifications:")
        for spec in passed_specs:
            print(f"  - {spec}")

    return validation_results

if __name__ == "__main__":
    main()