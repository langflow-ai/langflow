"""Template search and loading utilities for Langflow."""

import json
from pathlib import Path
from typing import Any

import orjson
from lfx.log.logger import logger


def list_templates(
    query: str | None = None,
    fields: list[str] | None = None,
    tags: list[str] | None = None,
    starter_projects_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Search and load template data with configurable field selection.

    Args:
        query: Optional search term to filter templates by name or description.
                     Case-insensitive substring matching.
        fields: List of fields to include in the results. If None, returns all available fields.
               Common fields: id, name, description, tags, is_component, last_tested_version,
               endpoint_name, data, icon, icon_bg_color, gradient, updated_at
        tags: Optional list of tags to filter templates. Returns templates that have ANY of these tags.
        starter_projects_path: Optional path to starter_projects directory.
                              If None, uses default location relative to initial_setup.

    Returns:
        List of dictionaries containing the selected fields for each matching template.

    Example:
        >>> # Get only id, name, and description
        >>> templates = list_templates(fields=["id", "name", "description"])

        >>> # Search for "agent" templates with specific fields
        >>> templates = list_templates(
        ...     search_query="agent",
        ...     fields=["id", "name", "description", "tags"]
        ... )

        >>> # Get templates by tag
        >>> templates = list_templates(
        ...     tags=["chatbots", "rag"],
        ...     fields=["name", "description"]
        ... )
    """
    # Get the starter_projects directory
    if starter_projects_path:
        starter_projects_dir = Path(starter_projects_path)
    else:
        # Navigate from agentic/utils back to initial_setup/starter_projects
        starter_projects_dir = Path(__file__).parent.parent.parent / "initial_setup" / "starter_projects"

    if not starter_projects_dir.exists():
        msg = f"Starter projects directory not found: {starter_projects_dir}"
        raise FileNotFoundError(msg)

    results = []

    # Iterate through all JSON files in the directory
    for template_file in starter_projects_dir.glob("*.json"):
        try:
            # Load the template
            with Path(template_file).open(encoding="utf-8") as f:
                template_data = json.load(f)

            # Apply search filter if provided
            if query:
                name = template_data.get("name", "").lower()
                description = template_data.get("description", "").lower()
                query_lower = query.lower()

                if query_lower not in name and query_lower not in description:
                    continue

            # Apply tag filter if provided
            if tags:
                template_tags = template_data.get("tags", [])
                if not template_tags:
                    continue
                # Check if any of the provided tags match
                if not any(tag in template_tags for tag in tags):
                    continue

            # Extract only the requested fields
            if fields:
                filtered_data = {field: template_data.get(field) for field in fields if field in template_data}
            else:
                # Return all fields if none specified
                filtered_data = template_data

            results.append(filtered_data)

        except (json.JSONDecodeError, orjson.JSONDecodeError) as e:
            # Log and skip invalid JSON files
            logger.warning(f"Failed to parse {template_file}: {e}")
            continue

    return results


def get_template_by_id(
    template_id: str,
    fields: list[str] | None = None,
    starter_projects_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Get a specific template by its ID.

    Args:
        template_id: The UUID string of the template to retrieve.
        fields: Optional list of fields to include. If None, returns all fields.
        starter_projects_path: Optional path to starter_projects directory.

    Returns:
        Dictionary containing the template data with selected fields, or None if not found.

    Example:
        >>> template = get_template_by_id(
        ...     "0dbee653-41ae-4e51-af2e-55757fb24be3",
        ...     fields=["name", "description"]
        ... )
    """
    if starter_projects_path:
        starter_projects_dir = Path(starter_projects_path)
    else:
        starter_projects_dir = Path(__file__).parent.parent.parent / "initial_setup" / "starter_projects"

    for template_file in starter_projects_dir.glob("*.json"):
        try:
            with Path(template_file).open(encoding="utf-8") as f:
                template_data = json.load(f)

            if template_data.get("id") == template_id:
                if fields:
                    return {field: template_data.get(field) for field in fields if field in template_data}
                return template_data

        except (json.JSONDecodeError, orjson.JSONDecodeError):
            continue

    return None


def get_all_tags(starter_projects_path: str | Path | None = None) -> list[str]:
    """Get a list of all unique tags used across all templates.

    Args:
        starter_projects_path: Optional path to starter_projects directory.

    Returns:
        Sorted list of unique tag names.

    Example:
        >>> tags = get_all_tags()
        >>> print(tags)
        ['agents', 'chatbots', 'rag', 'tools', ...]
    """
    if starter_projects_path:
        starter_projects_dir = Path(starter_projects_path)
    else:
        starter_projects_dir = Path(__file__).parent.parent.parent / "initial_setup" / "starter_projects"
    all_tags = set()

    for template_file in starter_projects_dir.glob("*.json"):
        try:
            template_data = orjson.loads(Path(template_file).read_text(encoding="utf-8"))

            tags = template_data.get("tags", [])
            all_tags.update(tags)

        except (json.JSONDecodeError, orjson.JSONDecodeError) as e:
            logger.aexception(f"Error loading template {template_file}: {e}")
            continue

    return sorted(all_tags)


def get_templates_count(starter_projects_path: str | Path | None = None) -> int:
    """Get the total count of available templates.

    Args:
        starter_projects_path: Optional path to starter_projects directory.

    Returns:
        Number of JSON template files found.
    """
    if starter_projects_path:
        starter_projects_dir = Path(starter_projects_path)
    else:
        starter_projects_dir = Path(__file__).parent.parent.parent / "initial_setup" / "starter_projects"
    return len(list(starter_projects_dir.glob("*.json")))
