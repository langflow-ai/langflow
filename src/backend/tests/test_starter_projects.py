"""Test suite for starter project JSON files.

Verifies that starter project JSON files are properly structured and that:
- noteNode types have width/height at the root level
- Other node types have width/height removed from root level
"""

import json
from pathlib import Path

import pytest

STARTER_PROJECTS_DIR = Path(__file__).parent.parent / "base" / "langflow" / "initial_setup" / "starter_projects"


def get_starter_project_files() -> list[Path]:
    """Get all starter project JSON files."""
    if not STARTER_PROJECTS_DIR.exists():
        msg = f"Starter projects directory not found: {STARTER_PROJECTS_DIR}"
        raise FileNotFoundError(msg) from None

    json_files = sorted(STARTER_PROJECTS_DIR.glob("*.json"))
    if not json_files:
        msg = f"No JSON files found in {STARTER_PROJECTS_DIR}"
        raise FileNotFoundError(msg) from None

    return json_files


def load_json_file(json_file: Path) -> dict:
    """Load and parse a JSON file."""
    try:
        with json_file.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {json_file.name}: {e}"
        raise ValueError(msg) from e
    except Exception as e:
        msg = f"Error reading {json_file.name}: {e}"
        raise OSError(msg) from e


@pytest.mark.parametrize("json_file", get_starter_project_files(), ids=lambda f: f.name)
class TestStarterProjects:
    """Test suite for all starter project JSON files."""

    def test_json_validity(self, json_file: Path):
        """Test that JSON file is valid and can be parsed."""
        data = load_json_file(json_file)
        assert isinstance(data, dict), f"{json_file.name} should be a valid JSON object"

    def test_width_height_at_node_level(self, json_file: Path):
        """Test that width/height are removed from node root level for all node types EXCEPT noteNode.

        noteNode type SHOULD have width/height at root level.
        Other node types should NOT have width/height at root level.
        """
        data = load_json_file(json_file)
        nodes = data["data"]["nodes"]

        issues = []

        for node_idx, node in enumerate(nodes):
            node_type = node.get("type", "unknown")
            node_id = node.get("id", "UNKNOWN")

            # noteNode SHOULD have width/height at root level - skip checking these
            if node_type == "noteNode":
                continue

            # For non-noteNode types, width/height should NOT exist at node level
            if "width" in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"'width' found at node root level (value: {node['width']}) - "
                    f"should be removed for non-noteNode types"
                )

            if "height" in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"'height' found at node root level (value: {node['height']}) - "
                    f"should be removed for non-noteNode types"
                )

        assert not issues, f"{json_file.name}: Width/height issues found:\n" + "\n".join(issues)

    def test_note_node_structure(self, json_file: Path):
        """Test that noteNode types have proper structure with required fields.

        Validates that:
        - noteNode has 'data' field
        - 'data' contains 'node' field
        - 'node' contains 'template' field
        - 'template' contains 'backgroundColor' field
        """
        data = load_json_file(json_file)
        nodes = data["data"]["nodes"]

        issues = []
        note_nodes_found = False

        for node_idx, node in enumerate(nodes):
            node_type = node.get("type", "unknown")
            node_id = node.get("id", "UNKNOWN")

            if node_type != "noteNode":
                continue

            note_nodes_found = True

            # Check for 'data' field
            if "data" not in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"missing 'data' field"
                )
                continue

            # Check for 'node' field in data
            if "node" not in node["data"]:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"missing 'node' field in 'data'"
                )
                continue

            # Check for 'template' field in node
            if "template" not in node["data"]["node"]:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"missing 'template' field in 'node'"
                )
                continue

            # Check for 'backgroundColor' field in template
            template = node["data"]["node"]["template"]
            if "backgroundColor" not in template:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}, type: {node_type}): "
                    f"missing 'backgroundColor' field in template"
                )

        # Only assert if we found note nodes
        if note_nodes_found:
            assert not issues, f"{json_file.name}: Note node structure issues found:\n" + "\n".join(issues)

    def test_note_node_background_color_values(self, json_file: Path):
        """Test that noteNode backgroundColor values are valid.

        Validates that backgroundColor is one of the allowed values:
        - A valid color name string (e.g., 'neutral', 'emerald', 'blue', etc.)
        - Not empty or null
        """
        data = load_json_file(json_file)
        nodes = data["data"]["nodes"]

        # Define valid background color values
        # Based on common Tailwind/design system color names
        valid_colors = {
            "neutral", "gray", "slate", "zinc", "stone",
            "red", "orange", "amber", "yellow", "lime", "green",
            "emerald", "teal", "cyan", "sky", "blue", "indigo",
            "violet", "purple", "fuchsia", "pink", "rose"
        }

        issues = []
        note_nodes_found = False

        for node_idx, node in enumerate(nodes):
            node_type = node.get("type", "unknown")
            node_id = node.get("id", "UNKNOWN")

            if node_type != "noteNode":
                continue

            note_nodes_found = True

            # Navigate to backgroundColor
            try:
                template = node["data"]["node"]["template"]
                bg_color = template.get("backgroundColor")

                # Check if backgroundColor exists and has a valid value
                if bg_color is None:
                    issues.append(
                        f"Node {node_idx} (ID: {node_id}): "
                        f"backgroundColor is None"
                    )
                elif isinstance(bg_color, str):
                    if not bg_color:
                        issues.append(
                            f"Node {node_idx} (ID: {node_id}): "
                            f"backgroundColor is empty string"
                        )
                    elif bg_color not in valid_colors:
                        issues.append(
                            f"Node {node_idx} (ID: {node_id}): "
                            f"backgroundColor '{bg_color}' is not a recognized color name. "
                            f"Expected one of: {', '.join(sorted(valid_colors))}"
                        )
                else:
                    issues.append(
                        f"Node {node_idx} (ID: {node_id}): "
                        f"backgroundColor has invalid type {type(bg_color).__name__}, expected string"
                    )
            except (KeyError, TypeError) as e:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}): "
                    f"error accessing backgroundColor: {e}"
                )

        # Only assert if we found note nodes
        if note_nodes_found:
            assert not issues, f"{json_file.name}: Background color issues found:\n" + "\n".join(issues)

    def test_specific_projects_have_neutral_background(self, json_file: Path):
        """Test that specific starter projects use 'neutral' backgroundColor.

        This test validates the specific change made in this PR where the following
        projects were updated from 'emerald' to 'neutral':
        - Invoice Summarizer.json
        - Market Research.json
        - Research Agent.json
        """
        # Define projects that should have neutral background
        projects_requiring_neutral = {
            "Invoice Summarizer.json",
            "Market Research.json",
            "Research Agent.json"
        }

        # Only check files that are in the list
        if json_file.name not in projects_requiring_neutral:
            pytest.skip(f"{json_file.name} is not required to have neutral background")

        data = load_json_file(json_file)
        nodes = data["data"]["nodes"]

        issues = []
        note_node_found = False

        for node_idx, node in enumerate(nodes):
            node_type = node.get("type", "unknown")
            node_id = node.get("id", "UNKNOWN")

            if node_type != "noteNode":
                continue

            note_node_found = True

            try:
                template = node["data"]["node"]["template"]
                bg_color = template.get("backgroundColor")

                if bg_color != "neutral":
                    issues.append(
                        f"Node {node_idx} (ID: {node_id}): "
                        f"backgroundColor is '{bg_color}', expected 'neutral' for {json_file.name}"
                    )
            except (KeyError, TypeError) as e:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}): "
                    f"error accessing backgroundColor: {e}"
                )

        assert note_node_found, f"{json_file.name}: No noteNode found, but expected one with neutral background"
        assert not issues, f"{json_file.name}: Background color validation failed:\n" + "\n".join(issues)

    def test_note_nodes_have_required_dimensions(self, json_file: Path):
        """Test that noteNode types have width and height at root level.

        This is the inverse of test_width_height_at_node_level - noteNodes SHOULD
        have width and height, and they should be positive numbers.
        """
        data = load_json_file(json_file)
        nodes = data["data"]["nodes"]

        issues = []
        note_nodes_found = False

        for node_idx, node in enumerate(nodes):
            node_type = node.get("type", "unknown")
            node_id = node.get("id", "UNKNOWN")

            if node_type != "noteNode":
                continue

            note_nodes_found = True

            # Check for width
            if "width" not in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}): "
                    f"noteNode missing 'width' at root level"
                )
            elif not isinstance(node["width"], (int, float)) or node["width"] <= 0:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}): "
                    f"noteNode 'width' should be a positive number, got {node['width']}"
                )

            # Check for height
            if "height" not in node:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}): "
                    f"noteNode missing 'height' at root level"
                )
            elif not isinstance(node["height"], (int, float)) or node["height"] <= 0:
                issues.append(
                    f"Node {node_idx} (ID: {node_id}): "
                    f"noteNode 'height' should be a positive number, got {node['height']}"
                )

        # Only assert if we found note nodes
        if note_nodes_found:
            assert not issues, f"{json_file.name}: Note node dimension issues found:\n" + "\n".join(issues)

    def test_data_structure_consistency(self, json_file: Path):
        """Test that starter project has consistent data structure.

        Validates:
        - Root has 'data' key
        - 'data' has 'nodes' and 'edges' keys
        - 'nodes' is a list
        - 'edges' is a list
        - Each node has required fields: id, type, data
        """
        data = load_json_file(json_file)

        issues = []

        # Check root structure
        if "data" not in data:
            issues.append("Missing 'data' key at root level")
            # Cannot continue without data
            assert not issues, f"{json_file.name}: Structure issues found:\n" + "\n".join(issues)
            return

        project_data = data["data"]

        # Check for nodes
        if "nodes" not in project_data:
            issues.append("Missing 'nodes' key in data")
        elif not isinstance(project_data["nodes"], list):
            issues.append(f"'nodes' should be a list, got {type(project_data['nodes']).__name__}")

        # Check for edges
        if "edges" not in project_data:
            issues.append("Missing 'edges' key in data")
        elif not isinstance(project_data["edges"], list):
            issues.append(f"'edges' should be a list, got {type(project_data['edges']).__name__}")

        # Validate each node has required fields
        if "nodes" in project_data and isinstance(project_data["nodes"], list):
            for node_idx, node in enumerate(project_data["nodes"]):
                if not isinstance(node, dict):
                    issues.append(f"Node {node_idx} is not a dictionary")
                    continue

                if "id" not in node:
                    issues.append(f"Node {node_idx} missing 'id' field")

                if "type" not in node:
                    issues.append(f"Node {node_idx} missing 'type' field")

                if "data" not in node:
                    issues.append(f"Node {node_idx} missing 'data' field")

        assert not issues, f"{json_file.name}: Structure issues found:\n" + "\n".join(issues)