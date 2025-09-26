"""Test run command with starter project templates from 1.6.0 for backwards compatibility.

Tests that all starter project JSON files from tag 1.6.0 can be loaded by lfx run command
without import errors for langflow modules. We expect execution errors
(missing API keys, etc.) but no import/module errors.

This ensures backwards compatibility with existing starter projects.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from lfx.__main__ import app

runner = CliRunner()

# GitHub configuration
GITHUB_REPO = "langflow-ai/langflow"
GITHUB_TAG = "1.6.0"
STARTER_PROJECTS_REMOTE_PATH = "src/backend/base/langflow/initial_setup/starter_projects"
HTTP_OK = 200


async def fetch_starter_projects_from_github() -> Path:
    """Fetch starter projects from GitHub tag 1.6.0 and cache them locally.

    Returns:
        Path to the cached starter projects directory.
    """
    # Create cache directory in tests/data
    test_file_path = Path(__file__).resolve()
    cache_dir = test_file_path.parent.parent.parent / "data" / "starter_projects_1_6_0"

    # If cache already exists and has files, return it
    if cache_dir.exists() and list(cache_dir.glob("*.json")):
        return cache_dir

    # Create cache directory
    cache_dir.mkdir(parents=True, exist_ok=True)

    # GitHub API URL for the tag's tree
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{GITHUB_TAG}?recursive=1"

    async with httpx.AsyncClient() as client:
        # Get the tree structure
        response = await client.get(api_url)
        if response.status_code != HTTP_OK:
            error_msg = f"Failed to fetch GitHub tree: {response.status_code}"
            raise RuntimeError(error_msg)
        tree_data = response.json()

        # Find all JSON files in the starter_projects directory
        starter_project_files = [
            item
            for item in tree_data.get("tree", [])
            if (
                item["path"].startswith(STARTER_PROJECTS_REMOTE_PATH)
                and item["path"].endswith(".json")
                and item["type"] == "blob"
            )
        ]

        if not starter_project_files:
            error_msg = f"No starter project files found in {STARTER_PROJECTS_REMOTE_PATH}"
            raise RuntimeError(error_msg)

        # Download each file
        for file_item in starter_project_files:
            file_name = Path(file_item["path"]).name
            file_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_TAG}/{file_item['path']}"

            file_response = await client.get(file_url)
            if file_response.status_code != HTTP_OK:
                # Use logger or skip silently in tests
                continue

            content = file_response.text

            # Save to cache directory
            cache_file = cache_dir / file_name
            cache_file.write_text(content, encoding="utf-8")

    return cache_dir


def get_starter_projects_path() -> Path:
    """Get path to starter projects directory from remote cache."""
    # Use cached remote starter projects from 1.6.0
    test_file_path = Path(__file__).resolve()
    cache_dir = test_file_path.parent.parent.parent / "data" / "starter_projects_1_6_0"

    # Ensure we have the remote files cached
    if not cache_dir.exists() or not list(cache_dir.glob("*.json")):
        # Download files synchronously if not cached
        asyncio.run(fetch_starter_projects_from_github())

    return cache_dir


def get_starter_project_files():
    """Get all starter project JSON files for parameterization."""
    starter_path = get_starter_projects_path()
    if not starter_path.exists():
        return []
    return sorted(starter_path.glob("*.json"))


class TestRunStarterProjectsBackwardCompatibility:
    """Test run command with starter project templates from 1.6.0 for backwards compatibility."""

    @classmethod
    def setup_class(cls):
        """Set up test class by ensuring starter projects are cached."""
        # Ensure starter projects from 1.6.0 are downloaded and cached
        asyncio.run(fetch_starter_projects_from_github())

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
    def test_run_1_6_0_starter_project_valid_json(self, template_file):
        """Test that 1.6.0 starter project file is valid JSON."""
        with template_file.open(encoding="utf-8") as f:
            try:
                data = json.load(f)
                # Basic structure validation
                if "data" not in data and "nodes" not in data:
                    pytest.fail(f"Missing 'data' or 'nodes' in 1.6.0 template {template_file.name}")
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in 1.6.0 template {template_file.name}: {e}")

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

    @pytest.mark.parametrize("template_file", get_starter_project_files()[:5], ids=lambda x: x.name)
    def test_run_1_6_0_starter_project_with_stdin(self, template_file):
        """Test loading 1.6.0 starter projects via stdin (testing first 5 for speed)."""
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

    @pytest.mark.parametrize("template_file", get_starter_project_files()[:5], ids=lambda x: x.name)
    def test_run_1_6_0_starter_project_inline_json(self, template_file):
        """Test loading 1.6.0 starter projects via --flow-json option (testing first 5 for speed)."""
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
