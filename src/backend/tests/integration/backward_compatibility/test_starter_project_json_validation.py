"""Comprehensive tests for starter project JSON files.

This module provides thorough validation of the starter project JSON files,
including structure validation, color scheme validation, and integrity checks.
"""

import json
from pathlib import Path
from typing import Any

import pytest


STARTER_PROJECTS_DIR = Path(__file__).parents[4] / "backend" / "base" / "langflow" / "initial_setup" / "starter_projects"

STARTER_PROJECT_FILES = [
    "Invoice Summarizer.json",
    "Market Research.json",
    "Research Agent.json",
]

# Valid color values based on the codebase color scheme
VALID_BACKGROUND_COLORS = {"neutral", "emerald", "blue", "red", "yellow", "purple", "pink", "gray"}


class TestStarterProjectJSONStructure:
    """Test suite for validating the structure of starter project JSON files."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_file_exists(self, project_file: str):
        """Verify that each starter project JSON file exists."""
        file_path = STARTER_PROJECTS_DIR / project_file
        assert file_path.exists(), f"Starter project file {project_file} does not exist"
        assert file_path.is_file(), f"{project_file} is not a file"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_is_valid(self, project_file: str):
        """Verify that each JSON file contains valid JSON."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            try:
                data = json.load(f)
                assert data is not None, f"{project_file} parsed to None"
                assert isinstance(data, dict), f"{project_file} should contain a JSON object (dict)"
            except json.JSONDecodeError as e:
                pytest.fail(f"{project_file} contains invalid JSON: {e}")

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_has_required_top_level_keys(self, project_file: str):
        """Verify that each JSON file has the expected top-level structure."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        # Based on Langflow's flow structure
        required_keys = ["data", "description", "name"]
        for key in required_keys:
            assert key in data, f"{project_file} missing required key: {key}"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_name_matches_filename(self, project_file: str):
        """Verify that the 'name' field matches the filename."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        expected_name = project_file.replace(".json", "")
        actual_name = data.get("name", "")
        assert actual_name == expected_name, (
            f"{project_file}: name field '{actual_name}' does not match filename '{expected_name}'"
        )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_has_valid_data_structure(self, project_file: str):
        """Verify that the 'data' field has valid structure."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        assert "data" in data, f"{project_file} missing 'data' key"
        data_obj = data["data"]
        assert isinstance(data_obj, dict), f"{project_file}: 'data' should be a dict"
        
        # Langflow data structure should have nodes and edges
        assert "nodes" in data_obj, f"{project_file}: 'data' missing 'nodes'"
        assert "edges" in data_obj, f"{project_file}: 'data' missing 'edges'"
        assert isinstance(data_obj["nodes"], list), f"{project_file}: 'nodes' should be a list"
        assert isinstance(data_obj["edges"], list), f"{project_file}: 'edges' should be a list"


class TestStarterProjectBackgroundColors:
    """Test suite for validating background color values in starter projects."""

    def _find_background_colors(self, obj: Any, path: str = "") -> list[tuple[str, str]]:
        """Recursively find all backgroundColor values in a nested structure."""
        results = []
        if isinstance(obj, dict):
            if "backgroundColor" in obj:
                results.append((path or "root", obj["backgroundColor"]))
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                results.extend(self._find_background_colors(value, new_path))
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_path = f"{path}[{idx}]"
                results.extend(self._find_background_colors(item, new_path))
        return results

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_all_background_colors_are_valid(self, project_file: str):
        """Verify that all backgroundColor values use valid color names."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        bg_colors = self._find_background_colors(data)
        assert len(bg_colors) > 0, f"{project_file} should contain at least one backgroundColor"
        
        invalid_colors = [
            (path, color) for path, color in bg_colors 
            if color not in VALID_BACKGROUND_COLORS
        ]
        
        assert not invalid_colors, (
            f"{project_file} contains invalid background colors:\n"
            + "\n".join(f"  {path}: {color}" for path, color in invalid_colors)
        )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_background_color_is_neutral(self, project_file: str):
        """Verify that backgroundColor is set to 'neutral' (not 'emerald')."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        bg_colors = self._find_background_colors(data)
        
        # Check that all background colors are 'neutral', not 'emerald'
        emerald_colors = [(path, color) for path, color in bg_colors if color == "emerald"]
        assert not emerald_colors, (
            f"{project_file} still contains 'emerald' backgroundColor:\n"
            + "\n".join(f"  {path}: {color}" for path, color in emerald_colors)
            + "\n  Expected: 'neutral'"
        )
        
        # Verify at least one 'neutral' color exists
        neutral_colors = [(path, color) for path, color in bg_colors if color == "neutral"]
        assert len(neutral_colors) > 0, f"{project_file} should contain at least one 'neutral' backgroundColor"

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_no_emerald_color_anywhere(self, project_file: str):
        """Ensure 'emerald' color has been completely replaced in the file."""
        file_path = STARTER_PROJECTS_DIR / project_file
        content = file_path.read_text()
        
        # Check that 'emerald' doesn't appear in backgroundColor contexts
        assert '"backgroundColor": "emerald"' not in content, (
            f"{project_file} still contains '\"backgroundColor\": \"emerald\"'"
        )


class TestStarterProjectNodeIntegrity:
    """Test suite for validating node integrity in starter projects."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_all_nodes_have_required_fields(self, project_file: str):
        """Verify that all nodes have required fields."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        nodes = data["data"]["nodes"]
        assert len(nodes) > 0, f"{project_file} should have at least one node"
        
        required_node_fields = ["id", "type", "data"]
        for idx, node in enumerate(nodes):
            for field in required_node_fields:
                assert field in node, (
                    f"{project_file}: node[{idx}] missing required field '{field}'"
                )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_node_ids_are_unique(self, project_file: str):
        """Verify that all node IDs are unique within a project."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        nodes = data["data"]["nodes"]
        node_ids = [node["id"] for node in nodes]
        
        duplicate_ids = [node_id for node_id in node_ids if node_ids.count(node_id) > 1]
        unique_duplicates = list(set(duplicate_ids))
        
        assert not unique_duplicates, (
            f"{project_file} contains duplicate node IDs: {unique_duplicates}"
        )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_note_nodes_have_background_color(self, project_file: str):
        """Verify that note-type nodes have backgroundColor defined."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        nodes = data["data"]["nodes"]
        note_nodes = [node for node in nodes if node.get("type") == "note"]
        
        if not note_nodes:
            pytest.skip(f"{project_file} has no note nodes")
        
        for idx, note_node in enumerate(note_nodes):
            node_data = note_node.get("data", {})
            template = node_data.get("template", {})
            
            assert "backgroundColor" in template, (
                f"{project_file}: note node at index {idx} (id: {note_node.get('id')}) "
                f"missing backgroundColor in template"
            )


class TestStarterProjectEdgeIntegrity:
    """Test suite for validating edge integrity in starter projects."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_all_edges_have_required_fields(self, project_file: str):
        """Verify that all edges have required fields."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        edges = data["data"]["edges"]
        
        if not edges:
            pytest.skip(f"{project_file} has no edges")
        
        required_edge_fields = ["source", "target", "id"]
        for idx, edge in enumerate(edges):
            for field in required_edge_fields:
                assert field in edge, (
                    f"{project_file}: edge[{idx}] missing required field '{field}'"
                )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_edge_references_valid_nodes(self, project_file: str):
        """Verify that all edges reference existing node IDs."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        nodes = data["data"]["nodes"]
        edges = data["data"]["edges"]
        
        if not edges:
            pytest.skip(f"{project_file} has no edges")
        
        valid_node_ids = {node["id"] for node in nodes}
        
        invalid_edges = []
        for idx, edge in enumerate(edges):
            source = edge.get("source")
            target = edge.get("target")
            
            if source not in valid_node_ids:
                invalid_edges.append(f"edge[{idx}] source '{source}' not found in nodes")
            if target not in valid_node_ids:
                invalid_edges.append(f"edge[{idx}] target '{target}' not found in nodes")
        
        assert not invalid_edges, (
            f"{project_file} has edges with invalid node references:\n"
            + "\n".join(f"  {err}" for err in invalid_edges)
        )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_edge_ids_are_unique(self, project_file: str):
        """Verify that all edge IDs are unique within a project."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        edges = data["data"]["edges"]
        
        if not edges:
            pytest.skip(f"{project_file} has no edges")
        
        edge_ids = [edge["id"] for edge in edges]
        duplicate_ids = [edge_id for edge_id in edge_ids if edge_ids.count(edge_id) > 1]
        unique_duplicates = list(set(duplicate_ids))
        
        assert not unique_duplicates, (
            f"{project_file} contains duplicate edge IDs: {unique_duplicates}"
        )


class TestStarterProjectJSONFormatting:
    """Test suite for validating JSON formatting and consistency."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_is_properly_formatted(self, project_file: str):
        """Verify that JSON files are properly formatted (can be re-serialized)."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            original_content = f.read()
            f.seek(0)
            data = json.load(f)
        
        # Re-serialize and ensure it's valid
        try:
            reserialized = json.dumps(data, indent=2)
            json.loads(reserialized)  # Should not raise
        except (json.JSONDecodeError, TypeError) as e:
            pytest.fail(f"{project_file} cannot be properly re-serialized: {e}")

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_json_has_reasonable_size(self, project_file: str):
        """Verify that JSON files are not unreasonably large."""
        file_path = STARTER_PROJECTS_DIR / project_file
        file_size = file_path.stat().st_size
        
        # Reasonable upper limit: 10MB
        max_size = 10 * 1024 * 1024
        assert file_size < max_size, (
            f"{project_file} is too large: {file_size} bytes (max: {max_size} bytes)"
        )
        
        # Reasonable lower limit: should have at least some content
        min_size = 100
        assert file_size > min_size, (
            f"{project_file} is too small: {file_size} bytes (min: {min_size} bytes)"
        )


class TestStarterProjectDescription:
    """Test suite for validating project descriptions."""

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_has_non_empty_description(self, project_file: str):
        """Verify that each project has a meaningful description."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        description = data.get("description", "")
        assert description, f"{project_file} has an empty description"
        assert len(description.strip()) > 10, (
            f"{project_file} description is too short: '{description}'"
        )

    @pytest.mark.parametrize("project_file", STARTER_PROJECT_FILES)
    def test_description_is_string(self, project_file: str):
        """Verify that description field is a string."""
        file_path = STARTER_PROJECTS_DIR / project_file
        with open(file_path) as f:
            data = json.load(f)
        
        description = data.get("description")
        assert isinstance(description, str), (
            f"{project_file} description should be a string, got {type(description)}"
        )


