"""Tests for the lfx check command functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.cli.check import (
    analyze_component_changes,
    check_component_outdated,
    check_flow_components,
    find_component_in_types,
    generate_code_diff,
    load_specific_components,
)


@pytest.fixture
def sample_flow_data():
    """Sample flow data for testing."""
    return {
        "data": {
            "nodes": [
                {
                    "id": "test-node-1",
                    "data": {
                        "type": "ChatInput",
                        "node": {
                            "metadata": {
                                "code_hash": "old_hash_123",
                                "module": "lfx.components.input_output.chat.ChatInput",
                            },
                            "template": {"input_value": {"value": "test"}, "code": {"value": "old code"}},
                        },
                    },
                }
            ]
        }
    }


class TestCheckCommand:
    """Test cases for the check command functionality."""

    @pytest.fixture
    def sample_component_dict(self):
        """Sample component dictionary for testing."""
        return {
            "ChatInput": {
                "metadata": {"code_hash": "new_hash_456", "module": "lfx.components.input_output.chat.ChatInput"},
                "template": {
                    "input_value": {"value": "", "required": False},
                    "new_field": {"value": "default", "required": True},
                    "code": {"value": "new code"},
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

    @pytest.fixture
    def outdated_flow_file(self):
        """Path to the test outdated flow file."""
        return Path(__file__).parent.parent / "data" / "outdated_flow.json"

    def test_find_component_in_types_direct_match(self, sample_component_dict):
        """Test finding component with direct type match."""
        result = find_component_in_types("ChatInput", sample_component_dict)
        assert result is not None
        assert result["metadata"]["code_hash"] == "new_hash_456"

    def test_find_component_in_types_nested_search(self):
        """Test finding component in nested categories."""
        nested_dict = {
            "input_output": {"ChatInput": {"metadata": {"code_hash": "test_hash"}, "display_name": "Chat Input"}}
        }
        result = find_component_in_types("ChatInput", nested_dict)
        assert result is not None
        assert result["metadata"]["code_hash"] == "test_hash"

    def test_find_component_in_types_by_display_name(self):
        """Test finding component by display name."""
        nested_dict = {
            "input_output": {"chat_input": {"metadata": {"code_hash": "test_hash"}, "display_name": "ChatInput"}}
        }
        result = find_component_in_types("ChatInput", nested_dict)
        assert result is not None
        assert result["metadata"]["code_hash"] == "test_hash"

    def test_find_component_in_types_not_found(self, sample_component_dict):
        """Test component not found scenario."""
        result = find_component_in_types("NonExistentComponent", sample_component_dict)
        assert result is None

    def test_check_component_outdated_hash_comparison(self, sample_flow_data, sample_component_dict):
        """Test component outdated check using hash comparison."""
        node = sample_flow_data["data"]["nodes"][0]
        result = check_component_outdated(node, sample_component_dict, sample_component_dict["ChatInput"])

        assert result["outdated"] is True
        assert result["comparison_method"] == "hash"
        assert result["node_hash"] == "old_hash_123"
        assert result["latest_hash"] == "new_hash_456"

    def test_check_component_outdated_code_comparison(self):
        """Test component outdated check using code comparison fallback."""
        node = {
            "id": "test-node",
            "data": {
                "type": "TestComponent",
                "node": {
                    "metadata": {},  # No hash
                    "template": {"code": {"value": "old code"}},
                },
            },
        }

        component_dict = {
            "TestComponent": {
                "metadata": {},  # No hash
                "template": {"code": {"value": "new code"}},
            }
        }

        result = check_component_outdated(node, component_dict, component_dict["TestComponent"])

        assert result["outdated"] is True
        assert result["comparison_method"] == "code"

    def test_check_component_up_to_date(self):
        """Test component that is up to date."""
        node = {
            "id": "test-node",
            "data": {"type": "TestComponent", "node": {"metadata": {"code_hash": "same_hash"}, "template": {}}},
        }

        component_dict = {"TestComponent": {"metadata": {"code_hash": "same_hash"}, "template": {}}}

        result = check_component_outdated(node, component_dict, component_dict["TestComponent"])

        assert result["outdated"] is False

    def test_check_component_outdated_missing_code_error(self):
        """Test that missing code in both versions returns an error."""
        from lfx.cli.check import check_component_outdated

        # Create a node without code_hash and without code in template
        node = {
            "id": "test-node-1",
            "data": {
                "type": "TestComponent",
                "node": {
                    "metadata": {},  # No code_hash
                    "template": {
                        "input_value": {"value": "test"},
                        # No "code" field
                    },
                },
            },
        }

        # Create a component without code_hash and without code in template
        component_dict = {
            "TestComponent": {
                "metadata": {},  # No code_hash
                "template": {
                    "input_value": {"value": "", "required": False},
                    # No "code" field
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

        result = check_component_outdated(node, component_dict, component_dict["TestComponent"])

        # Should return an error, not silently treat as up-to-date
        assert "error" in result
        assert result["outdated"] is False
        assert "no code" in result["error"].lower()
        assert result["component_type"] == "TestComponent"
        assert result["node_id"] == "test-node-1"

    def test_analyze_component_changes_added_inputs(self):
        """Test analyzing added inputs."""
        current_node = {"template": {"existing_field": {"type": "str"}}, "outputs": []}

        latest_component = {
            "template": {
                "existing_field": {"type": "str"},
                "new_field": {"type": "str", "required": True, "value": "default", "display_name": "New Field"},
            },
            "outputs": [],
        }

        changes = analyze_component_changes(current_node, latest_component)

        assert len(changes["added_inputs"]) == 1
        assert changes["added_inputs"][0]["name"] == "new_field"
        assert changes["added_inputs"][0]["required"] is True

    def test_analyze_component_changes_removed_outputs(self):
        """Test analyzing removed outputs."""
        current_node = {
            "template": {},
            "outputs": [{"name": "old_output", "types": ["Message"], "display_name": "Old Output"}],
        }

        latest_component = {"template": {}, "outputs": []}

        changes = analyze_component_changes(current_node, latest_component)

        assert len(changes["removed_outputs"]) == 1
        assert changes["removed_outputs"][0]["name"] == "old_output"

    def test_generate_code_diff(self):
        """Test code diff generation."""
        current_code = "def old_function():\n    return 'old'"
        latest_code = "def new_function():\n    return 'new'"

        diff = generate_code_diff(current_code, latest_code)

        assert diff is not None
        assert len(diff["added_lines"]) > 0
        assert len(diff["removed_lines"]) > 0
        assert "new_function" in diff["full_diff"]
        assert "old_function" in diff["full_diff"]

    def test_generate_code_diff_no_changes(self):
        """Test code diff with no changes."""
        code = "def same_function():\n    return 'same'"

        diff = generate_code_diff(code, code)

        assert diff is None

    @pytest.mark.asyncio
    async def test_load_specific_components(self):
        """Test selective component loading with real components."""
        # Test with a real component that should exist
        component_modules = {"lfx.components.input_output.chat.ChatInput"}

        result = await load_specific_components(component_modules)

        # Should successfully load the ChatInput component
        assert isinstance(result, dict)
        assert "ChatInput" in result
        assert "metadata" in result["ChatInput"]
        assert "template" in result["ChatInput"]

        # Should have a code hash
        metadata = result["ChatInput"]["metadata"]
        assert "code_hash" in metadata
        assert len(metadata["code_hash"]) == 12  # Hash should be 12 characters

    @pytest.mark.asyncio
    async def test_check_flow_components_with_real_flow(self, outdated_flow_file):
        """Test checking flow components with real flow file."""
        if not outdated_flow_file.exists():
            pytest.skip("Outdated flow file not found")

        result = await check_flow_components(str(outdated_flow_file))

        # Should successfully process the file
        assert "error" not in result
        assert result["flow_path"] == str(outdated_flow_file)
        assert result["total_nodes"] > 0

        # May or may not have outdated components depending on current state
        assert "outdated_count" in result
        assert isinstance(result["outdated_components"], list)

    @pytest.mark.asyncio
    async def test_load_specific_components_error_handling(self):
        """Test error handling in selective component loading."""
        # Test with a non-existent module
        component_modules = {"non.existent.module.Component"}

        result = await load_specific_components(component_modules)

        # Should handle errors gracefully and return empty dict
        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_check_flow_components_file_not_found(self):
        """Test error handling for non-existent file."""
        result = await check_flow_components("non_existent_file.json")

        assert "error" in result
        assert "Failed to load flow file" in result["error"]

    @pytest.mark.asyncio
    async def test_check_flow_components_invalid_json(self):
        """Test error handling for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            tmp_file.write("invalid json content")
            tmp_path = tmp_file.name

        try:
            result = await check_flow_components(tmp_path)

            assert "error" in result
            assert "Failed to load flow file" in result["error"]
        finally:
            Path(tmp_path).unlink()

    def test_component_mappings(self):
        """Test that component type mappings work correctly."""
        # Test the component mappings from the find_component_in_types function
        test_cases = [
            ("Agent", "AgentComponent"),
            ("CalculatorComponent", "Calculator"),
            ("ChatInput", "ChatInputComponent"),
            ("ChatOutput", "ChatOutputComponent"),
            ("URLComponent", "URL"),
        ]

        for flow_type, comp_name in test_cases:
            from lfx.cli.check import _matches_component_type

            comp_data = {"display_name": comp_name}
            assert _matches_component_type(flow_type, comp_name, comp_data)

    @pytest.mark.asyncio
    async def test_real_outdated_flow_file(self, outdated_flow_file):
        """Test with the real outdated flow file from frontend tests."""
        if not outdated_flow_file.exists():
            pytest.skip("Outdated flow file not found")

        with patch("lfx.cli.check.get_and_cache_all_types_dict") as mock_get_types:
            # Mock some basic component types that might be in the flow
            mock_components = {
                "ChatInput": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                },
                "ChatOutput": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                },
                "Prompt": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                },
                "OpenAIModel": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                },
                "Memory": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                },
            }
            mock_get_types.return_value = mock_components

            result = await check_flow_components(str(outdated_flow_file))

            assert "error" not in result
            assert "total_nodes" in result
            assert "outdated_count" in result
            assert result["total_nodes"] > 0

    def test_breaking_change_detection(self):
        """Test breaking change detection logic."""
        from lfx.cli.check import check_breaking_changes

        # Test removed output (breaking)
        current_node = {"outputs": [{"name": "old_output", "types": ["Message"]}], "template": {}}
        latest_component = {"outputs": [], "template": {}}

        assert check_breaking_changes(current_node, latest_component) is True

        # Test added required input (breaking)
        current_node = {"outputs": [], "template": {"existing": {"required": False}}}
        latest_component = {
            "outputs": [],
            "template": {"existing": {"required": False}, "new_required": {"required": True}},
        }

        assert check_breaking_changes(current_node, latest_component) is True

        # Test safe change (not breaking)
        current_node = {"outputs": [], "template": {"existing": {"required": False}}}
        latest_component = {
            "outputs": [],
            "template": {"existing": {"required": False}, "new_optional": {"required": False}},
        }

        assert check_breaking_changes(current_node, latest_component) is False

    def test_performance_optimization_concept(self):
        """Test that the performance optimization concept is working."""
        # Test that we can detect module metadata in flow nodes
        flow_with_modules = {
            "data": {
                "nodes": [
                    {
                        "id": "node1",
                        "data": {
                            "type": "ChatInput",
                            "node": {
                                "metadata": {
                                    "module": "lfx.components.input_output.chat.ChatInput",
                                    "code_hash": "hash1",
                                }
                            },
                        },
                    }
                ]
            }
        }

        # Extract modules like the real function does
        component_modules = set()
        for node in flow_with_modules["data"]["nodes"]:
            node_data = node.get("data", {})
            node_type = node_data.get("type")
            if node_type and node_type not in {"note", "genericNode", "noteNode"}:
                node_template = node_data.get("node", {})
                node_metadata = node_template.get("metadata", {})
                module_info = node_metadata.get("module")
                if module_info:
                    component_modules.add(module_info)

        # Should find the module
        assert len(component_modules) == 1
        assert "lfx.components.input_output.chat.ChatInput" in component_modules

    @pytest.mark.asyncio
    async def test_check_command_integration(self, outdated_flow_file):
        """Test the full check command integration."""
        if not outdated_flow_file.exists():
            pytest.skip("Outdated flow file not found")

        # This is an integration test that would run the actual command
        # For now, just test that the file exists and is valid JSON
        from anyio import Path as AsyncPath

        async_path = AsyncPath(outdated_flow_file)
        content = await async_path.read_text()
        flow_data = json.loads(content)

        assert "data" in flow_data
        assert "nodes" in flow_data["data"]
        assert len(flow_data["data"]["nodes"]) > 0

        # Check that it has the expected component types
        component_types = set()
        for node in flow_data["data"]["nodes"]:
            node_type = node.get("data", {}).get("type")
            if node_type and node_type not in {"note", "genericNode", "noteNode"}:
                component_types.add(node_type)

        # Should have some actual components
        assert len(component_types) > 0
        assert any(
            comp_type in {"ChatInput", "ChatOutput", "Prompt", "OpenAIModel", "Memory"} for comp_type in component_types
        )


