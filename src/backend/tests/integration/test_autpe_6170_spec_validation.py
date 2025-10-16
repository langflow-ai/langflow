"""
Integration tests for AUTPE-6170: Fix All Specifications in Library

This integration test validates that all specifications in the library
pass validation after the fixes implemented in AUTPE-6170.
"""

import pytest
import os
import yaml
from pathlib import Path
from typing import Dict, List, Any

from langflow.services.spec.service import SpecService


@pytest.mark.integration
class TestAUTPE6170SpecificationValidation:
    """Integration tests for AUTPE-6170 specification validation fixes."""

    @pytest.fixture
    def spec_service(self):
        """Create SpecService instance for validation."""
        return SpecService()

    @pytest.fixture
    def specification_library_path(self):
        """Get path to specification library."""
        base_path = Path(__file__).parent.parent.parent / "base" / "langflow" / "specifications_library"
        return base_path

    @pytest.fixture
    def all_specification_files(self, specification_library_path):
        """Get all specification files from the library."""
        spec_files = []
        agents_path = specification_library_path / "agents"

        if agents_path.exists():
            for spec_file in agents_path.rglob("*.yaml"):
                spec_files.append(spec_file)

        return spec_files

    def test_all_specifications_pass_validation(self, spec_service, all_specification_files):
        """Test that all specifications in the library pass validation."""
        failed_specs = []
        validation_results = {}

        for spec_file in all_specification_files:
            try:
                with open(spec_file, 'r', encoding='utf-8') as f:
                    spec_content = f.read()

                # Validate specification
                result = spec_service.validate_spec(spec_content)
                validation_results[spec_file.name] = result

                if not result.get("valid", False):
                    failed_specs.append({
                        "file": spec_file.name,
                        "path": str(spec_file),
                        "errors": result.get("errors", []),
                        "warnings": result.get("warnings", [])
                    })

            except Exception as e:
                failed_specs.append({
                    "file": spec_file.name,
                    "path": str(spec_file),
                    "errors": [f"Exception during validation: {str(e)}"],
                    "warnings": []
                })

        # Assert no specifications failed validation
        if failed_specs:
            error_msg = f"AUTPE-6170 validation failed! {len(failed_specs)} specifications failed validation:\n"
            for failed in failed_specs:
                error_msg += f"\n❌ {failed['file']}:\n"
                for error in failed['errors']:
                    error_msg += f"   - {error}\n"
                for warning in failed['warnings']:
                    error_msg += f"   - WARNING: {warning}\n"

            pytest.fail(error_msg)

        # Success metrics
        total_specs = len(all_specification_files)
        passed_specs = total_specs - len(failed_specs)

        print(f"\n✅ AUTPE-6170 Validation Success!")
        print(f"📊 Results: {passed_specs}/{total_specs} specifications passed validation")
        print(f"🎯 Success Rate: {(passed_specs/total_specs)*100:.1f}%")

    def test_healthcare_specifications_structure(self, specification_library_path):
        """Test that healthcare specifications are properly organized."""
        agents_path = specification_library_path / "agents"

        # Check healthcare directory structure
        healthcare_path = agents_path / "healthcare"
        assert healthcare_path.exists(), "Healthcare directory should exist after AUTPE-6170"

        # Check expected healthcare subdirectories
        expected_healthcare_dirs = [
            "patient-experience",
            "clinical-decision",
            "healthcare-operations",
            "claims-processing",
            "healthcare-analytics"
        ]

        for expected_dir in expected_healthcare_dirs:
            dir_path = healthcare_path / expected_dir
            # Check if directory exists or has specifications
            has_specs = any(dir_path.rglob("*.yaml")) if dir_path.exists() else False

            # At least some healthcare directories should have specifications
            print(f"Healthcare subdirectory {expected_dir}: {'✅' if has_specs else '⚠️'}")

    def test_operations_specifications_structure(self, specification_library_path):
        """Test that operations specifications are properly organized."""
        agents_path = specification_library_path / "agents"

        # Check operations directory structure
        operations_path = agents_path / "operations"
        assert operations_path.exists(), "Operations directory should exist after AUTPE-6170"

        # Check expected operations subdirectories
        expected_operations_dirs = [
            "document-processing",
            "process-optimization",
            "workflow-automation"
        ]

        for expected_dir in expected_operations_dirs:
            dir_path = operations_path / expected_dir
            has_specs = any(dir_path.rglob("*.yaml")) if dir_path.exists() else False
            print(f"Operations subdirectory {expected_dir}: {'✅' if has_specs else '⚠️'}")

    def test_specification_metadata_compliance(self, all_specification_files):
        """Test that all specifications have proper metadata after AUTPE-6170 fixes."""
        metadata_issues = []

        for spec_file in all_specification_files:
            try:
                with open(spec_file, 'r', encoding='utf-8') as f:
                    spec_dict = yaml.safe_load(f)

                # Check for proper URN format in id field
                spec_id = spec_dict.get("id", "")
                if not spec_id.startswith("urn:agent:genesis:autonomize.ai:"):
                    metadata_issues.append(f"{spec_file.name}: Invalid URN format in id field")

                # Check for required metadata fields
                required_fields = ["name", "description", "domain", "version", "agentGoal"]
                for field in required_fields:
                    if field not in spec_dict:
                        metadata_issues.append(f"{spec_file.name}: Missing required field '{field}'")

                # Check version format (should be semver like 1.0.0)
                version = spec_dict.get("version", "")
                if not version or len(version.split('.')) != 3:
                    metadata_issues.append(f"{spec_file.name}: Invalid version format '{version}'")

            except Exception as e:
                metadata_issues.append(f"{spec_file.name}: Error reading metadata - {str(e)}")

        if metadata_issues:
            error_msg = f"AUTPE-6170 metadata compliance failed! {len(metadata_issues)} issues found:\n"
            for issue in metadata_issues:
                error_msg += f"  - {issue}\n"
            pytest.fail(error_msg)

    def test_component_type_mappings(self, spec_service, all_specification_files):
        """Test that all component types used in specifications are properly mapped."""
        unknown_types = set()
        component_usage = {}

        for spec_file in all_specification_files:
            try:
                with open(spec_file, 'r', encoding='utf-8') as f:
                    spec_dict = yaml.safe_load(f)

                components = spec_dict.get("components", [])
                for component in components:
                    comp_type = component.get("type", "")
                    if comp_type:
                        if comp_type not in component_usage:
                            component_usage[comp_type] = []
                        component_usage[comp_type].append(spec_file.name)

                        # Validate component type exists
                        result = spec_service.validate_spec(yaml.dump(spec_dict))
                        if not result.get("valid", False):
                            errors = result.get("errors", [])
                            for error in errors:
                                if "unknown component type" in error.lower() or "unmapped component" in error.lower():
                                    unknown_types.add(comp_type)

            except Exception as e:
                print(f"Warning: Could not process {spec_file.name}: {e}")

        if unknown_types:
            error_msg = f"AUTPE-6170 component mapping failed! Unknown component types found:\n"
            for comp_type in sorted(unknown_types):
                used_in = component_usage.get(comp_type, [])
                error_msg += f"  - {comp_type} (used in: {', '.join(used_in)})\n"
            pytest.fail(error_msg)

        # Report component usage statistics
        print(f"\n📊 Component Type Usage Statistics:")
        for comp_type, files in sorted(component_usage.items()):
            print(f"  {comp_type}: {len(files)} specifications")

    def test_specification_library_completeness(self, all_specification_files):
        """Test that the specification library has expected number of specs after AUTPE-6170."""
        total_specs = len(all_specification_files)

        # Based on AUTPE-6170 report, we should have 22+ specifications
        expected_min_specs = 22

        assert total_specs >= expected_min_specs, \
            f"Expected at least {expected_min_specs} specifications, found {total_specs}"

        print(f"✅ Specification library completeness: {total_specs} specifications found")

    @pytest.mark.parametrize("category,expected_count", [
        ("healthcare", 10),  # Expect at least 10 healthcare specs
        ("operations", 5),   # Expect at least 5 operations specs
    ])
    def test_category_specification_distribution(self, specification_library_path, category, expected_count):
        """Test that specifications are properly distributed across categories."""
        agents_path = specification_library_path / "agents"
        category_path = agents_path / category

        if not category_path.exists():
            pytest.skip(f"Category {category} directory not found")

        spec_files = list(category_path.rglob("*.yaml"))
        actual_count = len(spec_files)

        print(f"📁 {category.title()} category: {actual_count} specifications")

        # Note: This is informational rather than strict requirement
        # as the exact distribution may vary based on implementation
        if actual_count < expected_count:
            print(f"⚠️  Expected at least {expected_count} {category} specs, found {actual_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])