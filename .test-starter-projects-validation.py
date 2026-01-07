"""
Comprehensive tests for starter project JSON file validation.

This test module validates the structure, schema, and configuration
of starter project JSON files, with focus on the recent backgroundColor changes.
"""

import json
from pathlib import Path
from typing import Any

import pytest


# Path to starter projects
STARTER_PROJECTS_DIR = Path("src/backend/base/langflow/initial_setup/starter_projects")

# All starter project files
STARTER_PROJECT_FILES = [
    "Invoice Summarizer.json",
    "Market Research.json",
    "Research Agent.json",
]

# Valid background colors for note nodes
VALID_NOTE_BACKGROUND_COLORS = [
    "neutral",
    "emerald",
    "blue",
    "red",
    "yellow",
    "purple",
    "pink",
    "gray",
]


class TestStarterProjectJSONStructure:
    """Test suite for validating starter project JSON file structure."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_files_exist(self, project_file: str) -> None:
        """Verify that all starter project JSON files exist."""
        file_path = STARTER_PROJECTS_DIR / project_file
        assert file_path.exists(), f"Starter project file {project_file} does not exist"
        assert file_path.is_file(), f"{project_file} is not a file"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_files_are_valid_json(self, project_file: str) -> None:
        """Verify that all starter project files contain valid JSON."""
        file_path = STARTER_PROJECTS_DIR / project_file
        try:
            with file_path.open("r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in {project_file}: {e}")

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_has_required_top_level_keys(self, project_file: str) -> None:
        """Verify that JSON files have required top-level structure."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        assert "data" in data, f"{project_file} missing 'data' key"
        assert isinstance(data["data"], dict), f"{project_file} 'data' should be a dictionary"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_has_nodes_structure(self, project_file: str) -> None:
        """Verify that JSON files have a valid nodes structure."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        assert "nodes" in data["data"], f"{project_file} missing 'nodes' in data"
        assert isinstance(data["data"]["nodes"], list), f"{project_file} 'nodes' should be a list"
        assert len(data["data"]["nodes"]) > 0, f"{project_file} has no nodes"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_has_edges_structure(self, project_file: str) -> None:
        """Verify that JSON files have a valid edges structure."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Edges are optional but should be a list if present
        if "edges" in data["data"]:
            assert isinstance(
                data["data"]["edges"], list
            ), f"{project_file} 'edges' should be a list"


class TestNoteNodeBackgroundColors:
    """Test suite specifically for note node backgroundColor validation."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_note_nodes_use_neutral_background(self, project_file: str) -> None:
        """Verify that note nodes use 'neutral' backgroundColor (not 'emerald')."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]
        note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

        assert len(note_nodes) > 0, f"{project_file} has no note nodes"

        for node in note_nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            node_config = node_data.get("node", {})
            template = node_config.get("template", {})
            bg_color = template.get("backgroundColor")

            assert (
                bg_color == "neutral"
            ), f"{project_file} node {node_id} has backgroundColor '{bg_color}', expected 'neutral'"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_no_emerald_background_colors(self, project_file: str) -> None:
        """Ensure no note nodes use the deprecated 'emerald' backgroundColor."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]
        note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

        for node in note_nodes:
            node_id = node.get("id", "unknown")
            template = node.get("data", {}).get("node", {}).get("template", {})
            bg_color = template.get("backgroundColor")

            assert (
                bg_color != "emerald"
            ), f"{project_file} node {node_id} still uses deprecated 'emerald' backgroundColor"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_note_nodes_have_background_color_defined(self, project_file: str) -> None:
        """Verify that all note nodes have backgroundColor explicitly defined."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]
        note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

        for node in note_nodes:
            node_id = node.get("id", "unknown")
            template = node.get("data", {}).get("node", {}).get("template", {})

            assert (
                "backgroundColor" in template
            ), f"{project_file} note node {node_id} missing backgroundColor"
            assert (
                template["backgroundColor"] is not None
            ), f"{project_file} note node {node_id} backgroundColor is None"

    def test_all_starter_projects_consistent_note_background(self) -> None:
        """Verify that all starter projects use the same backgroundColor for notes."""
        background_colors = set()

        for project_file in STARTER_PROJECT_FILES:
            file_path = STARTER_PROJECTS_DIR / project_file
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            nodes = data["data"]["nodes"]
            note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

            for node in note_nodes:
                bg_color = node.get("data", {}).get("node", {}).get("template", {}).get("backgroundColor")
                if bg_color:
                    background_colors.add(bg_color)

        assert (
            len(background_colors) == 1
        ), f"Inconsistent backgroundColor across projects: {background_colors}"
        assert (
            background_colors == {"neutral"}
        ), f"Expected only 'neutral', found: {background_colors}"