class TestCheckCommandCLI:
    """Test cases for CLI integration."""

    def test_check_command_functions_exist(self):
        """Test that check command functions are available."""
        from lfx.cli.check import check_command

        assert callable(check_command)

    def test_run_command_check_function_exists(self):
        """Test that run command check function exists."""
        from lfx.cli.run import check_components_before_run

        assert callable(check_components_before_run)


class TestInPlaceOption:
    """Test cases for the --in-place option."""

    @pytest.fixture
    def sample_flow_file(self, sample_flow_data):
        """Create a temporary flow file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            json.dump(sample_flow_data, tmp_file, indent=2)
            tmp_path = tmp_file.name

        yield Path(tmp_path)

        # Cleanup
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    @pytest.fixture
    def mock_component_dict(self):
        """Mock component dictionary with updated hash."""
        return {
            "ChatInput": {
                "metadata": {"code_hash": "new_hash_456", "module": "lfx.components.input_output.chat.ChatInput"},
                "template": {
                    "input_value": {"value": "", "required": False},
                    "code": {"value": "new code"},
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

    @pytest.mark.asyncio
    async def test_in_place_requires_update_or_interactive(self, sample_flow_file):
        """Test that --in-place requires --update or --interactive."""
        from lfx.cli.check import check_flow_components

        # Read original content
        original_content = Path(sample_flow_file).read_text()

        # Try to use in_place without update or interactive
        result = await check_flow_components(str(sample_flow_file), update=False, interactive=False, in_place=True)

        # Should not error, but also should not update (just check)
        assert "error" not in result
        assert result.get("applied_updates", 0) == 0

        # File should not be modified
        current_content = Path(sample_flow_file).read_text()
        assert current_content == original_content

    @pytest.mark.asyncio
    async def test_in_place_with_update_modifies_file(self, sample_flow_file, mock_component_dict):
        """Test that --in-place with --update modifies the original file."""
        from lfx.cli.check import check_flow_components

        # Read original content
        original_content = Path(sample_flow_file).read_text()

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Use in_place with update
            result = await check_flow_components(str(sample_flow_file), update=True, in_place=True, force=True)

            # Should have applied updates
            assert "error" not in result
            assert result.get("applied_updates", 0) > 0
            assert result.get("output_path") == str(sample_flow_file)

            # File should be modified
            updated_content = Path(sample_flow_file).read_text()
            updated_data = json.loads(updated_content)

            # The file should have been updated (hash should change)
            assert updated_content != original_content
            # Verify the structure is still valid
            assert "data" in updated_data
            assert "nodes" in updated_data["data"]

    @pytest.mark.asyncio
    async def test_in_place_error_when_no_output_specified(self, sample_flow_file, mock_component_dict):
        """Test that update requires either --output or --in-place."""
        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Try to update without output or in_place
            result = await check_flow_components(str(sample_flow_file), update=True, output=None, in_place=False)

            # Should return error
            assert "error" in result
            assert "must specify either --output" in result["error"] or "must specify either" in result["error"]
            assert "--in-place" in result["error"]

    @pytest.mark.asyncio
    async def test_interactive_error_before_prompts(self, sample_flow_file, mock_component_dict):
        """Test that interactive mode fails early if --output or --in-place is not specified."""
        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Try interactive mode without output or in_place
            result = await check_flow_components(str(sample_flow_file), interactive=True, output=None, in_place=False)

            # Should return error immediately, before any prompts
            assert "error" in result
            assert "must specify either --output" in result["error"] or "must specify either" in result["error"]
            assert "--in-place" in result["error"]
            # Should have 0 applied updates since we failed before prompting
            assert result.get("applied_updates", 0) == 0

    @pytest.mark.asyncio
    async def test_output_takes_precedence_over_in_place(self, sample_flow_file, mock_component_dict):
        """Test that --output takes precedence over --in-place when both are specified."""
        from lfx.cli.check import check_flow_components

        # Create a separate output file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as output_file:
            output_path = output_file.name

        try:
            original_content = Path(sample_flow_file).read_text()

            with patch("lfx.cli.check.load_specific_components") as mock_load:
                mock_load.return_value = mock_component_dict

                # Use both output and in_place (output should take precedence)
                result = await check_flow_components(
                    str(sample_flow_file), update=True, output=output_path, in_place=True, force=True
                )

                # Should have applied updates
                assert "error" not in result
                assert result.get("applied_updates", 0) > 0
                assert result.get("output_path") == output_path

                # Original file should NOT be modified (output took precedence)
                current_content = Path(sample_flow_file).read_text()
                assert current_content == original_content

                # Output file should be modified
                assert Path(output_path).exists()
                output_content = Path(output_path).read_text()
                assert output_content != original_content
        finally:
            # Cleanup output file
            if Path(output_path).exists():
                Path(output_path).unlink()

    @pytest.mark.asyncio
    async def test_in_place_preserves_file_structure(self, sample_flow_file, mock_component_dict):
        """Test that --in-place preserves the overall file structure."""
        from lfx.cli.check import check_flow_components

        original_data = json.loads(Path(sample_flow_file).read_text())
        original_node_count = len(original_data["data"]["nodes"])

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            result = await check_flow_components(str(sample_flow_file), update=True, in_place=True, force=True)

            assert "error" not in result

            # Verify file structure is preserved
            updated_data = json.loads(Path(sample_flow_file).read_text())
            assert "data" in updated_data
            assert "nodes" in updated_data["data"]
            assert len(updated_data["data"]["nodes"]) == original_node_count

    @pytest.mark.asyncio
    async def test_in_place_with_interactive_mode(self, sample_flow_file, mock_component_dict):
        """Test that --in-place works with --interactive mode."""
        from lfx.cli.check import check_flow_components

        with (
            patch("lfx.cli.check.load_specific_components") as mock_load,
            patch("lfx.cli.check.prompt_for_component_update") as mock_prompt,
        ):
            mock_load.return_value = mock_component_dict
            # Simulate user accepting the update
            mock_prompt.return_value = True

            result = await check_flow_components(str(sample_flow_file), interactive=True, in_place=True, force=True)

            # Should have applied updates if user accepted
            assert "error" not in result
            # File may or may not be modified depending on prompts
            # But the structure should be valid
            updated_content = Path(sample_flow_file).read_text()
            updated_data = json.loads(updated_content)
            assert "data" in updated_data


class TestShowDiffOption:
    """Test cases for the --show-diff option."""

    @pytest.fixture
    def sample_flow_file(self, sample_flow_data):
        """Create a temporary flow file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            json.dump(sample_flow_data, tmp_file, indent=2)
            tmp_path = tmp_file.name

        yield Path(tmp_path)

        # Cleanup
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    @pytest.fixture
    def mock_component_dict_with_code_change(self):
        """Mock component dictionary with different code."""
        return {
            "ChatInput": {
                "metadata": {"code_hash": "new_hash_456", "module": "lfx.components.input_output.chat.ChatInput"},
                "template": {
                    "input_value": {"value": "", "required": False},
                    "code": {"value": "def new_code():\n    return 'updated'"},
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

    @pytest.mark.asyncio
    async def test_show_diff_false_does_not_calculate_diff(
        self, sample_flow_file, mock_component_dict_with_code_change
    ):
        """Test that code diff is not calculated when show_diff is False."""
        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict_with_code_change

            result = await check_flow_components(str(sample_flow_file), show_diff=False)

            assert "error" not in result
            outdated_components = result.get("outdated_components", [])
            if outdated_components:
                # Check that code_diff is None when show_diff is False
                for comp in outdated_components:
                    changes = comp.get("changes", {})
                    assert changes.get("code_diff") is None

    @pytest.mark.asyncio
    async def test_show_diff_true_calculates_diff(self, sample_flow_file, mock_component_dict_with_code_change):
        """Test that code diff is calculated when show_diff is True."""
        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict_with_code_change

            result = await check_flow_components(str(sample_flow_file), show_diff=True)

            assert "error" not in result
            outdated_components = result.get("outdated_components", [])
            if outdated_components:
                # Check that code_diff is calculated when show_diff is True
                for comp in outdated_components:
                    changes = comp.get("changes", {})
                    # If code changed, diff should be present
                    if changes.get("code_diff") is not None:
                        diff_data = changes["code_diff"]
                        assert isinstance(diff_data, dict)
                        assert "full_diff" in diff_data or "added_lines" in diff_data or "removed_lines" in diff_data

    @pytest.mark.asyncio
    async def test_show_diff_default_is_false(self, sample_flow_file, mock_component_dict_with_code_change):
        """Test that show_diff defaults to False (no diff calculation)."""
        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict_with_code_change

            # Don't pass show_diff, should default to False
            result = await check_flow_components(str(sample_flow_file))

            assert "error" not in result
            outdated_components = result.get("outdated_components", [])
            if outdated_components:
                # Check that code_diff is None by default
                for comp in outdated_components:
                    changes = comp.get("changes", {})
                    assert changes.get("code_diff") is None

    @pytest.fixture
    def mock_component_dict_same_code(self):
        """Mock component dictionary with same code (no changes)."""
        return {
            "ChatInput": {
                "metadata": {"code_hash": "old_hash_123", "module": "lfx.components.input_output.chat.ChatInput"},
                "template": {
                    "input_value": {"value": "", "required": False},
                    "code": {"value": "old code"},
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

    @pytest.mark.asyncio
    async def test_show_diff_with_no_code_changes(self, sample_flow_file, mock_component_dict_same_code):
        """Test that show_diff doesn't break when there are no code changes."""
        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict_same_code

            result = await check_flow_components(str(sample_flow_file), show_diff=True)

            assert "error" not in result
            # Should not raise any errors even with show_diff=True when no code changes


class TestStdoutOutput:
    """Test cases for the --output - (STDOUT) option."""

    @pytest.fixture
    def sample_flow_file(self, sample_flow_data):
        """Create a temporary flow file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            json.dump(sample_flow_data, tmp_file, indent=2)
            tmp_path = tmp_file.name

        yield Path(tmp_path)

        # Cleanup
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

    @pytest.fixture
    def mock_component_dict(self):
        """Mock component dictionary with updated hash."""
        return {
            "ChatInput": {
                "metadata": {"code_hash": "new_hash_456", "module": "lfx.components.input_output.chat.ChatInput"},
                "template": {
                    "input_value": {"value": "", "required": False},
                    "code": {"value": "new code"},
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

    @pytest.mark.asyncio
    async def test_output_to_stdout(self, sample_flow_file, mock_component_dict):
        """Test that --output - writes to stdout."""
        import sys
        from io import StringIO

        from lfx.cli.check import check_flow_components

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Capture stdout
            old_stdout = sys.stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            try:
                result = await check_flow_components(str(sample_flow_file), update=True, output="-", force=True)

                sys.stdout = old_stdout
                output_content = captured_output.getvalue()

                # Should have applied updates
                assert "error" not in result
                assert result.get("applied_updates", 0) > 0
                assert result.get("output_path") == "-"

                # Should have written JSON to stdout
                assert output_content.strip()
                parsed_output = json.loads(output_content.strip())
                assert "data" in parsed_output
                assert "nodes" in parsed_output["data"]
            finally:
                sys.stdout = old_stdout

    @pytest.mark.asyncio
    async def test_stdout_takes_precedence_over_in_place(self, sample_flow_file, mock_component_dict):
        """Test that --output - takes precedence over --in-place."""
        import sys
        from io import StringIO

        from lfx.cli.check import check_flow_components

        original_content = Path(sample_flow_file).read_text()

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Capture stdout
            old_stdout = sys.stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            try:
                result = await check_flow_components(
                    str(sample_flow_file), update=True, output="-", in_place=True, force=True
                )

                sys.stdout = old_stdout
                output_content = captured_output.getvalue()

                # Should have applied updates
                assert "error" not in result
                assert result.get("applied_updates", 0) > 0
                assert result.get("output_path") == "-"

                # Original file should NOT be modified (stdout took precedence)
                current_content = Path(sample_flow_file).read_text()
                assert current_content == original_content

                # Should have written JSON to stdout
                assert output_content.strip()
                parsed_output = json.loads(output_content.strip())
                assert "data" in parsed_output
            finally:
                sys.stdout = old_stdout

    @pytest.mark.asyncio
    async def test_stdout_with_interactive_requires_output(self, sample_flow_file, mock_component_dict):
        """Test that interactive mode accepts --output - as valid."""
        import sys
        from io import StringIO

        from lfx.cli.check import check_flow_components

        with (
            patch("lfx.cli.check.load_specific_components") as mock_load,
            patch("lfx.cli.check.prompt_for_component_update") as mock_prompt,
        ):
            mock_load.return_value = mock_component_dict
            mock_prompt.return_value = True  # User accepts updates

            # Capture stdout
            old_stdout = sys.stdout
            captured_output = StringIO()
            sys.stdout = captured_output

            try:
                # Should not error when using --output - with interactive
                result = await check_flow_components(str(sample_flow_file), interactive=True, output="-", force=True)

                sys.stdout = old_stdout
                output_content = captured_output.getvalue()

                # Should not have error about missing output
                assert "error" not in result or "must specify either" not in result.get("error", "")
                # If updates were applied, should have written to stdout
                if result.get("applied_updates", 0) > 0:
                    assert output_content.strip()
            finally:
                sys.stdout = old_stdout


class TestBackupOption:
    """Test cases for the --backup option."""

    @pytest.fixture
    def sample_flow_file(self, sample_flow_data):
        """Create a temporary flow file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            json.dump(sample_flow_data, tmp_file, indent=2)
            tmp_path = tmp_file.name

        yield Path(tmp_path)

        # Cleanup
        if Path(tmp_path).exists():
            Path(tmp_path).unlink()
        # Also cleanup backup file if it exists
        backup_path = Path(f"{tmp_path}.bak")
        if backup_path.exists():
            backup_path.unlink()

    @pytest.fixture
    def mock_component_dict(self):
        """Mock component dictionary with updated hash."""
        return {
            "ChatInput": {
                "metadata": {"code_hash": "new_hash_456", "module": "lfx.components.input_output.chat.ChatInput"},
                "template": {
                    "input_value": {"value": "", "required": False},
                    "code": {"value": "new code"},
                },
                "outputs": [{"name": "message", "types": ["Message"]}],
            }
        }

    @pytest.mark.asyncio
    async def test_backup_created_by_default_with_in_place(self, sample_flow_file, mock_component_dict):
        """Test that backup is created by default when using --in-place."""
        from lfx.cli.check import check_flow_components

        # Read original content
        original_content = Path(sample_flow_file).read_text()
        backup_path = Path(f"{sample_flow_file}.bak")

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Use in_place with update (backup defaults to True)
            result = await check_flow_components(
                str(sample_flow_file), update=True, in_place=True, force=True, backup=True
            )

            # Should have applied updates
            assert "error" not in result
            assert result.get("applied_updates", 0) > 0
            assert result.get("output_path") == str(sample_flow_file)
            assert result.get("backup_path") == str(backup_path)

            # Backup file should exist
            assert backup_path.exists()

            # Backup should contain original content
            backup_content = backup_path.read_text()
            assert backup_content == original_content

            # Original file should be modified
            updated_content = Path(sample_flow_file).read_text()
            assert updated_content != original_content

    @pytest.mark.asyncio
    async def test_backup_not_created_with_no_backup(self, sample_flow_file, mock_component_dict):
        """Test that backup is not created when --no-backup is used."""
        from lfx.cli.check import check_flow_components

        backup_path = Path(f"{sample_flow_file}.bak")

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Use in_place with update and no_backup
            result = await check_flow_components(
                str(sample_flow_file), update=True, in_place=True, force=True, backup=False
            )

            # Should have applied updates
            assert "error" not in result
            assert result.get("applied_updates", 0) > 0

            # Backup file should NOT exist
            assert not backup_path.exists()

            # Result should not have backup_path
            assert "backup_path" not in result

    @pytest.mark.asyncio
    async def test_backup_only_with_in_place(self, sample_flow_file, mock_component_dict):
        """Test that backup option only works with --in-place."""
        from lfx.cli.check import check_flow_components

        backup_path = Path(f"{sample_flow_file}.bak")
        output_file = Path(str(sample_flow_file) + ".new")

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Use backup with output (not in_place) - should not create backup
            result = await check_flow_components(
                str(sample_flow_file), update=True, output=str(output_file), backup=True
            )

            # Should have applied updates
            assert "error" not in result
            assert result.get("applied_updates", 0) > 0

            # Backup file should NOT exist (backup only works with in_place)
            assert not backup_path.exists()

            # Cleanup output file
            if output_file.exists():
                output_file.unlink()

    @pytest.mark.asyncio
    async def test_backup_contains_exact_original_content(self, sample_flow_file, mock_component_dict):
        """Test that backup file contains the exact original file content."""
        from lfx.cli.check import check_flow_components

        # Read original content
        original_content = Path(sample_flow_file).read_text()
        backup_path = Path(f"{sample_flow_file}.bak")

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = mock_component_dict

            # Use in_place with update and backup
            result = await check_flow_components(
                str(sample_flow_file), update=True, in_place=True, force=True, backup=True
            )

            # Should have applied updates
            assert "error" not in result
            assert result.get("applied_updates", 0) > 0
            assert result.get("backup_path") == str(backup_path)

            # Backup should exist
            assert backup_path.exists()

            # Backup content should match original exactly
            backup_content = backup_path.read_text()
            assert backup_content == original_content

            # Verify backup is valid JSON
            backup_data = json.loads(backup_content)
            assert "data" in backup_data

    @pytest.mark.asyncio
    async def test_backup_works_with_interactive(self, sample_flow_file, mock_component_dict):
        """Test that backup works with interactive mode."""
        from lfx.cli.check import check_flow_components

        original_content = Path(sample_flow_file).read_text()
        backup_path = Path(f"{sample_flow_file}.bak")

        with (
            patch("lfx.cli.check.load_specific_components") as mock_load,
            patch("lfx.cli.check.prompt_for_component_update") as mock_prompt,
        ):
            mock_load.return_value = mock_component_dict
            mock_prompt.return_value = True  # User accepts updates

            # Use interactive with in_place and backup
            result = await check_flow_components(
                str(sample_flow_file), interactive=True, in_place=True, backup=True, force=True
            )

            # Should have applied updates
            assert "error" not in result
            assert result.get("applied_updates", 0) > 0

            # Backup should exist
            assert backup_path.exists()

            # Backup should contain original content
            backup_content = backup_path.read_text()
            assert backup_content == original_content


class TestApplyComponentUpdate:
    """Test cases for the apply_component_update function."""

    @pytest.mark.asyncio
    async def test_apply_component_update_preserves_user_values(self):
        """Test that user-configured values are preserved after component update."""
        from lfx.cli.check import apply_component_update

        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "test-node-1",
                        "data": {
                            "type": "ChatInput",
                            "node": {
                                "template": {
                                    "input_value": {"value": "user_configured_value"},
                                    "sender_name": {"value": "CustomName"},
                                }
                            },
                        },
                    }
                ]
            }
        }
        component = {"component_type": "ChatInput", "node_id": "test-node-1"}
        all_types_dict = {
            "ChatInput": {
                "template": {
                    "input_value": {"value": ""},
                    "sender_name": {"value": "default"},
                    "new_field": {"value": "new_default"},
                }
            }
        }

        result = await apply_component_update(flow_data, component, all_types_dict)

        assert result is True
        updated_node = flow_data["data"]["nodes"][0]["data"]["node"]
        # User values should be preserved
        assert updated_node["template"]["input_value"]["value"] == "user_configured_value"
        assert updated_node["template"]["sender_name"]["value"] == "CustomName"
        # New fields should have defaults
        assert "new_field" in updated_node["template"]

    @pytest.mark.asyncio
    async def test_apply_component_update_returns_false_when_component_not_found(self):
        """Test that apply_component_update returns False when component type not found."""
        from lfx.cli.check import apply_component_update

        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "test-node-1",
                        "data": {
                            "type": "ChatInput",
                            "node": {"template": {"input_value": {"value": "test"}}},
                        },
                    }
                ]
            }
        }
        component = {"component_type": "NonExistentComponent", "node_id": "test-node-1"}
        all_types_dict = {}  # Empty - component not found

        result = await apply_component_update(flow_data, component, all_types_dict)

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_component_update_returns_false_when_node_not_found(self):
        """Test that apply_component_update returns False when node ID not found."""
        from lfx.cli.check import apply_component_update

        flow_data = {"data": {"nodes": []}}  # No nodes
        component = {"component_type": "ChatInput", "node_id": "nonexistent-node"}
        all_types_dict = {"ChatInput": {"template": {}}}

        result = await apply_component_update(flow_data, component, all_types_dict)

        assert result is False

    @pytest.mark.asyncio
    async def test_apply_component_update_flat_flow_format(self):
        """Test apply_component_update with flat flow format (no 'data' wrapper)."""
        from lfx.cli.check import apply_component_update

        # Flat format - nodes directly in flow_data
        flow_data = {
            "nodes": [
                {
                    "id": "test-node-1",
                    "data": {
                        "type": "ChatInput",
                        "node": {"template": {"input_value": {"value": "original"}}},
                    },
                }
            ]
        }
        component = {"component_type": "ChatInput", "node_id": "test-node-1"}
        all_types_dict = {"ChatInput": {"template": {"input_value": {"value": ""}, "new_field": {"value": "new"}}}}

        result = await apply_component_update(flow_data, component, all_types_dict)

        assert result is True
        updated_node = flow_data["nodes"][0]["data"]["node"]
        assert updated_node["template"]["input_value"]["value"] == "original"
        assert "new_field" in updated_node["template"]


