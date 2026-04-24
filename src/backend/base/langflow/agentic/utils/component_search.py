"""Component search and metadata utilities for Langflow."""

from typing import Any

from lfx.interface.components import get_and_cache_all_types_dict
from lfx.log.logger import logger
from lfx.services.settings.service import SettingsService


async def list_all_components(
    query: str | None = None,
    component_type: str | None = None,
    fields: list[str] | None = None,
    settings_service: SettingsService | None = None,
) -> list[dict[str, Any]]:
    """Search and retrieve component data with configurable field selection.

    Args:
        query: Optional search term to filter components by name or description.
               Case-insensitive substring matching.
        component_type: Optional component type to filter by (e.g., "agents", "embeddings", "llms").
        fields: List of fields to include in the results. If None, returns all available fields.
               Common fields: name, display_name, description, type, template, documentation,
               icon, is_input, is_output, lazy_loaded, field_order
        settings_service: Settings service instance for loading components.

    Returns:
        List of dictionaries containing the selected fields for each matching component.

    Example:
        >>> # Get all components with default fields
        >>> components = await list_all_components()

        >>> # Get only name and description
        >>> components = await list_all_components(fields=["name", "description"])

        >>> # Search for "openai" components
        >>> components = await list_all_components(
        ...     query="openai",
        ...     fields=["name", "description", "type"]
        ... )

        >>> # Get all LLM components
        >>> components = await list_all_components(
        ...     component_type="llms",
        ...     fields=["name", "display_name"]
        ... )
    """
    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    try:
        # Get all components from cache
        all_types_dict = await get_and_cache_all_types_dict(settings_service)
        results = []

        # Iterate through component types
        for comp_type, components in all_types_dict.items():
            # Filter by component_type if specified
            if component_type and comp_type.lower() != component_type.lower():
                continue

            # Iterate through components in this type
            for component_name, component_data in components.items():
                # Apply search filter if provided
                if query:
                    name = component_name.lower()
                    display_name = component_data.get("display_name", "").lower()
                    description = component_data.get("description", "").lower()
                    query_lower = query.lower()

                    if query_lower not in name and query_lower not in display_name and query_lower not in description:
                        continue

                # Build result dict with component metadata
                result = {
                    "name": component_name,
                    "type": comp_type,
                }

                # Add all component data fields
                if fields:
                    # Extract only requested fields
                    for field in fields:
                        if field == "name":
                            continue  # Already added
                        if field == "type":
                            continue  # Already added
                        if field in component_data:
                            result[field] = component_data[field]
                else:
                    # Include all fields
                    result.update(component_data)

                results.append(result)

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error listing components: {e}")
        return []
    else:
        return results
    finally:
        await logger.ainfo("Listing components completed")


async def get_component_by_name(
    component_name: str,
    component_type: str | None = None,
    fields: list[str] | None = None,
    settings_service: SettingsService | None = None,
) -> dict[str, Any] | None:
    """Get a specific component by its name.

    Args:
        component_name: The name of the component to retrieve.
        component_type: Optional component type to narrow search.
        fields: Optional list of fields to include. If None, returns all fields.
        settings_service: Settings service instance for loading components.

    Returns:
        Dictionary containing the component data with selected fields, or None if not found.

    Example:
        >>> component = await get_component_by_name(
        ...     "OpenAIModel",
        ...     fields=["display_name", "description", "template"]
        ... )
    """
    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    try:
        all_types_dict = await get_and_cache_all_types_dict(settings_service)

        # If component_type specified, search only that type
        if component_type:
            components = all_types_dict.get(component_type, {})
            component_data = components.get(component_name)

            if component_data:
                result = {"name": component_name, "type": component_type}
                if fields:
                    for field in fields:
                        if field in {"name", "type"}:
                            continue
                        if field in component_data:
                            result[field] = component_data[field]
                else:
                    result.update(component_data)
                return result
        else:
            # Search across all types
            for comp_type, components in all_types_dict.items():
                if component_name in components:
                    component_data = components[component_name]
                    result = {"name": component_name, "type": comp_type}
                    if fields:
                        for field in fields:
                            if field in {"name", "type"}:
                                continue
                            if field in component_data:
                                result[field] = component_data[field]
                    else:
                        result.update(component_data)
                    return result

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error getting component {component_name}: {e}")
        return None
    else:
        return None
    finally:
        await logger.ainfo("Getting component completed")


async def get_all_component_types(settings_service: SettingsService | None = None) -> list[str]:
    """Get a list of all available component types.

    Args:
        settings_service: Settings service instance for loading components.

    Returns:
        Sorted list of component type names.

    Example:
        >>> types = await get_all_component_types()
        >>> print(types)
        ['agents', 'data', 'embeddings', 'llms', 'memories', 'tools', ...]
    """
    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    try:
        all_types_dict = await get_and_cache_all_types_dict(settings_service)
        return sorted(all_types_dict.keys())

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error getting component types: {e}")
        return []
    finally:
        await logger.ainfo("Getting component types completed")


async def get_components_count(
    component_type: str | None = None, settings_service: SettingsService | None = None
) -> int:
    """Get the total count of available components.

    Args:
        component_type: Optional component type to count only that type.
        settings_service: Settings service instance for loading components.

    Returns:
        Number of components found.

    Example:
        >>> count = await get_components_count()
        >>> print(f"Found {count} total components")

        >>> llm_count = await get_components_count(component_type="llms")
        >>> print(f"Found {llm_count} LLM components")
    """
    if settings_service is None:
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    try:
        all_types_dict = await get_and_cache_all_types_dict(settings_service)

        if component_type:
            components = all_types_dict.get(component_type, {})
            return len(components)

        # Count all components across all types
        return sum(len(components) for components in all_types_dict.values())

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error counting components: {e}")
        return 0
    finally:
        await logger.ainfo("Counting components completed")


async def get_components_by_type(
    component_type: str,
    fields: list[str] | None = None,
    settings_service: SettingsService | None = None,
) -> list[dict[str, Any]]:
    """Get all components of a specific type.

    Args:
        component_type: The component type to retrieve (e.g., "llms", "agents").
        fields: Optional list of fields to include. If None, returns all fields.
        settings_service: Settings service instance for loading components.

    Returns:
        List of components of the specified type.

    Example:
        >>> llms = await get_components_by_type(
        ...     "llms",
        ...     fields=["name", "display_name", "description"]
        ... )
    """
    return await list_all_components(component_type=component_type, fields=fields, settings_service=settings_service)
