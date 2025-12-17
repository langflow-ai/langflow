"""Edge case tests for pluggable service system."""

import pytest
from lfx.services.base import Service
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType


class MockSessionService(Service):
    """Mock session service for testing."""

    name = "session_service"

    def __init__(self):
        """Initialize mock session service."""
        self.set_ready()

    async def teardown(self) -> None:
        """Teardown the mock session service."""


@pytest.fixture
def clean_manager():
    """Create a clean ServiceManager instance with mock dependencies."""
    manager = ServiceManager()

    # Register mock SESSION_SERVICE so services with dependencies can be created
    manager.register_service_class(ServiceType.SESSION_SERVICE, MockSessionService, override=True)

    yield manager
    # Cleanup
    import asyncio

    asyncio.run(manager.teardown())


class TestCircularDependencyDetection:
    """Test detection and handling of circular dependencies."""

    def test_self_circular_dependency(self, clean_manager):
        """Test service that depends on itself."""

        class SelfCircularService(Service):
            @property
            def name(self) -> str:
                return "self_circular"

            def __init__(self, storage_service):
                super().__init__()
                self.storage = storage_service
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, SelfCircularService)

        # Should raise RecursionError or TypeError (missing required argument)
        with pytest.raises((RecursionError, RuntimeError, TypeError)):
            clean_manager.get(ServiceType.STORAGE_SERVICE)


class TestServiceLifecycle:
    """Test service lifecycle management."""

    def test_service_ready_state(self, clean_manager):
        """Test service ready state tracking."""

        class SlowInitService(Service):
            @property
            def name(self) -> str:
                return "slow_service"

            def __init__(self):
                super().__init__()
                # Don't set ready immediately

            def complete_init(self):
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, SlowInitService)

        service = clean_manager.get(ServiceType.STORAGE_SERVICE)

        # Should not be ready yet
        assert service.ready is False

        # Complete initialization
        service.complete_init()
        assert service.ready is True

    @pytest.mark.asyncio
    async def test_service_teardown_called(self, clean_manager):
        """Test that teardown is called on services."""
        teardown_called = []

        class TeardownTrackingService(Service):
            name = "tracking_service"

            def __init__(self):
                super().__init__()
                self.set_ready()

            async def teardown(self) -> None:
                teardown_called.append(True)

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, TeardownTrackingService)

        # Create service
        clean_manager.get(ServiceType.STORAGE_SERVICE)

        # Teardown
        await clean_manager.teardown()

        # Should have been called
        assert len(teardown_called) == 1

    @pytest.mark.asyncio
    async def test_multiple_teardowns_safe(self, clean_manager):
        """Test that calling teardown multiple times is safe."""

        class SimpleService(Service):
            name = "simple_service"

            def __init__(self):
                super().__init__()
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, SimpleService)
        clean_manager.get(ServiceType.STORAGE_SERVICE)

        # Teardown multiple times - should not raise
        await clean_manager.teardown()
        await clean_manager.teardown()


class TestConfigParsingEdgeCases:
    """Test edge cases in configuration parsing."""

    def test_empty_config_file(self, clean_manager, tmp_path):
        """Test empty configuration file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text("")

        # Should not raise
        clean_manager.discover_plugins(config_dir)

        assert len(clean_manager.service_classes) == 1  # MockSessionService from fixture

    def test_config_with_no_services_section(self, clean_manager, tmp_path):
        """Test config file with no [services] section."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[other_section]
key = "value"
"""
        )

        # Should not raise
        clean_manager.discover_plugins(config_dir)

        assert len(clean_manager.service_classes) == 1  # MockSessionService from fixture

    def test_config_with_empty_services_section(self, clean_manager, tmp_path):
        """Test config with empty [services] section."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
"""
        )

        # Should not raise
        clean_manager.discover_plugins(config_dir)

        assert len(clean_manager.service_classes) == 1  # MockSessionService from fixture

    def test_config_with_malformed_import_path(self, clean_manager, tmp_path):
        """Test config with malformed import path."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "invalid_path_without_colon"
"""
        )

        # Should not raise, just log warning
        clean_manager.discover_plugins(config_dir)

        assert ServiceType.STORAGE_SERVICE not in clean_manager.service_classes

    def test_config_with_too_many_colons(self, clean_manager, tmp_path):
        """Test config with too many colons in import path."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "module:submodule:class:extra"
