"""Test that starter projects do not contain hash_history in their JSON files.

This test ensures that internal component metadata (hash_history) used for tracking
component evolution in the component index does not leak into saved flow templates.
"""

import json
from pathlib import Path

import pytest


def find_hash_history_in_dict(data, path=""):
    """Recursively search for hash_history keys in nested dictionaries.

    Args:
        data: Dictionary or list to search
        path: Current path in the data structure (for error reporting)

    Returns:
        List of paths where hash_history was found
    """
    found_paths = []

    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            if key == "hash_history":
                found_paths.append(current_path)

            # Recursively search nested structures
            found_paths.extend(find_hash_history_in_dict(value, current_path))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f"{path}[{i}]"
            found_paths.extend(find_hash_history_in_dict(item, current_path))

    return found_paths


def get_starter_project_files():
    """Get all starter project JSON files."""
    starter_projects_dir = (
        Path(__file__).parent.parent.parent / "base" / "langflow" / "initial_setup" / "starter_projects"
    )

    if not starter_projects_dir.exists():
        pytest.skip(f"Starter projects directory not found: {starter_projects_dir}")

    json_files = list(starter_projects_dir.glob("*.json"))

    if not json_files:
        pytest.skip(f"No JSON files found in {starter_projects_dir}")

    return json_files


@pytest.mark.parametrize("project_file", get_starter_project_files())
def test_starter_project_has_no_hash_history(project_file):
    """Test that a starter project file does not contain hash_history.

    Hash_history is internal metadata for tracking component code evolution
    and should only exist in component_index.json, never in saved flows.
    """
    with project_file.open(encoding="utf-8") as f:
        project_data = json.load(f)

    # Search for any hash_history keys in the entire project structure
    hash_history_paths = find_hash_history_in_dict(project_data)

    assert not hash_history_paths, (
        f"Found hash_history in {project_file.name} at paths: {hash_history_paths}\n"
        "hash_history is internal component metadata and should not be in saved flows. "
        "It should only exist in component_index.json for tracking component evolution."
    )


def test_all_starter_projects_loaded():
    """Sanity check that we're actually testing starter projects."""
    project_files = get_starter_project_files()

    # We should have multiple starter projects
    assert len(project_files) > 0, "No starter project files found to test"

    # Print count for visibility
