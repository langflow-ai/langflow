"""Initialize services for lfx package."""

from lfx.services.manager import service_manager
from lfx.services.settings.factory import SettingsServiceFactory


def initialize_services():
    """Initialize required services for lfx."""
    # Register the settings service factory
    service_manager.register_factory(SettingsServiceFactory())

    # Note: We don't create the service immediately,
    # it will be created on first use via get_settings_service()


# Initialize services when the module is imported
initialize_services()
