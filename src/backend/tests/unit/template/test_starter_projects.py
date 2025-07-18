"""Comprehensive tests for starter project templates.

Tests all JSON templates in the starter_projects folder to ensure they:
1. Are valid JSON
2. Have required structure (nodes, edges)
3. Don't have basic security issues
4. Can be built into working flows

Validates that templates work correctly and prevent unexpected breakage.
"""

import json
from pathlib import Path

import pytest

# Import langflow validation utilities
from langflow.utils.template_validation import (
    validate_flow_can_build,
    validate_flow_endpoint,
    validate_flow_execution,
    validate_template_structure,
)


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory."""
    return Path("src/backend/base/langflow/initial_setup/starter_projects")


class TestStarterProjects:
    """Test all starter project templates."""

    def test_templates_exist(self):
        """Test that templates directory exists and has templates."""
        path = get_starter_projects_path()
        assert path.exists(), f"Directory not found: {path}"

        templates = list(path.glob("*.json"))
        assert len(templates) > 0, "No template files found"

    def test_all_templates_valid_json(self):
        """Test all templates are valid JSON."""
        path = get_starter_projects_path()
        templates = list(path.glob("*.json"))

        for template_file in templates:
            with template_file.open(encoding="utf-8") as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {template_file.name}: {e}")

    def test_all_templates_structure(self):
        """Test all templates have required structure."""
        path = get_starter_projects_path()
        templates = list(path.glob("*.json"))

        all_errors = []
        for template_file in templates:
            with template_file.open(encoding="utf-8") as f:
                template_data = json.load(f)

            errors = validate_template_structure(template_data, template_file.name)
            all_errors.extend(errors)

        if all_errors:
            error_msg = "\n".join(all_errors)
            pytest.fail(f"Template structure errors:\n{error_msg}")

    def test_all_templates_can_build_flow(self):
        """Test all templates can be built into working flows."""
        path = get_starter_projects_path()
        templates = list(path.glob("*.json"))

        all_errors = []
        for template_file in templates:
            with template_file.open(encoding="utf-8") as f:
                template_data = json.load(f)

            errors = validate_flow_can_build(template_data, template_file.name)
            all_errors.extend(errors)

        if all_errors:
            error_msg = "\n".join(all_errors)
            pytest.fail(f"Flow build errors:\n{error_msg}")

    @pytest.mark.asyncio
    async def test_all_templates_validate_endpoint(self, client, logged_in_headers):
        """Test all templates using the validate endpoint."""
        path = get_starter_projects_path()
        templates = list(path.glob("*.json"))

        all_errors = []
        for template_file in templates:
            with template_file.open(encoding="utf-8") as f:
                template_data = json.load(f)

            errors = await validate_flow_endpoint(client, template_data, template_file.name, logged_in_headers)
            all_errors.extend(errors)

        if all_errors:
            error_msg = "\n".join(all_errors)
            pytest.fail(f"Endpoint validation errors:\n{error_msg}")

    @pytest.mark.asyncio
    async def test_all_templates_flow_execution(self, client, logged_in_headers):
        """Test all templates can execute successfully."""
        path = get_starter_projects_path()
        templates = list(path.glob("*.json"))

        all_errors = []
        for template_file in templates:
            with template_file.open(encoding="utf-8") as f:
                template_data = json.load(f)

            errors = await validate_flow_execution(client, template_data, template_file.name, logged_in_headers)
            all_errors.extend(errors)

        if all_errors:
            error_msg = "\n".join(all_errors)
            pytest.fail(f"Flow execution errors:\n{error_msg}")
