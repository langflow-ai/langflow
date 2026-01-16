"""Tests for the ServiceManager plugin system."""

from pathlib import Path

import pytest
from lfx.services.base import Service
from lfx.services.manager import NoFactoryRegisteredError, ServiceManager
from lfx.services.schema import ServiceType
from lfx.services.storage.local import LocalStorageService
from lfx.services.telemetry.service import TelemetryService
from lfx.services.tracing.service import TracingService
from lfx.services.variable.service import VariableService


@pytest.fixture
def service_manager():
    """Create a fresh ServiceManager for each test."""
    manager = ServiceManager()
    yield manager
    # Cleanup
    import asyncio

    asyncio.run(manager.teardown())


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


class TestServiceRegistration:
    """Tests for service registration with real implementations."""

    def test_register_storage_service(self, service_manager):
        """Test registering the real LocalStorageService."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService, override=True)

        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes
        assert service_manager.service_classes[ServiceType.STORAGE_SERVICE] == LocalStorageService

    def test_register_multiple_real_services(self, service_manager):
        """Test registering multiple real services."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService, override=True)
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService, override=True)
        service_manager.register_service_class(ServiceType.TRACING_SERVICE, TracingService, override=True)
        service_manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService, override=True)

        assert len(service_manager.service_classes) == 4
        assert service_manager.service_classes[ServiceType.STORAGE_SERVICE] == LocalStorageService
        assert service_manager.service_classes[ServiceType.TELEMETRY_SERVICE] == TelemetryService
        assert service_manager.service_classes[ServiceType.TRACING_SERVICE] == TracingService
        assert service_manager.service_classes[ServiceType.VARIABLE_SERVICE] == VariableService

    def test_register_service_class_no_override(self, service_manager):
        """Test that override=False prevents replacement."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService, override=True)

        # Try to register different class with override=False
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, TelemetryService, override=False)

        # Should still have the original
        assert service_manager.service_classes[ServiceType.STORAGE_SERVICE] == LocalStorageService

    def test_register_service_class_with_override(self, service_manager):
        """Test that override=True replaces existing registration."""
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService, override=True)

        # Override with different service
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TracingService, override=True)

        # Should have the new one
        assert service_manager.service_classes[ServiceType.TELEMETRY_SERVICE] == TracingService

    def test_cannot_register_settings_service(self, service_manager):
        """Test that settings service cannot be registered via plugins."""
        with pytest.raises(ValueError, match="Settings service cannot be registered"):
            service_manager.register_service_class(ServiceType.SETTINGS_SERVICE, LocalStorageService)


class TestPluginDiscovery:
    """Tests for plugin discovery with real service paths."""

    def test_discover_storage_from_config_file(self, service_manager, temp_config_dir):
        """Test discovering LocalStorageService from lfx.toml."""
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)

        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes
        assert service_manager.service_classes[ServiceType.STORAGE_SERVICE] == LocalStorageService

    def test_discover_multiple_services_from_config(self, service_manager, temp_config_dir):
        """Test discovering multiple real services from config."""
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
telemetry_service = "lfx.services.telemetry.service:TelemetryService"
tracing_service = "lfx.services.tracing.service:TracingService"
variable_service = "lfx.services.variable.service:VariableService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)

        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes
        assert ServiceType.TELEMETRY_SERVICE in service_manager.service_classes
        assert ServiceType.TRACING_SERVICE in service_manager.service_classes
        assert ServiceType.VARIABLE_SERVICE in service_manager.service_classes

    def test_discover_from_pyproject_toml(self, service_manager, temp_config_dir):
        """Test discovering services from pyproject.toml."""
        config_file = temp_config_dir / "pyproject.toml"
        config_file.write_text(
            """