class TestCheckComponentsBeforeRun:
    """Test cases for the check_components_before_run function."""

    @pytest.mark.asyncio
    async def test_check_components_before_run_raises_on_outdated(self, tmp_path):
        """Test that check_components_before_run raises ValueError when outdated components found."""
        from lfx.cli.run import check_components_before_run

        # Create a sample flow file
        flow_file = tmp_path / "test_flow.json"
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "type": "ChatInput",
                            "node": {
                                "metadata": {"code_hash": "old_hash"},
                                "template": {"code": {"value": "old code"}},
                            },
                        },
                    }
                ]
            }
        }
        flow_file.write_text(json.dumps(flow_data))

        def verbose_print(msg):
            pass

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = {
                "ChatInput": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                }
            }

            with pytest.raises(ValueError, match=r"(?i)outdated"):
                await check_components_before_run(flow_file, verbose_print)

    @pytest.mark.asyncio
    async def test_check_components_before_run_success_when_up_to_date(self, tmp_path):
        """Test that check_components_before_run succeeds when components are up to date."""
        from lfx.cli.run import check_components_before_run

        # Create a sample flow file with module in metadata (required for load_specific_components)
        flow_file = tmp_path / "test_flow.json"
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "type": "ChatInput",
                            "node": {
                                "metadata": {
                                    "code_hash": "same_hash",
                                    "module": "lfx.components.inputs.ChatInput",
                                },
                                "template": {"code": {"value": "same code"}},
                            },
                        },
                    }
                ]
            }
        }
        flow_file.write_text(json.dumps(flow_data))

        def verbose_print(msg):
            pass

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = {
                "ChatInput": {
                    "metadata": {"code_hash": "same_hash"},
                    "template": {"code": {"value": "same code"}},
                    "outputs": [],
                }
            }

            # Should not raise
            await check_components_before_run(flow_file, verbose_print)

    @pytest.mark.asyncio
    async def test_check_components_before_run_raises_on_error(self, tmp_path):
        """Test that check_components_before_run raises ValueError when check fails."""
        from lfx.cli.run import check_components_before_run

        # Non-existent file
        flow_file = tmp_path / "nonexistent.json"

        def verbose_print(msg):
            pass

        with pytest.raises(ValueError, match=r"(?i)component check failed|error"):
            await check_components_before_run(flow_file, verbose_print)

    @pytest.mark.asyncio
    async def test_check_components_before_run_shows_breaking_change(self, tmp_path):
        """Test that breaking changes are indicated in the error message."""
        from lfx.cli.run import check_components_before_run

        flow_file = tmp_path / "test_flow.json"
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "type": "ChatInput",
                            "node": {
                                "display_name": "Chat Input",
                                "metadata": {"code_hash": "old_hash"},
                                "template": {"code": {"value": "old code"}, "removed_field": {"value": "x"}},
                                "outputs": [{"name": "message", "types": ["Message"]}],
                            },
                        },
                    }
                ]
            }
        }
        flow_file.write_text(json.dumps(flow_data))

        def verbose_print(msg):
            pass

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = {
                "ChatInput": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},  # removed_field is gone
                    "outputs": [{"name": "message", "types": ["Message"]}],
                }
            }

            with pytest.raises(ValueError, match=r"\(breaking\)"):
                await check_components_before_run(flow_file, verbose_print)


