"""Genesis Services Registration Module.

This module handles the registration of Genesis-specific services
with the Langflow service manager.
"""

from loguru import logger
from langflow.services.manager import ServiceManager


def register_genesis_services() -> bool:
    """Register Genesis-specific services with the service manager.

    Returns:
        bool: True if registration was successful
    """
    try:
        logger.info("🔧 Registering Genesis services...")

        # Get the service manager instance
        service_manager = ServiceManager()

        # For now, just return True as the existing services are already registered
        # Add any additional Genesis-specific service registrations here if needed

        logger.debug("✅ Genesis services registered successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to register Genesis services: {e}")
        return False


__all__ = [
    "register_genesis_services",
]