[tool.lfx.services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)

        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes

    def test_lfx_toml_takes_precedence_over_pyproject(self, service_manager, temp_config_dir):
        """Test that lfx.toml is preferred over pyproject.toml."""
        # Create both files
        (temp_config_dir / "lfx.toml").write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )
        (temp_config_dir / "pyproject.toml").write_text(
            """
[tool.lfx.services]
telemetry_service = "lfx.services.telemetry.service:TelemetryService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)

        # Should have loaded from lfx.toml (storage_service)
        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes
        # Should NOT have loaded from pyproject.toml (telemetry_service)
        assert ServiceType.TELEMETRY_SERVICE not in service_manager.service_classes

    def test_discover_plugins_only_once(self, service_manager, temp_config_dir):
        """Test that plugin discovery only runs once."""
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)
        initial_count = len(service_manager.service_classes)

        # Try to discover again
        service_manager.discover_plugins(temp_config_dir)

        # Should not have changed
        assert len(service_manager.service_classes) == initial_count

    def test_invalid_service_key_in_config(self, service_manager, temp_config_dir):
        """Test that invalid service keys are ignored."""
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
invalid_service_key = "some.module:SomeClass"  # pragma: allowlist secret
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        # Should not raise, just log warning
        service_manager.discover_plugins(temp_config_dir)

        # Valid service should still be registered
        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes

    def test_invalid_import_path_in_config(self, service_manager, temp_config_dir):
        """Test that invalid import paths are handled gracefully."""
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "nonexistent.module:NonexistentClass"
"""
        )

        # Should not raise, just log warning
        service_manager.discover_plugins(temp_config_dir)

        # Service should not be registered
        assert ServiceType.STORAGE_SERVICE not in service_manager.service_classes


class TestServiceCreation:
    """Tests for creating real services with dependency injection."""

    def test_create_storage_service(self, service_manager):
        """Test creating LocalStorageService."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)

        service = service_manager.get(ServiceType.STORAGE_SERVICE)

        assert isinstance(service, LocalStorageService)
        assert service.ready is True
        assert service.name == "storage_service"

    def test_create_telemetry_service(self, service_manager):
        """Test creating TelemetryService."""
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService)

        service = service_manager.get(ServiceType.TELEMETRY_SERVICE)

        assert isinstance(service, TelemetryService)
        assert service.ready is True
        assert service.name == "telemetry_service"

    def test_create_tracing_service(self, service_manager):
        """Test creating TracingService."""
        service_manager.register_service_class(ServiceType.TRACING_SERVICE, TracingService)

        service = service_manager.get(ServiceType.TRACING_SERVICE)

        assert isinstance(service, TracingService)
        assert service.ready is True
        assert service.name == "tracing_service"

    def test_create_variable_service(self, service_manager):
        """Test creating VariableService."""
        service_manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService)

        service = service_manager.get(ServiceType.VARIABLE_SERVICE)

        assert isinstance(service, VariableService)
        assert service.ready is True
        assert service.name == "variable_service"

    def test_create_service_with_settings_dependency(self, service_manager):
        """Test creating a service that depends on settings."""

        # Create a real service that needs settings
        class ServiceWithSettings(Service):
            @property
            def name(self) -> str:
                return "test_service"

            def __init__(self, settings_service):
                super().__init__()
                self.settings = settings_service
                self.set_ready()

            async def teardown(self) -> None:
                pass

        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, ServiceWithSettings)

        service = service_manager.get(ServiceType.STORAGE_SERVICE)

        # Should have settings injected
        from lfx.services.settings.service import SettingsService

        assert isinstance(service, ServiceWithSettings)
        assert isinstance(service.settings, SettingsService)
        assert service.ready is True

    def test_create_service_caching(self, service_manager):
        """Test that services are cached (singleton)."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)

        service1 = service_manager.get(ServiceType.STORAGE_SERVICE)
        service2 = service_manager.get(ServiceType.STORAGE_SERVICE)

        assert service1 is service2

    def test_settings_service_always_uses_factory(self, service_manager):
        """Test that settings service always uses factory."""
        service = service_manager.get(ServiceType.SETTINGS_SERVICE)

        from lfx.services.settings.service import SettingsService

        assert isinstance(service, SettingsService)

    def test_fallback_to_factory_if_no_plugin(self, service_manager):
        """Test that services fall back to factory if no plugin registered."""
        # Don't register any plugin for storage
        # Should fail since there's no factory either
        with pytest.raises(NoFactoryRegisteredError):
            service_manager.get(ServiceType.STORAGE_SERVICE)