"""
        )

        # Should not raise, just log warning
        clean_manager.discover_plugins(config_dir)

        assert ServiceType.STORAGE_SERVICE not in clean_manager.service_classes


class TestServiceRegistrationEdgeCases:
    """Test edge cases in service registration."""

    def test_register_non_service_class(self, clean_manager):
        """Test registering a class that doesn't inherit from Service."""

        class NotAService:
            @property
            def name(self) -> str:
                return "not_service"

            def __init__(self):
                pass

            async def teardown(self) -> None:
                pass

        # Should not raise during registration
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, NotAService)

        # Gets created successfully but doesn't have service methods
        service = clean_manager.get(ServiceType.STORAGE_SERVICE)
        assert service is not None
        # But won't have ready attribute since it doesn't inherit from Service
        assert not hasattr(service, "_ready")

    def test_register_abstract_service(self, clean_manager):
        """Test registering an abstract service class."""
        from abc import ABC, abstractmethod

        class AbstractService(Service, ABC):
            name = "abstract_service"

            @abstractmethod
            def do_something(self):
                pass

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, AbstractService)

        # Should fail due to abstract methods
        with pytest.raises(TypeError):
            clean_manager.get(ServiceType.STORAGE_SERVICE)

    def test_register_same_service_multiple_times_with_override(self, clean_manager):
        """Test registering same service type multiple times with override."""

        class Service1(Service):
            name = "service1"

            async def teardown(self) -> None:
                pass

        class Service2(Service):
            name = "service2"

            async def teardown(self) -> None:
                pass

        class Service3(Service):
            name = "service3"

            async def teardown(self) -> None:
                pass

        # Register multiple times
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, Service1, override=True)
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, Service2, override=True)
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, Service3, override=True)

        # Should have the last one
        assert clean_manager.service_classes[ServiceType.STORAGE_SERVICE] == Service3


class TestDependencyInjectionEdgeCases:
    """Test edge cases in dependency injection."""

    def test_service_with_optional_dependencies(self, clean_manager):
        """Test service with optional parameters."""

        class ServiceWithOptional(Service):
            name = "optional_service"

            def __init__(self, settings_service=None):
                super().__init__()
                self.settings = settings_service
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, ServiceWithOptional)

        service = clean_manager.get(ServiceType.STORAGE_SERVICE)

        # Should have settings injected
        from lfx.services.settings.service import SettingsService

        assert isinstance(service.settings, SettingsService)

    def test_service_with_no_init_params(self, clean_manager):
        """Test service that takes no init parameters."""

        class NoParamService(Service):
            name = "no_param_service"

            def __init__(self):
                super().__init__()
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, NoParamService)

        service = clean_manager.get(ServiceType.STORAGE_SERVICE)

        assert service.ready is True

    def test_service_with_non_service_params(self, clean_manager):
        """Test service with parameters that aren't services."""

        class ServiceWithConfig(Service):
            name = "config_service"

            def __init__(self, config: dict):
                super().__init__()
                self.config = config
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, ServiceWithConfig)

        # Should fail - can't resolve dict parameter
        with pytest.raises(TypeError):
            clean_manager.get(ServiceType.STORAGE_SERVICE)


class TestConcurrentAccess:
    """Test concurrent access to service manager."""

    def test_multiple_gets_return_same_instance(self, clean_manager):
        """Test that multiple get calls return same instance."""

        class SimpleService(Service):
            name = "simple_service"

            def __init__(self):
                super().__init__()
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, SimpleService)

        # Get multiple times
        service1 = clean_manager.get(ServiceType.STORAGE_SERVICE)
        service2 = clean_manager.get(ServiceType.STORAGE_SERVICE)
        service3 = clean_manager.get(ServiceType.STORAGE_SERVICE)

        # Should all be the same instance
        assert service1 is service2
        assert service2 is service3


class TestSettingsServiceProtection:
    """Test settings service protection mechanisms."""

    def test_cannot_register_settings_via_class(self, clean_manager):
        """Test that settings service cannot be registered via class."""

        class CustomSettings(Service):
            name = "settings_service"

            async def teardown(self) -> None:
                pass

        with pytest.raises(ValueError, match="Settings service cannot be registered"):
            clean_manager.register_service_class(ServiceType.SETTINGS_SERVICE, CustomSettings)

    def test_cannot_register_settings_via_decorator(self):
        """Test that settings service cannot be registered via decorator."""
        from lfx.services.registry import register_service

        with pytest.raises(ValueError, match="Settings service cannot be registered"):

            @register_service(ServiceType.SETTINGS_SERVICE)
            class CustomSettings(Service):
                name = "settings_service"

                async def teardown(self) -> None:
                    pass

    def test_settings_service_always_uses_factory(self, clean_manager):
        """Test that settings service always uses factory."""
        settings = clean_manager.get(ServiceType.SETTINGS_SERVICE)

        from lfx.services.settings.service import SettingsService

        # Should be the built-in SettingsService
        assert isinstance(settings, SettingsService)

    def test_cannot_override_settings_in_config(self, clean_manager, tmp_path):
        """Test that settings service in config is ignored."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
settings_service = "some.custom:SettingsService"
"""
        )

        # Should not raise, but should ignore the settings_service entry
        clean_manager.discover_plugins(config_dir)

        # Settings should not be in service_classes
        assert ServiceType.SETTINGS_SERVICE not in clean_manager.service_classes

        # Getting settings should still work (via factory)
        settings = clean_manager.get(ServiceType.SETTINGS_SERVICE)

        from lfx.services.settings.service import SettingsService

        assert isinstance(settings, SettingsService)
