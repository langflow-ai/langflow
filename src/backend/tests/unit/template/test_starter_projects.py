"""Comprehensive tests for starter project templates.

Tests all JSON templates in the starter_projects folder to ensure they:
1. Are valid JSON
2. Have required structure (nodes, edges)
3. Don't have basic security issues
4. Can be built into working flows

Validates that templates work correctly and prevent unexpected breakage.
"""

import json
from importlib import import_module
from pathlib import Path

import pytest

# Import langflow validation utilities
from langflow.utils.template_validation import (
    validate_flow_can_build,
    validate_flow_execution,
    validate_template_structure,
)


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory."""
    return Path("src/backend/base/langflow/initial_setup/starter_projects")


def get_template_files():
    """Get all template files for parameterization."""
    return list(get_starter_projects_path().glob("*.json"))


def get_basic_template_files():
    """Get basic template files for parameterization."""
    path = get_starter_projects_path()
    basic_templates = ["Basic Prompting.json", "Basic Prompt Chaining.json"]
    return [path / name for name in basic_templates if (path / name).exists()]


@pytest.fixture(autouse=True)
def disable_tracing(monkeypatch):
    """Disable tracing for all template tests."""
    monkeypatch.setenv("LANGFLOW_DEACTIVATE_TRACING", "true")


class TestStarterProjects:
    """Test all starter project templates."""

    def test_templates_exist(self):
        """Test that templates directory exists and has templates."""
        path = get_starter_projects_path()
        assert path.exists(), f"Directory not found: {path}"

        templates = get_template_files()
        assert len(templates) > 0, "No template files found"

    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    def test_template_valid_json(self, template_file):
        """Test template is valid JSON."""
        with template_file.open(encoding="utf-8") as f:
            try:
                json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {template_file.name}: {e}")

    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    def test_template_structure(self, template_file):
        """Test template has required structure."""
        with template_file.open(encoding="utf-8") as f:
            template_data = json.load(f)

        errors = validate_template_structure(template_data, template_file.name)
        if errors:
            error_msg = "\n".join(errors)
            pytest.fail(f"Template structure errors in {template_file.name}:\n{error_msg}")

    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    def test_template_can_build_flow(self, template_file):
        """Test template can be built into working flow."""
        with template_file.open(encoding="utf-8") as f:
            template_data = json.load(f)

        errors = validate_flow_can_build(template_data, template_file.name)
        if errors:
            error_msg = "\n".join(errors)
            pytest.fail(f"Flow build errors in {template_file.name}:\n{error_msg}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    async def test_template_validate_endpoint(self, template_file, client, logged_in_headers):
        """Test template using the validate endpoint."""
        with template_file.open(encoding="utf-8") as f:
            template_data = json.load(f)

        errors = await validate_flow_execution(client, template_data, template_file.name, logged_in_headers)
        if errors:
            error_msg = "\n".join(errors)
            pytest.fail(f"Endpoint validation errors in {template_file.name}:\n{error_msg}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    async def test_template_flow_execution(self, template_file, client, logged_in_headers):
        """Test template can execute successfully."""
        try:
            with template_file.open(encoding="utf-8") as f:
                template_data = json.load(f)

            errors = await validate_flow_execution(client, template_data, template_file.name, logged_in_headers)
            if errors:
                error_msg = "\n".join(errors)
                pytest.fail(f"Template execution errors in {template_file.name}:\n{error_msg}")

        except (ValueError, TypeError, KeyError, AttributeError, OSError, json.JSONDecodeError) as e:
            pytest.fail(f"{template_file.name}: Unexpected error during validation: {e!s}")

    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    def test_template_field_order_matches_component(self, template_file):
        """Test that field_order in starter project JSON matches the actual component's input order."""
        with template_file.open(encoding="utf-8") as f:
            template_data = json.load(f)

        errors = []
        for node in template_data.get("data", {}).get("nodes", []):
            node_data = node.get("data", {})
            node_info = node_data.get("node", {})
            metadata = node_info.get("metadata", {})
            module_path = metadata.get("module", "")
            json_field_order = node_info.get("field_order")

            if not module_path or json_field_order is None:
                continue

            # Parse module path: "lfx.components.foo.bar.ClassName"
            parts = module_path.rsplit(".", 1)
            if len(parts) != 2:
                continue

            module_name, class_name = parts

            try:
                mod = import_module(module_name)
                cls = getattr(mod, class_name)
                instance = cls()
                component_field_order = instance._get_field_order()
            except Exception as e:
                errors.append(
                    f"  Node '{node_data.get('display_name', node_data.get('type', '?'))}' "
                    f"({class_name}): Could not instantiate component: {e}"
                )
                continue

            # The JSON field_order may be a subset of the component's full field order.
            # Verify that the fields listed maintain the same relative order as the component.
            json_fields_set = set(json_field_order)
            expected_field_order = [f for f in component_field_order if f in json_fields_set]

            if json_field_order != expected_field_order:
                display = node_data.get("display_name") or node_data.get("type", "?")
                errors.append(
                    f"  Node '{display}' ({class_name}):\n"
                    f"    JSON field_order:     {json_field_order}\n"
                    f"    Expected (component): {expected_field_order}"
                )

        if errors:
            error_msg = "\n".join(errors)
            pytest.fail(f"field_order mismatches in {template_file.name}:\n{error_msg}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("template_file", get_basic_template_files(), ids=lambda x: x.name)
    async def test_basic_template_flow_execution(self, template_file, client, logged_in_headers):
        """Test basic template can execute successfully."""
        try:
            with template_file.open(encoding="utf-8") as f:
                template_data = json.load(f)

            errors = await validate_flow_execution(client, template_data, template_file.name, logged_in_headers)
            if errors:
                error_msg = "\n".join(errors)
                pytest.fail(f"Basic template execution errors in {template_file.name}:\n{error_msg}")

        except (ValueError, TypeError, KeyError, AttributeError, OSError, json.JSONDecodeError) as e:
            pytest.fail(f"{template_file.name}: Unexpected error during validation: {e!s}")
