"""Simple tests for starter project templates.

Tests all JSON templates in the starter_projects folder to ensure they:
1. Are valid JSON
2. Have required structure (nodes, edges)
3. Don't have basic security issues

Can also be run as a script: python test_starter_projects.py
"""

import json
from pathlib import Path
from typing import Any

import pytest


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory."""
    return Path("src/backend/base/langflow/initial_setup/starter_projects")


def validate_template_structure(template_data: dict[str, Any], filename: str) -> list[str]:
    """Validate basic template structure. Returns list of errors."""
    errors = []

    # Handle wrapped format
    data = template_data.get("data", template_data)

    # Check required fields
    if "nodes" not in data:
        errors.append(f"{filename}: Missing 'nodes' field")
    elif not isinstance(data["nodes"], list):
        errors.append(f"{filename}: 'nodes' must be a list")

    if "edges" not in data:
        errors.append(f"{filename}: Missing 'edges' field")
    elif not isinstance(data["edges"], list):
        errors.append(f"{filename}: 'edges' must be a list")

    # Check nodes have required fields
    for i, node in enumerate(data.get("nodes", [])):
        if "id" not in node:
            errors.append(f"{filename}: Node {i} missing 'id'")
        if "data" not in node:
            errors.append(f"{filename}: Node {i} missing 'data'")

    return errors


def check_security_issues(template_data: dict[str, Any], filename: str) -> list[str]:
    """Check for basic security issues. Returns list of critical issues."""
    critical_patterns = ["__import__", "eval(", "exec(", "compile(", "os.system", "subprocess"]
    issues = []

    template_str = json.dumps(template_data).lower()
    for pattern in critical_patterns:
        if pattern in template_str:
            issues.append(f"{filename}: Contains potentially dangerous pattern: {pattern}")  # noqa: PERF401

    return issues


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
