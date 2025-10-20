"""FastMCP server for Langflow Agentic tools.

This module exposes template search functions as MCP tools using FastMCP decorators.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from langflow.agentic.utils.template_search import (
    get_all_tags,
    get_template_by_id,
    get_templates_count,
    list_templates,
)

# Initialize FastMCP server
mcp = FastMCP("langflow-agentic")


@mcp.tool()
def search_templates(
    query: str | None = None,
    fields: list[str] | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search and load template data with configurable field selection.

    Args:
        query: Optional search term to filter templates by name or description.
               Case-insensitive substring matching.
        fields: List of fields to include in the results. If None, returns default fields:
               ["id", "name", "description", "tags", "endpoint_name", "icon"]
               Common fields: id, name, description, tags, is_component, last_tested_version,
               endpoint_name, data, icon, icon_bg_color, gradient, updated_at
        tags: Optional list of tags to filter templates. Returns templates that have ANY of these tags.

    Returns:
        List of dictionaries containing the selected fields for each matching template.

    Example:
        >>> # Get default fields for all templates
        >>> templates = search_templates()

        >>> # Get only specific fields
        >>> templates = search_templates(fields=["id", "name", "description"])

        >>> # Search for "agent" templates with specific fields
        >>> templates = search_templates(
        ...     query="agent",
        ...     fields=["id", "name", "description", "tags"]
        ... )

        >>> # Get templates by tag
        >>> templates = search_templates(
        ...     tags=["chatbots", "rag"],
        ...     fields=["name", "description"]
        ... )
    """
    # Set default fields if not provided
    if fields is None:
        fields = ["id", "name", "description", "tags", "endpoint_name", "icon"]
    return list_templates(query=query, fields=fields, tags=tags)


@mcp.tool()
def get_template(
    template_id: str,
    fields: list[str] | None = None,
) -> dict[str, Any] | None:
    """Get a specific template by its ID.

    Args:
        template_id: The UUID string of the template to retrieve.
        fields: Optional list of fields to include. If None, returns all fields.

    Returns:
        Dictionary containing the template data with selected fields, or None if not found.

    Example:
        >>> template = get_template(
        ...     template_id="0dbee653-41ae-4e51-af2e-55757fb24be3",
        ...     fields=["name", "description"]
        ... )
    """
    return get_template_by_id(template_id=template_id, fields=fields)


@mcp.tool()
def list_all_tags() -> list[str]:
    """Get a list of all unique tags used across all templates.

    Returns:
        Sorted list of unique tag names.

    Example:
        >>> tags = list_all_tags()
        >>> print(tags)
        ['agents', 'chatbots', 'rag', 'tools', ...]
    """
    return get_all_tags()


@mcp.tool()
def count_templates() -> int:
    """Get the total count of available templates.

    Returns:
        Number of JSON template files found.

    Example:
        >>> count = count_templates()
        >>> print(f"Found {count} templates")
    """
    return get_templates_count()


# Entry point for running the server
if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run()
