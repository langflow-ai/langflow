"""Cloud environment validation utilities.

This module contains validation functions for cloud-specific constraints,
such as disabling certain features when running in Astra cloud environment.
"""

import os
from typing import Any


def is_astra_cloud_environment() -> bool:
    """Check if we're running in an Astra cloud environment.

    Check if the environment variable ASTRA_CLOUD_DISABLE_COMPONENT is set to true.
    IF it is, then we know we are in an Astra cloud environment.

    Returns:
        bool: True if running in an Astra cloud environment, False otherwise.
    """
    disable_component = os.getenv("ASTRA_CLOUD_DISABLE_COMPONENT", "false")
    return disable_component.lower().strip() == "true"


def raise_error_if_astra_cloud_disable_component(msg: str):
    """Validate that we're not in an Astra cloud environment and certain components/features need to be disabled.

    Check if the environment variable ASTRA_CLOUD_DISABLE_COMPONENT is set to true.
    IF it is, then we know we are in an Astra cloud environment and
    that certain components or component-features need to be disabled.

    Args:
        msg: The error message to raise if we're in an Astra cloud environment.

    Raises:
        ValueError: If running in an Astra cloud environment.
    """
    if is_astra_cloud_environment():
        raise ValueError(msg)


# Mapping of component types to their disabled module names and component names when in Astra cloud environment.
# Keys are component type names (e.g., "docling")
# Values are sets containing both module filenames (e.g., "chunk_docling_document")
# and component names (e.g., "ChunkDoclingDocument")
# To add new disabled components in the future, simply add entries to this dictionary.
ASTRA_CLOUD_DISABLED_COMPONENTS: dict[str, set[str]] = {
    "docling": {
        # Module filenames (for dynamic loading)
        "chunk_docling_document",
        "docling_inline",
        "export_docling_document",
        # Component names (for index/cache loading)
        "ChunkDoclingDocument",
        "DoclingInline",
        "ExportDoclingDocument",
    }
}


def is_component_disabled_in_astra_cloud(component_type: str, module_filename: str) -> bool:
    """Check if a specific component module should be disabled in cloud environment.

    Args:
        component_type: The top-level component type (e.g., "docling")
        module_filename: The module filename without extension (e.g., "chunk_docling_document")

    Returns:
        bool: True if the component should be disabled, False otherwise.
    """
    if not is_astra_cloud_environment():
        return False

    disabled_modules = ASTRA_CLOUD_DISABLED_COMPONENTS.get(component_type.lower(), set())
    return module_filename in disabled_modules


def filter_disabled_components_from_dict(modules_dict: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Filter out disabled components from a loaded modules dictionary.

    This function is used to filter components that were loaded from index/cache,
    since those bypass the dynamic loading filter.

    Args:
        modules_dict: Dictionary mapping component types to their components

    Returns:
        Filtered dictionary with disabled components removed
    """
    if not is_astra_cloud_environment():
        return modules_dict

    filtered_dict: dict[str, dict[str, Any]] = {}
    for component_type, components in modules_dict.items():
        disabled_set = ASTRA_CLOUD_DISABLED_COMPONENTS.get(component_type.lower(), set())
        if disabled_set:
            # Filter out disabled components
            filtered_components = {name: comp for name, comp in components.items() if name not in disabled_set}
            if filtered_components:  # Only add if there are remaining components
                filtered_dict[component_type] = filtered_components
        else:
            # No disabled components for this type, keep all
            filtered_dict[component_type] = components

    return filtered_dict
