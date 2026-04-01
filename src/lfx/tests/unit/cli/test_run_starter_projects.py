"""Test run command with all starter project templates.

Tests that all starter project JSON files can be loaded by lfx run command
without import errors for langflow modules. We expect execution errors
(missing API keys, etc.) but no import/module errors.
"""

import json
from pathlib import Path

import pytest
from lfx.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory."""
    # Use absolute path to find the starter projects
    test_file_path = Path(__file__).resolve()

    # Navigate up to find the langflow project root
    current = test_file_path.parent
    while current != current.parent:
        if (current / "src" / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects").exists():
            return current / "src" / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"
        current = current.parent

    # Fallback to a relative path from the test file
    # test_file is in: src/lfx/tests/unit/cli
    # starter projects are in: src/backend/base/langflow/initial_setup/starter_projects
    project_root = test_file_path.parent.parent.parent.parent.parent
    return project_root / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"


def get_starter_project_files():
    """Get all starter project JSON files for parameterization."""
    starter_path = get_starter_projects_path()
    if not starter_path.exists():
        return []
    return sorted(starter_path.glob("*.json"))


class TestRunStarterProjects:
    """Test run command with all starter project templates."""

    def test_starter_projects_exist(self):
        """Test that starter projects directory exists and has templates."""
        path = get_starter_projects_path()
        assert path.exists(), f"Starter projects directory not found: {path}"

        templates = get_starter_project_files()
        assert len(templates) > 0, "No starter project files found"

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_starter_project_no_import_errors(self, template_file):
        """Test that starter project can be loaded without langflow or lfx import errors.

        We expect execution errors (missing API keys, missing inputs, etc.)
        but there should be NO errors about importing langflow or lfx modules.
        """
        # Run the command with --no-check-variables to skip variable validation
        # Use verbose mode to get detailed error messages in stderr
        result = runner.invoke(
            app,
            ["run", "--verbose", "--no-check-variables", str(template_file), "test input"],
        )

        # The command will likely fail due to missing API keys, etc.
        # But we're checking that there are no import errors

        # Use the combined output provided by Click/Typer
        all_output = result.output

        # Check for import errors related to langflow or lfx
        if "ModuleNotFoundError" in all_output or "ImportError" in all_output or "Module" in all_output:
            # Check for langflow import errors
            if "No module named 'langflow'" in all_output or "Module langflow" in all_output:
                # Extract the specific error for better debugging
                error_line = ""
                for line in all_output.split("\n"):
                    if "langflow" in line and ("No module named" in line or "Module" in line):
                        error_line = line.strip()
                        break
                pytest.fail(f"Langflow import error found in {template_file.name}.\nError: {error_line}")

            # Check for lfx import errors (these indicate structural issues)
            if "No module named 'lfx." in all_output or "Module lfx." in all_output:
                # Extract the specific error for better debugging
                import re

                # Remove ANSI color codes for cleaner output
                clean_output = re.sub(r"\x1b\[[0-9;]*m", "", all_output)

                error_lines = []
                for line in clean_output.split("\n"):
                    if "lfx" in line and ("No module named" in line or "Module lfx." in line):
                        # Extract just the module name from various error formats
                        if "No module named" in line:
                            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", line)
                            if match:
                                error_lines.append(f"  - Missing module: {match.group(1)}")
                        elif "Module lfx." in line and "not found" in line:
                            match = re.search(r"Module (lfx\.[^\s]+)", line)
                            if match:
                                error_lines.append(f"  - Missing module: {match.group(1)}")

                # Deduplicate while preserving order
                seen = set()
                unique_errors = []
                for error in error_lines:
                    if error not in seen:
                        seen.add(error)
                        unique_errors.append(error)

                error_detail = "\n".join(unique_errors[:5])  # Show first 5 unique lfx errors
                pytest.fail(
                    f"LFX import error found in {template_file.name}.\n"
                    f"This indicates lfx internal structure issues.\n"
                    f"Missing modules:\n{error_detail}"
                )

            # Check for other critical import errors
            if "cannot import name" in all_output and ("langflow" in all_output or "lfx" in all_output):
                # Extract the specific import error
                error_line = ""
                for line in all_output.split("\n"):
                    if "cannot import name" in line:
                        error_line = line.strip()
                        break
                pytest.fail(f"Import error found in {template_file.name}.\nError: {error_line}")

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_starter_project_valid_json(self, template_file):
        """Test that starter project file is valid JSON."""
        with template_file.open(encoding="utf-8") as f:
            try:
                data = json.load(f)
                # Basic structure validation
                assert "data" in data or "nodes" in data, f"Missing 'data' or 'nodes' in {template_file.name}"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {template_file.name}: {e}")

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_starter_project_format_options(self, template_file):
        """Test that starter projects can be run with different output formats.

        This tests that the basic command parsing works, even if execution fails.
        """
        formats = ["json", "text", "message", "result"]

        for fmt in formats:
            result = runner.invoke(
                app,
                ["run", "--format", fmt, "--no-check-variables", str(template_file), "test"],
            )

            # We don't check exit code as it may fail due to missing dependencies
            # We just want to ensure the command is parsed and attempted

            # Check that we got some output (even if it's an error)
            assert len(result.output) > 0, f"No output for {template_file.name} with format {fmt}"

    def test_run_basic_starter_projects_detailed(self):
        """Test basic starter projects that should have minimal dependencies."""
        basic_templates = [
            "Basic Prompting.json",
            "Basic Prompt Chaining.json",
        ]

        starter_path = get_starter_projects_path()

        for template_name in basic_templates:
            template_file = starter_path / template_name
            if not template_file.exists():
                continue

            result = runner.invoke(
                app,
                ["run", "--verbose", "--no-check-variables", str(template_file), "Hello test"],
            )

            # These basic templates might still fail due to missing LLM API keys
            # but should not have import errors
            all_output = result.output

            # More specific checks for these basic templates
            assert "No module named 'langflow'" not in all_output, f"Langflow import error in {template_name}"

            # Check for module not found errors specifically related to langflow
            # (Settings service errors are runtime errors, not import errors)
            if "ModuleNotFoundError" in all_output and "langflow" in all_output and "lfx.services" not in all_output:
                # This is an actual langflow import error, not an internal lfx error
                pytest.fail(f"Module not found error for langflow in {template_name}")

    @pytest.mark.parametrize("template_file", get_starter_project_files()[:5], ids=lambda x: x.name)
    def test_run_starter_project_with_stdin(self, template_file):
        """Test loading starter projects via stdin (testing first 5 for speed)."""
        with template_file.open(encoding="utf-8") as f:
            json_content = f.read()

        result = runner.invoke(
            app,
            ["run", "--stdin", "--no-check-variables", "--input-value", "test"],
            input=json_content,
        )

        # Check that the command attempted to process the input
        assert len(result.output) > 0

        # Verify no import errors
        all_output = result.output
        assert "No module named 'langflow'" not in all_output

    @pytest.mark.parametrize("template_file", get_starter_project_files()[:5], ids=lambda x: x.name)
    def test_run_starter_project_inline_json(self, template_file):
        """Test loading starter projects via --flow-json option (testing first 5 for speed)."""
        with template_file.open(encoding="utf-8") as f:
            json_content = f.read()

        result = runner.invoke(
            app,
            ["run", "--flow-json", json_content, "--no-check-variables", "--input-value", "test"],
        )

        # Check that the command attempted to process the input
        assert len(result.output) > 0

        # Verify no import errors
        all_output = result.output
        assert "No module named 'langflow'" not in all_output