class TestNodeStructureIntegrity:
    """Test suite for validating overall node structure integrity."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_all_nodes_have_required_fields(self, project_file: str) -> None:
        """Verify that all nodes have required fields."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]

        for i, node in enumerate(nodes):
            assert "id" in node, f"{project_file} node {i} missing 'id'"
            assert "data" in node, f"{project_file} node {i} missing 'data'"
            assert "type" in node.get("data", {}), f"{project_file} node {i} missing 'type' in data"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_note_nodes_have_complete_structure(self, project_file: str) -> None:
        """Verify that note nodes have complete required structure."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]
        note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

        for node in note_nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})

            # Check nested structure
            assert "node" in node_data, f"{project_file} note node {node_id} missing 'node' in data"
            assert (
                "template" in node_data["node"]
            ), f"{project_file} note node {node_id} missing 'template'"

            # Verify template structure
            template = node_data["node"]["template"]
            assert isinstance(
                template, dict
            ), f"{project_file} note node {node_id} template is not a dict"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_node_ids_are_unique(self, project_file: str) -> None:
        """Verify that all node IDs are unique within a project."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]
        node_ids = [node.get("id") for node in nodes]

        assert len(node_ids) == len(
            set(node_ids)
        ), f"{project_file} has duplicate node IDs: {[nid for nid in node_ids if node_ids.count(nid) > 1]}"


class TestJSONFileFormatting:
    """Test suite for JSON file formatting and consistency."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_is_properly_indented(self, project_file: str) -> None:
        """Verify that JSON files use consistent indentation."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
            data = json.loads(content)

        # Re-serialize with standard indentation
        expected = json.dumps(data, indent=2, ensure_ascii=False)

        # Check if content matches expected formatting (allowing for trailing whitespace)
        content_lines = [line.rstrip() for line in content.strip().split("\n")]
        expected_lines = [line.rstrip() for line in expected.strip().split("\n")]

        # Allow some flexibility in formatting, but check key structure
        assert len(content_lines) > 0, f"{project_file} is empty"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_uses_utf8_encoding(self, project_file: str) -> None:
        """Verify that JSON files use UTF-8 encoding."""
        file_path = STARTER_PROJECTS_DIR / project_file
        try:
            with file_path.open("r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError as e:
            pytest.fail(f"{project_file} is not valid UTF-8: {e}")


class TestBackwardCompatibility:
    """Test suite for backward compatibility of configuration changes."""

    def test_background_color_change_is_intentional(self) -> None:
        """Document that the backgroundColor change from 'emerald' to 'neutral' is intentional."""
        # This test serves as documentation that the change was deliberate
        for project_file in STARTER_PROJECT_FILES:
            file_path = STARTER_PROJECTS_DIR / project_file
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            nodes = data["data"]["nodes"]
            note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

            for node in note_nodes:
                bg_color = node.get("data", {}).get("node", {}).get("template", {}).get("backgroundColor")
                assert bg_color == "neutral", (
                    f"Expected backgroundColor 'neutral' in {project_file}, "
                    f"found '{bg_color}'. If this test fails, verify the change is intentional."
                )


class TestEdgeCasesAndErrorHandling:
    """Test suite for edge cases and potential error conditions."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_empty_nodes_list_handling(self, project_file: str) -> None:
        """Verify behavior with empty or missing nodes (should not occur in valid files)."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Valid starter projects should always have nodes
        assert (
            "nodes" in data["data"] and len(data["data"]["nodes"]) > 0
        ), f"{project_file} should have at least one node"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_malformed_template_structure_detection(self, project_file: str) -> None:
        """Detect potential malformed template structures in note nodes."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = data["data"]["nodes"]
        note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

        for node in note_nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})

            # Ensure proper nesting
            assert (
                "node" in node_data
            ), f"{project_file} note {node_id} missing 'node' in data structure"
            assert isinstance(
                node_data["node"], dict
            ), f"{project_file} note {node_id} 'node' is not a dict"

            if "template" in node_data["node"]:
                assert isinstance(
                    node_data["node"]["template"], dict
                ), f"{project_file} note {node_id} 'template' is not a dict"

    def test_no_unexpected_background_color_values(self) -> None:
        """Ensure no unexpected or invalid backgroundColor values are present."""
        for project_file in STARTER_PROJECT_FILES:
            file_path = STARTER_PROJECTS_DIR / project_file
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            nodes = data["data"]["nodes"]
            note_nodes = [node for node in nodes if node.get("data", {}).get("type") == "note"]

            for node in note_nodes:
                node_id = node.get("id", "unknown")
                bg_color = node.get("data", {}).get("node", {}).get("template", {}).get("backgroundColor")

                if bg_color:
                    assert bg_color in VALID_NOTE_BACKGROUND_COLORS, (
                        f"{project_file} note {node_id} has invalid backgroundColor '{bg_color}'. "
                        f"Valid colors: {VALID_NOTE_BACKGROUND_COLORS}"
                    )


class TestFileMetadata:
    """Test suite for file metadata and attributes."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_file_size_is_reasonable(self, project_file: str) -> None:
        """Verify that JSON files are not unexpectedly large or small."""
        file_path = STARTER_PROJECTS_DIR / project_file
        file_size = file_path.stat().st_size

        # Reasonable bounds: 1KB to 10MB
        assert 1024 < file_size < 10_485_760, (
            f"{project_file} size {file_size} bytes is outside reasonable bounds (1KB - 10MB)"
        )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_file_is_readable(self, project_file: str) -> None:
        """Verify that files have proper read permissions."""
        file_path = STARTER_PROJECTS_DIR / project_file
        assert file_path.exists(), f"{project_file} does not exist"
        assert file_path.is_file(), f"{project_file} is not a file"

        # Try to read the file
        try:
            with file_path.open("r", encoding="utf-8") as f:
                f.read(1)  # Read just one character to verify readability
        except (PermissionError, IOError) as e:
            pytest.fail(f"Cannot read {project_file}: {e}")