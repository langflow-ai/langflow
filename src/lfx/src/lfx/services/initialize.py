"""Initialize services for lfx package."""

from lfx.services.memory.factory import MemoryServiceFactory
from lfx.services.settings.factory import SettingsServiceFactory
from lfx.services.storage.factory import StorageServiceFactory
from lfx.services.variable.factory import VariableServiceFactory


def initialize_services():
    """Initialize required services for lfx."""
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()

    # Register the lean no-deps defaults. Settings is the only hard requirement;
    # storage, variable, and memory are registered here so file-backed,
    # variable-using, and chat-memory components have a real service in bare lfx
    # instead of None. These go into the factory tier, so a heavier backend (e.g.
    # langflow) can override any of them through the same manager (config/decorator
    # registrations take precedence).
    service_manager.register_factory(SettingsServiceFactory())
    service_manager.register_factory(StorageServiceFactory())
    service_manager.register_factory(VariableServiceFactory())
    service_manager.register_factory(MemoryServiceFactory())

    # Note: auth and authorization self-register at import time via the
    # @register_service decorator. Storage and variable do NOT self-register on
    # import — they are wired up by the explicit register_factory calls above.

    # Services are created lazily on first use (e.g. via get_storage_service()),
    # not eagerly here.


# Initialize services when the module is imported
initialize_services()