class TestBreakingChangeOutputTypeNarrowing:
    """Test cases for output type narrowing detection."""

    def test_breaking_change_output_type_narrowed(self):
        """Test that narrowing output types is detected as breaking."""
        from lfx.cli.check import check_breaking_changes

        current_node = {
            "outputs": [{"name": "output", "types": ["Message", "Text"]}],
            "template": {},
        }
        latest_component = {
            "outputs": [{"name": "output", "types": ["Message"]}],  # Text removed
            "template": {},
        }

        assert check_breaking_changes(current_node, latest_component) is True

    def test_not_breaking_when_output_types_expanded(self):
        """Test that expanding output types is not breaking."""
        from lfx.cli.check import check_breaking_changes

        current_node = {
            "outputs": [{"name": "output", "types": ["Message"]}],
            "template": {},
        }
        latest_component = {
            "outputs": [{"name": "output", "types": ["Message", "Text"]}],  # Text added
            "template": {},
        }

        assert check_breaking_changes(current_node, latest_component) is False

    def test_not_breaking_when_output_types_same(self):
        """Test that same output types is not breaking."""
        from lfx.cli.check import check_breaking_changes

        current_node = {
            "outputs": [{"name": "output", "types": ["Message", "Text"]}],
            "template": {},
        }
        latest_component = {
            "outputs": [{"name": "output", "types": ["Message", "Text"]}],
            "template": {},
        }

        assert check_breaking_changes(current_node, latest_component) is False


