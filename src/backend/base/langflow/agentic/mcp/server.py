"""FastMCP server for Langflow Agentic tools.

This module exposes template search and creation functions as MCP tools using FastMCP decorators.
"""

from typing import Any
from uuid import UUID

from langflow.agentic.mcp.support import replace_none_and_null_with_empty_str
from mcp.server.fastmcp import FastMCP

from langflow.agentic.utils.component_search import (
    get_all_component_types,
    get_component_by_name,
    get_components_by_type,
    get_components_count,
    list_all_components,
)
from langflow.agentic.utils.flow_graph import (
    get_flow_ascii_graph,
    get_flow_graph_representations,
    get_flow_graph_summary,
    get_flow_text_repr,
)
from langflow.agentic.utils.template_create import (
    create_flow_from_template_and_get_link,
)
from langflow.agentic.utils.template_search import (
    get_all_tags,
    get_template_by_id,
    get_templates_count,
    list_templates,
)
from langflow.services.deps import get_settings_service, session_scope

# Initialize FastMCP server
mcp = FastMCP("langflow-agentic")


@mcp.tool()
def search_templates(
    query: str | None = None,
    fields: list[str]= ["id", "name", "description", "tags", "endpoint_name", "icon"]
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
    return list_templates(query=query, fields=fields)



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


# Flow creation from template
@mcp.tool()
async def create_flow_from_template(
    template_id: str,
    user_id: str,
    folder_id: str | None = None,
) -> dict[str, Any]:
    """Create a new flow from a starter template and return its id and UI link.

    Args:
        template_id: ID field inside the starter template JSON file.
        user_id: UUID string of the owner user.
        folder_id: Optional target folder UUID; default folder is used if omitted.

    Returns:
        Dict with keys: {"id": str, "link": str}
    """
    async with session_scope() as session:
        return await create_flow_from_template_and_get_link(
            session=session,
            user_id=UUID(user_id),
            template_id=template_id,
            target_folder_id=UUID(folder_id) if folder_id else None,
        )


# Component search and retrieval tools
@mcp.tool()
async def search_components(
    query: str | None = None,
    component_type: str | None = None,
    fields: list[str] | None = None,
    add_search_text: bool = True,
) -> list[dict[str, Any]]:
    """Search and retrieve component data with configurable field selection.

    Args:
        query: Optional search term to filter components by name or description.
               Case-insensitive substring matching.
        component_type: Optional component type to filter by (e.g., "agents", "embeddings", "llms").
        fields: List of fields to include in the results. If None, returns default fields:
               ["name", "type", "display_name", "description"]
               All fields: name, display_name, description, type, template, documentation,
               icon, is_input, is_output, lazy_loaded, field_order

    Returns:
        List of dictionaries containing the selected fields for each matching component.

    Example:
        >>> # Get all components with default fields
        >>> components = search_components()

        >>> # Search for "openai" components
        >>> components = search_components(
        ...     query="openai",
        ...     fields=["name", "description", "type"]
        ... )

        >>> # Get all LLM components
        >>> components = search_components(
        ...     component_type="llms",
        ...     fields=["name", "display_name"]
        ... )
    """
    # Set default fields if not provided
    if fields is None:
        fields = ["name", "type", "display_name", "description"]

    settings_service = get_settings_service()
    result = await list_all_components(
        query=query,
        component_type=component_type,
        fields=fields,
        settings_service=settings_service,
    ) 
    # For each component dict in result, add a 'text' key with all key-value pairs joined by newline.

    if add_search_text:
        for comp in result:
            text_lines = [f"{k} {v}" for k, v in comp.items() if k != "text"]
            comp["text"] = "\n".join(text_lines)
    return replace_none_and_null_with_empty_str(result,required_fields=fields)

@mcp.tool()
async def get_component(
    component_name: str,
    component_type: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any] | None:
    """Get a specific component by its name.

    Args:
        component_name: The name of the component to retrieve.
        component_type: Optional component type to narrow search (e.g., "llms", "agents").
        fields: Optional list of fields to include. If None, returns all fields.

    Returns:
        Dictionary containing the component data with selected fields, or None if not found.

    Example:
        >>> component = get_component(
        ...     component_name="OpenAIModel",
        ...     fields=["display_name", "description", "template"]
        ... )
    """
    settings_service = get_settings_service()
    return await get_component_by_name(
        component_name=component_name,
        component_type=component_type,
        fields=fields,
        settings_service=settings_service,
    )


@mcp.tool()
async def list_component_types() -> list[str]:
    """Get a list of all available component types.

    Returns:
        Sorted list of component type names.

    Example:
        >>> types = list_component_types()
        >>> print(types)
        ['agents', 'data', 'embeddings', 'llms', 'memories', 'tools', ...]
    """
    settings_service = get_settings_service()
    return await get_all_component_types(settings_service=settings_service)


@mcp.tool()
async def count_components(component_type: str | None = None) -> int:
    """Get the total count of available components.

    Args:
        component_type: Optional component type to count only that type.

    Returns:
        Number of components found.

    Example:
        >>> count = count_components()
        >>> print(f"Found {count} total components")

        >>> llm_count = count_components(component_type="llms")
        >>> print(f"Found {llm_count} LLM components")
    """
    settings_service = get_settings_service()
    return await get_components_count(component_type=component_type, settings_service=settings_service)


@mcp.tool()
async def get_components_by_type_tool(
    component_type: str,
    fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Get all components of a specific type.

    Args:
        component_type: The component type to retrieve (e.g., "llms", "agents", "embeddings").
        fields: Optional list of fields to include. If None, returns default fields.

    Returns:
        List of components of the specified type.

    Example:
        >>> llms = get_components_by_type_tool(
        ...     component_type="llms",
        ...     fields=["name", "display_name", "description"]
        ... )
    """
    # Set default fields if not provided
    if fields is None:
        fields = ["name", "type", "display_name", "description"]

    settings_service = get_settings_service()
    return await get_components_by_type(
        component_type=component_type,
        fields=fields,
        settings_service=settings_service,
    )


# Flow graph visualization tools
@mcp.tool()
async def visualize_flow_graph(
    flow_id_or_name: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Get both ASCII and text representations of a flow graph.

    This tool provides comprehensive visualization of a flow's graph structure,
    including an ASCII art diagram and a detailed text representation of all
    vertices and edges.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name to visualize.
        user_id: Optional user ID to filter flows (UUID string).

    Returns:
        Dictionary containing:
        - flow_id: The flow ID
        - flow_name: The flow name
        - ascii_graph: ASCII art representation of the graph
        - text_repr: Text representation with vertices and edges
        - vertex_count: Number of vertices in the graph
        - edge_count: Number of edges in the graph
        - error: Error message if any (only present if operation fails)

    Example:
        >>> result = visualize_flow_graph("my-flow-id")
        >>> print(result["ascii_graph"])
        >>> print(result["text_repr"])
        >>> print(f"Graph has {result['vertex_count']} vertices")
    """
    return await get_flow_graph_representations(flow_id_or_name, user_id)


@mcp.tool()
async def get_flow_ascii_diagram(
    flow_id_or_name: str,
    user_id: str | None = None,
) -> str:
    """Get ASCII art diagram of a flow graph.

    Returns a visual ASCII representation of the flow's graph structure,
    showing how components are connected.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows (UUID string).

    Returns:
        ASCII art string representation of the graph, or error message.

    Example:
        >>> ascii_art = get_flow_ascii_diagram("my-flow-id")
        >>> print(ascii_art)
    """
    return await get_flow_ascii_graph(flow_id_or_name, user_id)


@mcp.tool()
async def get_flow_text_representation(
    flow_id_or_name: str,
    user_id: str | None = None,
) -> str:
    """Get text representation of a flow graph.

    Returns a structured text representation showing all vertices (components)
    and edges (connections) in the flow.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows (UUID string).

    Returns:
        Text representation string with vertices and edges, or error message.

    Example:
        >>> text = get_flow_text_representation("my-flow-id")
        >>> print(text)
        Graph Representation:
        ----------------------
        Vertices (3):
          ChatInput, OpenAIModel, ChatOutput

        Edges (2):
          ChatInput --> OpenAIModel
          OpenAIModel --> ChatOutput
    """
    return await get_flow_text_repr(flow_id_or_name, user_id)


@mcp.tool()
async def get_flow_structure_summary(
    flow_id_or_name: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Get a summary of flow graph structure and metadata.

    Returns flow metadata including vertex and edge lists without the
    full visual representations. Useful for quickly understanding the
    flow structure.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        user_id: Optional user ID to filter flows (UUID string).

    Returns:
        Dictionary with flow metadata:
        - flow_id: The flow ID
        - flow_name: The flow name
        - vertex_count: Number of vertices
        - edge_count: Number of edges
        - vertices: List of vertex IDs (component names)
        - edges: List of edge tuples (source_id, target_id)

    Example:
        >>> summary = get_flow_structure_summary("my-flow-id")
        >>> print(f"Flow '{summary['flow_name']}' has {summary['vertex_count']} components")
        >>> print(f"Components: {', '.join(summary['vertices'])}")
    """
    return await get_flow_graph_summary(flow_id_or_name, user_id)


# Entry point for running the server
if __name__ == "__main__":
    # Run the FastMCP server
    mcp.run()
