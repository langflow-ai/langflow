"""Cloud environment validation utilities.

This module contains validation functions for cloud-specific constraints,
such as disabling certain features when running in Astra cloud environment.
"""

import os


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


def get_cloud_disabled_components() -> dict[str, set[str]]:
    """Get a mapping of component types to their disabled module names when in cloud environment.

    This function returns a dictionary where:
    - Keys are component type names (e.g., "docling")
    - Values are sets of module filenames that should be disabled (e.g., {"chunk_docling_document", "docling_inline"})

    To add new disabled components in the future, simply add entries to this dictionary.

    Returns:
        dict[str, set[str]]: Mapping of component type to disabled module names.
    """
    return {
        "docling": {
            "chunk_docling_document",
            "docling_inline",
            "export_docling_document",
        }
    }


def is_component_disabled_in_cloud(component_type: str, module_filename: str) -> bool:
    """Check if a specific component module should be disabled in cloud environment.

    Args:
        component_type: The top-level component type (e.g., "docling")
        module_filename: The module filename without extension (e.g., "chunk_docling_document")

    Returns:
        bool: True if the component should be disabled, False otherwise.
    """
    if not is_astra_cloud_environment():
        return False

    disabled_components = get_cloud_disabled_components()
    disabled_modules = disabled_components.get(component_type, set())
    return module_filename in disabled_modules
