"""Test run command with starter project templates from 1.6.0 for backwards compatibility.

Tests that all starter project JSON files from tag 1.6.0 can be loaded by lfx run command
without import errors for langflow modules. We expect execution errors
(missing API keys, etc.) but no import/module errors.

This ensures backwards compatibility with existing starter projects.
"""

from pathlib import Path

import pytest
from lfx.__main__ import app
from typer.testing import CliRunner

runner = CliRunner()


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory.

    Returns:
        Path to the 1.6.0 starter projects directory in tests/data.
    """
    test_file_path = Path(__file__).resolve()
    return test_file_path.parent.parent.parent / "data" / "starter_projects_1_6_0"


def get_starter_project_files():
    """Get all starter project JSON files for parameterization.

    Returns files in sorted order for deterministic test execution.
    """
    starter_path = get_starter_projects_path()
    if not starter_path.exists():
        return []
    return sorted(starter_path.glob("*.json"))


class TestRunStarterProjectsBackwardCompatibility:
    """Test run command with starter project templates from 1.6.0 for backwards compatibility."""

    def test_starter_projects_1_6_0_exist(self):
        """Test that 1.6.0 starter projects directory exists and has templates."""
        path = get_starter_projects_path()
        if not path.exists():
            pytest.fail(f"1.6.0 starter projects cache directory not found: {path}")

        templates = get_starter_project_files()
        if len(templates) == 0:
            pytest.fail(f"No 1.6.0 starter project files found in cache: {path}")

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_1_6_0_starter_project_no_import_errors(self, template_file):
        """Test that 1.6.0 starter project can be loaded without langflow or lfx import errors.

        We expect execution errors (missing API keys, missing inputs, etc.)
        but there should be NO errors about importing langflow or lfx modules.

        Note: Some 1.6.0 starter projects contain components with import bugs that were
        fixed in later versions. These are marked as expected failures.
        """
        # Known failing starter projects due to component-level import bugs in 1.6.0
        known_failing_projects = {
            "News Aggregator.json": "Contains SaveToFile component with langflow.api import bug "
            "(fixed in later versions)"
        }

        if template_file.name in known_failing_projects:
            pytest.xfail(f"Known 1.6.0 component bug: {known_failing_projects[template_file.name]}")
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
                pytest.fail(f"Langflow import error found in 1.6.0 template {template_file.name}.\nError: {error_line}")

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
                    f"LFX import error found in 1.6.0 template {template_file.name}.\n"
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
                pytest.fail(f"Import error found in 1.6.0 template {template_file.name}.\nError: {error_line}")

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_1_6_0_starter_project_format_options(self, template_file):
        """Test that 1.6.0 starter projects can be run with different output formats.

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
            if len(result.output) == 0:
                pytest.fail(f"No output for 1.6.0 template {template_file.name} with format {fmt}")

    @pytest.mark.xfail(reason="CLI --format option doesn't apply to error messages")
    @pytest.mark.parametrize("template_file", get_starter_project_files()[:1], ids=lambda x: x.name)
    def test_run_1_6_0_format_option_applies_to_errors(self, template_file):
        """Test that --format option applies to error messages.

        Currently fails: Error messages are always returned as JSON regardless of --format.
        This test documents the expected behavior for future CLI fixes.
        """
        import json as json_module

        # Test with text format - errors should be plain text, not JSON
        result = runner.invoke(
            app,
            ["run", "--format", "text", "--no-check-variables", str(template_file), "test"],
        )

        # If we get an error (which we expect due to missing API keys), it should be plain text
        if result.exit_code != 0:
            # Should NOT be valid JSON when format is "text"
            try:
                json_module.loads(result.output)
                pytest.fail(
                    "Error output is JSON format when --format text was specified. "
                    "Error messages should respect the --format option."
                )
            except json_module.JSONDecodeError:
                # This is the expected behavior - plain text error
                pass

    @pytest.mark.xfail(reason="CLI --format option doesn't apply when --verbose is used")
    @pytest.mark.parametrize("template_file", get_starter_project_files()[:1], ids=lambda x: x.name)
    def test_run_1_6_0_format_option_applies_with_verbose(self, template_file):
        """Test that --format option applies even when --verbose is used.

        Currently fails: --verbose output doesn't conform to --format specification.
        This test documents the expected behavior for future CLI fixes.
        """
        import json as json_module

        # Test with JSON format + verbose - all output should be valid JSON
        result = runner.invoke(
            app,
            ["run", "--format", "json", "--verbose", "--no-check-variables", str(template_file), "test"],
        )

        # With --format json, even verbose output should be parseable as JSON
        # (or at least the final output should be JSON without mixed text logs)
        lines = result.output.strip().split("\n")
        last_line = lines[-1] if lines else ""

        try:
            json_module.loads(last_line)
        except json_module.JSONDecodeError:
            pytest.fail(
                "With --format json and --verbose, expected final output to be valid JSON. "
                "Verbose logs should not interfere with JSON output format."
            )

    @pytest.mark.xfail(
        reason="1.6.0 basic templates have langflow import issues - components expect langflow package to be available"
    )
    def test_run_basic_1_6_0_starter_projects_detailed(self):
        """Test basic 1.6.0 starter projects that should have minimal dependencies."""
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
            if "No module named 'langflow'" in all_output:
                pytest.fail(f"Langflow import error in 1.6.0 template {template_name}")

            # Check for module not found errors specifically related to langflow
            # (Settings service errors are runtime errors, not import errors)
            if "ModuleNotFoundError" in all_output and "langflow" in all_output and "lfx.services" not in all_output:
                # This is an actual langflow import error, not an internal lfx error
                pytest.fail(f"Module not found error for langflow in 1.6.0 template {template_name}")

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_1_6_0_starter_project_with_stdin(self, template_file):
        """Test loading 1.6.0 starter projects via stdin."""
        with template_file.open(encoding="utf-8") as f:
            json_content = f.read()

        result = runner.invoke(
            app,
            ["run", "--stdin", "--no-check-variables", "--input-value", "test"],
            input=json_content,
        )

        # Check that the command attempted to process the input
        if len(result.output) == 0:
            pytest.fail("No output from 1.6.0 stdin test")

        # Verify no import errors
        all_output = result.output
        if "No module named 'langflow'" in all_output:
            pytest.fail("Langflow import error in 1.6.0 stdin test")

    @pytest.mark.parametrize("template_file", get_starter_project_files(), ids=lambda x: x.name)
    def test_run_1_6_0_starter_project_inline_json(self, template_file):
        """Test loading 1.6.0 starter projects via --flow-json option."""
        with template_file.open(encoding="utf-8") as f:
            json_content = f.read()

        result = runner.invoke(
            app,
            ["run", "--flow-json", json_content, "--no-check-variables", "--input-value", "test"],
        )

        # Check that the command attempted to process the input
        if len(result.output) == 0:
            pytest.fail("No output from 1.6.0 inline JSON test")

        # Verify no import errors
        all_output = result.output
        if "No module named 'langflow'" in all_output:
            pytest.fail("Langflow import error in 1.6.0 inline JSON test")
