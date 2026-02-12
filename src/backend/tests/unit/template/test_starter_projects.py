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

            # Verify that the JSON field_order exactly matches the component's full field order.
            # A subset would cause layout inconsistency between template and sidebar components.
            if json_field_order != component_field_order:
                display = node_data.get("display_name") or node_data.get("type", "?")
                missing = [f for f in component_field_order if f not in json_field_order]
                extra = [f for f in json_field_order if f not in component_field_order]
                detail_lines = [
                    f"    JSON field_order:     {json_field_order}",
                    f"    Expected (component): {component_field_order}",
                ]
                if missing:
                    detail_lines.append(f"    Missing fields:       {missing}")
                if extra:
                    detail_lines.append(f"    Extra fields:         {extra}")
                errors.append(f"  Node '{display}' ({class_name}):\n" + "\n".join(detail_lines))

        if errors:
            error_msg = "\n".join(errors)
            pytest.fail(f"field_order mismatches in {template_file.name}:\n{error_msg}")

    @pytest.mark.parametrize("template_file", get_template_files(), ids=lambda x: x.name)
    def test_template_nodes_no_overlap(self, template_file):
        """Test that no two generic nodes overlap on the canvas."""
        with template_file.open(encoding="utf-8") as f:
            template_data = json.load(f)

        nodes = template_data.get("data", {}).get("nodes", [])

        # Collect bounding boxes for generic (non-note) nodes
        boxes = []
        for node in nodes:
            if node.get("type") == "noteNode":
                continue
            pos = node.get("position", {})
            measured = node.get("measured", {})
            x = pos.get("x")
            y = pos.get("y")
            w = measured.get("width")
            h = measured.get("height")
            if x is None or y is None or w is None or h is None:
                continue
            display = node.get("data", {}).get("display_name") or node.get("data", {}).get("type", node.get("id", "?"))
            boxes.append((display, x, y, w, h))

        # Minimum overlap in pixels on each axis to count as a real overlap.
        # Stored `measured` dimensions can be slightly stale, so ignore
        # near-miss intersections smaller than this threshold.
        min_overlap_px = 20

        errors = []
        for i, (name_a, ax, ay, aw, ah) in enumerate(boxes):
            for name_b, bx, by, bw, bh in boxes[i + 1 :]:
                # Compute overlap extent on each axis
                overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
                overlap_y = min(ay + ah, by + bh) - max(ay, by)
                if overlap_x > min_overlap_px and overlap_y > min_overlap_px:
                    errors.append(f"  '{name_a}' and '{name_b}' overlap on the canvas")

        if errors:
            error_msg = "\n".join(errors)
            pytest.fail(f"Node overlaps in {template_file.name}:\n{error_msg}")

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