class TestFlatFlowFormat:
    """Test cases for flat flow format (no 'data' wrapper)."""

    @pytest.mark.asyncio
    async def test_check_flow_components_flat_format(self, tmp_path):
        """Test check_flow_components with flat flow format."""
        from lfx.cli.check import check_flow_components

        # Create a flat format flow file
        flow_file = tmp_path / "flat_flow.json"
        flow_data = {
            "nodes": [
                {
                    "id": "node-1",
                    "data": {
                        "type": "ChatInput",
                        "node": {
                            "metadata": {"code_hash": "old_hash"},
                            "template": {"code": {"value": "old code"}},
                        },
                    },
                }
            ]
        }
        flow_file.write_text(json.dumps(flow_data))

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = {
                "ChatInput": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                }
            }

            result = await check_flow_components(str(flow_file))

            assert "error" not in result
            assert result["total_nodes"] == 1
            assert result["outdated_count"] == 1

    @pytest.mark.asyncio
    async def test_check_flow_components_nested_format(self, tmp_path):
        """Test check_flow_components with nested flow format (data wrapper)."""
        from lfx.cli.check import check_flow_components

        # Create a nested format flow file
        flow_file = tmp_path / "nested_flow.json"
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node-1",
                        "data": {
                            "type": "ChatInput",
                            "node": {
                                "metadata": {"code_hash": "old_hash"},
                                "template": {"code": {"value": "old code"}},
                            },
                        },
                    }
                ]
            }
        }
        flow_file.write_text(json.dumps(flow_data))

        with patch("lfx.cli.check.load_specific_components") as mock_load:
            mock_load.return_value = {
                "ChatInput": {
                    "metadata": {"code_hash": "new_hash"},
                    "template": {"code": {"value": "new code"}},
                    "outputs": [],
                }
            }

            result = await check_flow_components(str(flow_file))

            assert "error" not in result
            assert result["total_nodes"] == 1
            assert result["outdated_count"] == 1