class TestConflictResolution:
    """Tests for conflict resolution with real services."""

    def test_direct_registration_overrides_config(self, service_manager, temp_config_dir):
        """Test that direct registration overrides config file."""
        # First load from config
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
telemetry_service = "lfx.services.telemetry.service:TelemetryService"
"""
        )
        service_manager.discover_plugins(temp_config_dir)

        # Then register via direct call (override=True)
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TracingService, override=True)

        # Should use the directly registered service
        assert service_manager.service_classes[ServiceType.TELEMETRY_SERVICE] == TracingService


class TestTeardown:
    """Tests for service teardown with real services."""

    @pytest.mark.asyncio
    async def test_teardown_all_services(self, service_manager):
        """Test that teardown clears all services."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService)
        service_manager.get(ServiceType.STORAGE_SERVICE)
        service_manager.get(ServiceType.TELEMETRY_SERVICE)

        await service_manager.teardown()

        assert len(service_manager.services) == 0
        assert len(service_manager.factories) == 0

    @pytest.mark.asyncio
    async def test_teardown_calls_service_teardown(self, service_manager):
        """Test that teardown calls each service's teardown method."""
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)
        storage = service_manager.get(ServiceType.STORAGE_SERVICE)

        # Service should exist
        assert storage is not None

        await service_manager.teardown()

        # Services should be cleared
        assert ServiceType.STORAGE_SERVICE not in service_manager.services


class TestConfigDirectorySource:
    """Tests for config_dir parameter with real services."""

    def test_config_dir_from_settings_service(self, service_manager):
        """Test that config_dir comes from settings service."""
        # Create settings service first
        settings_service = service_manager.get(ServiceType.SETTINGS_SERVICE)

        # Create config in the settings config_dir
        config_dir = Path(settings_service.settings.config_dir)
        config_dir.mkdir(parents=True, exist_ok=True)

        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        # Discover plugins (should use settings.config_dir)
        service_manager._plugins_discovered = False  # Reset flag
        service_manager.discover_plugins()

        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes

    def test_config_dir_falls_back_to_cwd(self, service_manager, temp_config_dir):
        """Test that config_dir falls back to cwd if settings not available."""
        # Don't create settings service
        # Should fall back to provided config_dir
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)

        # Should have searched temp_config_dir (passed as param)
        assert service_manager._plugins_discovered is True
        assert ServiceType.STORAGE_SERVICE in service_manager.service_classes


class TestRealWorldScenarios:
    """Tests for realistic usage scenarios."""

    @pytest.mark.asyncio
    async def test_complete_service_lifecycle(self, service_manager):
        """Test complete lifecycle: register, create, use, teardown."""
        # Register
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)

        # Create
        storage = service_manager.get(ServiceType.STORAGE_SERVICE)
        assert storage.ready is True

        # Use
        await storage.save_file("test_flow", "test.txt", b"test content")
        content = await storage.get_file("test_flow", "test.txt")
        assert content == b"test content"

        # Teardown
        await service_manager.teardown()
        assert ServiceType.STORAGE_SERVICE not in service_manager.services

    def test_multiple_services_working_together(self, service_manager):
        """Test multiple services can coexist and work together."""
        # Register all minimal services
        service_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)
        service_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService)
        service_manager.register_service_class(ServiceType.TRACING_SERVICE, TracingService)
        service_manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService)

        # Create all services
        storage = service_manager.get(ServiceType.STORAGE_SERVICE)
        telemetry = service_manager.get(ServiceType.TELEMETRY_SERVICE)
        tracing = service_manager.get(ServiceType.TRACING_SERVICE)
        variables = service_manager.get(ServiceType.VARIABLE_SERVICE)

        # All should be ready
        assert storage.ready is True
        assert telemetry.ready is True
        assert tracing.ready is True
        assert variables.ready is True

        # All should be usable
        tracing.add_log("test_trace", {"message": "test"})
        variables.set_variable("TEST_KEY", "test_value")
        assert variables.get_variable("TEST_KEY") == "test_value"

    def test_config_file_with_all_minimal_services(self, service_manager, temp_config_dir):
        """Test loading all minimal services from config file."""
        config_file = temp_config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
telemetry_service = "lfx.services.telemetry.service:TelemetryService"
tracing_service = "lfx.services.tracing.service:TracingService"
variable_service = "lfx.services.variable.service:VariableService"
"""
        )

        service_manager.discover_plugins(temp_config_dir)

        # All services should be registered
        assert len(service_manager.service_classes) == 4

        # Create and verify each service
        storage = service_manager.get(ServiceType.STORAGE_SERVICE)
        telemetry = service_manager.get(ServiceType.TELEMETRY_SERVICE)
        tracing = service_manager.get(ServiceType.TRACING_SERVICE)
        variables = service_manager.get(ServiceType.VARIABLE_SERVICE)

        assert isinstance(storage, LocalStorageService)
        assert isinstance(telemetry, TelemetryService)
        assert isinstance(tracing, TracingService)
        assert isinstance(variables, VariableService)