class TestStarterProjectsConsistency:
    """Test suite for validating consistency across all starter projects."""

    def test_all_expected_projects_exist(self):
        """Verify that all expected starter project files exist."""
        for project_file in STARTER_PROJECT_FILES:
            file_path = STARTER_PROJECTS_DIR / project_file
            assert file_path.exists(), f"Expected starter project {project_file} does not exist"

    def test_projects_use_consistent_color_scheme(self):
        """Verify that all projects use the same color scheme (neutral)."""
        colors_by_project = {}
        
        for project_file in STARTER_PROJECT_FILES:
            file_path = STARTER_PROJECTS_DIR / project_file
            with open(file_path) as f:
                data = json.load(f)
            
            def find_colors(obj):
                colors = set()
                if isinstance(obj, dict):
                    if "backgroundColor" in obj:
                        colors.add(obj["backgroundColor"])
                    for value in obj.values():
                        colors.update(find_colors(value))
                elif isinstance(obj, list):
                    for item in obj:
                        colors.update(find_colors(item))
                return colors
            
            colors_by_project[project_file] = find_colors(data)
        
        # All projects should use 'neutral', not 'emerald'
        for project_file, colors in colors_by_project.items():
            assert "emerald" not in colors, (
                f"{project_file} still uses 'emerald' color"
            )
            assert "neutral" in colors or not colors, (
                f"{project_file} should use 'neutral' color"
            )

    def test_all_projects_have_valid_structure(self):
        """Verify that all projects follow the same structural pattern."""
        structures = {}
        
        for project_file in STARTER_PROJECT_FILES:
            file_path = STARTER_PROJECTS_DIR / project_file
            with open(file_path) as f:
                data = json.load(f)
            
            structure = {
                "top_keys": sorted(data.keys()),
                "data_keys": sorted(data.get("data", {}).keys()) if "data" in data else [],
                "has_nodes": "nodes" in data.get("data", {}),
                "has_edges": "edges" in data.get("data", {}),
            }
            structures[project_file] = structure
        
        # All structures should be consistent
        first_structure = structures[STARTER_PROJECT_FILES[0]]
        for project_file, structure in structures.items():
            assert structure["top_keys"] == first_structure["top_keys"], (
                f"{project_file} has different top-level keys than {STARTER_PROJECT_FILES[0]}"
            )
            assert structure["has_nodes"], f"{project_file} missing nodes"
            assert structure["has_edges"], f"{project_file} missing edges"