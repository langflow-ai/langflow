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
