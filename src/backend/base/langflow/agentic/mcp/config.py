"""Configuration for Langflow Agentic MCP Server.

This module defines which functions from the agentic folder should be exposed
as MCP tools and how they should be configured.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolConfig:
    """Configuration for an MCP tool.

    Attributes:
        enabled: Whether the tool should be exposed in the MCP server
        name: Optional custom name for the tool (defaults to function name)
        description: Optional custom description (defaults to function docstring)
        parameters_schema: Optional custom JSON schema for parameters
    """

    enabled: bool = True
    name: str | None = None
    description: str | None = None
    parameters_schema: dict[str, Any] | None = None


# Configuration for which functions to expose as MCP tools
# Key: module path (e.g., "utils.template_search")
# Value: Dictionary mapping function names to their ToolConfig
TOOL_CONFIGS: dict[str, dict[str, ToolConfig]] = {
    # Template search utilities
    "utils.template_search": {
        "list_templates": ToolConfig(
            enabled=True,
            name="list_templates",
            description="Search and list Langflow templates with optional filtering by query and tags",
        ),
        "get_template_by_id": ToolConfig(
            enabled=True,
            name="get_template_by_id",
            description="Get a specific Langflow template by its unique ID",
        ),
        "get_all_tags": ToolConfig(
            enabled=True,
            name="get_all_tags",
            description="Get all unique tags available across Langflow templates",
        ),
        "get_templates_count": ToolConfig(
            enabled=True,
            name="get_templates_count",
            description="Get the total count of available Langflow templates",
        ),
    },
    # Add more modules here as they are developed
    # Example:
    # "core.orchestrator": {
    #     "execute_workflow": ToolConfig(enabled=True),
    #     "internal_helper": ToolConfig(enabled=False),  # Skip this function
    # },
}


def is_tool_enabled(module_path: str, function_name: str) -> bool:
    """Check if a tool should be enabled in the MCP server.

    Args:
        module_path: The module path (e.g., "utils.template_search")
        function_name: The function name (e.g., "list_templates")

    Returns:
        True if the tool should be enabled, False otherwise
    """
    if module_path not in TOOL_CONFIGS:
        return False

    if function_name not in TOOL_CONFIGS[module_path]:
        return False

    return TOOL_CONFIGS[module_path][function_name].enabled


def get_tool_config(module_path: str, function_name: str) -> ToolConfig | None:
    """Get the configuration for a specific tool.

    Args:
        module_path: The module path (e.g., "utils.template_search")
        function_name: The function name (e.g., "list_templates")

    Returns:
        ToolConfig if found, None otherwise
    """
    if module_path not in TOOL_CONFIGS:
        return None

    return TOOL_CONFIGS[module_path].get(function_name)


# Global MCP server configuration
SERVER_NAME = "langflow-agentic"
SERVER_VERSION = "1.0.0"
SERVER_DESCRIPTION = "MCP server for Langflow Agentic features providing template search and workflow automation"
