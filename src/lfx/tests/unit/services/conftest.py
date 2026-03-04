"""Shared fixtures for service tests."""

from unittest.mock import MagicMock

import pytest
from lfx.services.base import Service
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType


class MockSessionService(Service):
    """Mock session service for testing.

    Provides a minimal session service implementation that satisfies
    the dependency requirements of services like LocalStorageService.
    """

    name = "session_service"

    def __init__(self):
        super().__init__()
        self.set_ready()

    async def teardown(self) -> None:
        pass


@pytest.fixture
def mock_session_service():
    """Create a mock session service using MagicMock."""
    return MagicMock()


@pytest.fixture
def mock_settings_service(tmp_path):
    """Create a mock settings service with tmp_path as config_dir."""
    mock = MagicMock()
    mock.settings.config_dir = str(tmp_path)
    return mock


@pytest.fixture
def service_manager_with_session():
    """Create a ServiceManager with MockSessionService registered.

    This fixture is useful for tests that need to create services
    via the ServiceManager that depend on session_service.
    """
    import asyncio

    manager = ServiceManager()
    manager.register_service_class(ServiceType.SESSION_SERVICE, MockSessionService, override=True)
    yield manager
    asyncio.run(manager.teardown())
