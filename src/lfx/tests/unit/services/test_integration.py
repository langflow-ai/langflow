"""Integration tests for pluggable service system."""

import os

import pytest

from lfx.services.base import Service
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType


class TestStandaloneLFX:
    """Test LFX running standalone without langflow."""

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_minimal_storage_service_loads(self, clean_manager):
        """Test that minimal storage service loads by default."""
        from lfx.services.storage.local import LocalStorageService

        # Register the minimal storage service
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService)

        storage = clean_manager.get(ServiceType.STORAGE_SERVICE)

        assert isinstance(storage, LocalStorageService)
        assert storage.ready is True

    def test_minimal_telemetry_service_loads(self, clean_manager):
        """Test that minimal telemetry service loads by default."""
        # Should fall back to factory since no plugin registered

        # Telemetry doesn't have a default factory, so should fail
        # unless we register it first
        from lfx.services.telemetry.service import TelemetryService

        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService)

        telemetry = clean_manager.get(ServiceType.TELEMETRY_SERVICE)
        assert isinstance(telemetry, TelemetryService)
        assert telemetry.ready is True

    def test_minimal_variable_service_loads(self, clean_manager):
        """Test that minimal variable service loads by default."""
        from lfx.services.variable.service import VariableService

        clean_manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService)

        variables = clean_manager.get(ServiceType.VARIABLE_SERVICE)
        assert isinstance(variables, VariableService)
        assert variables.ready is True

    def test_settings_service_always_available(self, clean_manager):
        """Test that settings service is always available."""
        settings = clean_manager.get(ServiceType.SETTINGS_SERVICE)

        from lfx.services.settings.service import SettingsService

        assert isinstance(settings, SettingsService)
        assert settings.ready is True


class TestLFXWithLangflowConfig:
    """Test LFX with langflow configuration."""

    @pytest.fixture
    def langflow_config_dir(self, tmp_path):
        """Create a temporary langflow-style config directory."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create lfx.toml with langflow services
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
cache_service = "lfx.services.cache.service:ThreadingInMemoryCache"
"""
        )

        return config_dir

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_config_overrides_defaults(self, clean_manager, langflow_config_dir):
        """Test that config file overrides default services."""
        # Discover plugins from config
        clean_manager.discover_plugins(langflow_config_dir)

        # Storage should be loaded from config
        assert ServiceType.STORAGE_SERVICE in clean_manager.service_classes

        from lfx.services.storage.local import LocalStorageService

        assert clean_manager.service_classes[ServiceType.STORAGE_SERVICE] == LocalStorageService

    def test_multiple_services_from_config(self, clean_manager, langflow_config_dir):
        """Test loading multiple services from config."""
        clean_manager.discover_plugins(langflow_config_dir)

        # Both services should be registered
        assert ServiceType.STORAGE_SERVICE in clean_manager.service_classes
        assert ServiceType.CACHE_SERVICE in clean_manager.service_classes


class TestServiceOverrideScenarios:
    """Test various service override scenarios."""

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_decorator_overrides_config(self, clean_manager, tmp_path):
        """Test that decorator registration overrides config."""
        # First create config
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        # Load from config
        clean_manager.discover_plugins(config_dir)

        # Now override with direct registration (simulating decorator)
        class CustomStorageService(Service):
            @property
            def name(self) -> str:
                return "storage_service"

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, CustomStorageService, override=True)

        # Should use the override version
        assert clean_manager.service_classes[ServiceType.STORAGE_SERVICE] == CustomStorageService

    def test_override_false_preserves_existing(self, clean_manager):
        """Test that override=False preserves existing registration."""

        class FirstService(Service):
            name = "storage_service"

            async def teardown(self) -> None:
                pass

        class SecondService(Service):
            name = "storage_service"

            async def teardown(self) -> None:
                pass

        # Register first
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, FirstService, override=True)

        # Try to register second with override=False
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, SecondService, override=False)

        # Should still be first
        assert clean_manager.service_classes[ServiceType.STORAGE_SERVICE] == FirstService


class TestErrorConditions:
    """Test error handling in various conditions."""

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_missing_import_in_config(self, clean_manager, tmp_path):
        """Test handling of missing import in config."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
storage_service = "nonexistent.module:NonexistentClass"
"""
        )

        # Should not raise, just log warning
        clean_manager.discover_plugins(config_dir)

        # Service should not be registered
        assert ServiceType.STORAGE_SERVICE not in clean_manager.service_classes

    def test_invalid_service_type_in_config(self, clean_manager, tmp_path):
        """Test handling of invalid service type in config."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services]
invalid_service_type = "some.module:SomeClass"
"""
        )

        # Should not raise, just log warning
        clean_manager.discover_plugins(config_dir)

        # No services should be registered (invalid key)
        assert len(clean_manager.service_classes) == 0

    def test_malformed_toml_in_config(self, clean_manager, tmp_path):
        """Test handling of malformed TOML."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "lfx.toml"
        config_file.write_text(
            """
[services
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        # Should not raise, just log warning
        clean_manager.discover_plugins(config_dir)

        # No services should be registered
        assert len(clean_manager.service_classes) == 0

    def test_service_without_name_attribute(self, clean_manager):
        """Test registering a service without name attribute."""

        class InvalidService(Service):
            async def teardown(self) -> None:
                pass

        # Should not raise during registration
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, InvalidService)

        # But should fail during creation (can't instantiate abstract class)
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            clean_manager.get(ServiceType.STORAGE_SERVICE)

    def test_service_initialization_failure(self, clean_manager):
        """Test handling of service initialization failure."""

        class FailingService(Service):
            name = "storage_service"

            def __init__(self):
                msg = "Initialization failed"
                raise RuntimeError(msg)

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, FailingService)

        # Should raise the initialization error
        with pytest.raises(RuntimeError, match="Initialization failed"):
            clean_manager.get(ServiceType.STORAGE_SERVICE)


class TestDependencyResolution:
    """Test dependency resolution and injection."""

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_service_with_settings_dependency(self, clean_manager):
        """Test service that depends on settings service."""

        class ServiceWithSettings(Service):
            name = "test_service"

            def __init__(self, settings_service):
                super().__init__()
                self.settings = settings_service
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, ServiceWithSettings)

        service = clean_manager.get(ServiceType.STORAGE_SERVICE)

        # Should have settings injected
        from lfx.services.settings.service import SettingsService

        assert isinstance(service.settings, SettingsService)

    def test_service_with_multiple_dependencies(self, clean_manager):
        """Test service with multiple dependencies."""

        class SimpleService(Service):
            name = "simple_service"

            def __init__(self):
                super().__init__()
                self.set_ready()

            async def teardown(self) -> None:
                pass

        class ComplexService(Service):
            name = "complex_service"

            def __init__(self, settings_service, storage_service):
                super().__init__()
                self.settings = settings_service
                self.storage = storage_service
                self.set_ready()

            async def teardown(self) -> None:
                pass

        # Register both
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, SimpleService)
        clean_manager.register_service_class(ServiceType.CACHE_SERVICE, ComplexService)

        # Create complex service
        complex_service = clean_manager.get(ServiceType.CACHE_SERVICE)

        # Should have both dependencies
        from lfx.services.settings.service import SettingsService

        assert isinstance(complex_service.settings, SettingsService)
        assert isinstance(complex_service.storage, SimpleService)

    def test_service_with_unresolvable_dependency(self, clean_manager):
        """Test service with dependency that can't be resolved."""

        class ServiceWithUnknownDep(Service):
            name = "test_service"

            def __init__(self, unknown_param: str):
                super().__init__()
                self.unknown_param = unknown_param
                self.set_ready()

            async def teardown(self) -> None:
                pass

        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, ServiceWithUnknownDep)

        # Should raise due to missing parameter
        with pytest.raises(TypeError):
            clean_manager.get(ServiceType.STORAGE_SERVICE)


class TestConfigFileDiscovery:
    """Test configuration file discovery."""

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_pyproject_toml_discovery(self, clean_manager, tmp_path):
        """Test discovering services from pyproject.toml."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "pyproject.toml"
        config_file.write_text(
            """
[tool.lfx.services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        clean_manager.discover_plugins(config_dir)

        assert ServiceType.STORAGE_SERVICE in clean_manager.service_classes

    def test_lfx_toml_takes_precedence(self, clean_manager, tmp_path):
        """Test that lfx.toml takes precedence over pyproject.toml."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create both files with different services
        (config_dir / "lfx.toml").write_text(
            """
[services]
storage_service = "lfx.services.storage.local:LocalStorageService"
"""
        )

        (config_dir / "pyproject.toml").write_text(
            """
[tool.lfx.services]
cache_service = "lfx.services.cache.service:ThreadingInMemoryCache"
"""
        )

        clean_manager.discover_plugins(config_dir)

        # Should only have storage from lfx.toml
        assert ServiceType.STORAGE_SERVICE in clean_manager.service_classes
        assert ServiceType.CACHE_SERVICE not in clean_manager.service_classes

    def test_no_config_file_no_error(self, clean_manager, tmp_path):
        """Test that missing config files don't cause errors."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Should not raise
        clean_manager.discover_plugins(config_dir)

        assert len(clean_manager.service_classes) == 0


class TestEnvironmentVariableIntegration:
    """Test environment variable integration with services."""

    @pytest.fixture
    def clean_manager(self):
        """Create a clean ServiceManager instance."""
        manager = ServiceManager()
        yield manager
        # Cleanup
        import asyncio

        asyncio.run(manager.teardown())

    def test_variable_service_uses_env(self, clean_manager):
        """Test that variable service reads from environment."""
        from lfx.services.variable.service import VariableService

        clean_manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService)

        os.environ["TEST_API_KEY"] = "test_value_123"  # pragma: allowlist secret
        try:
            variables = clean_manager.get(ServiceType.VARIABLE_SERVICE)
            value = variables.get_variable("TEST_API_KEY")
            assert value == "test_value_123"
        finally:
            del os.environ["TEST_API_KEY"]

    def test_variable_service_in_memory_overrides_env(self, clean_manager):
        """Test that in-memory variables override environment."""
        from lfx.services.variable.service import VariableService

        clean_manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService)

        os.environ["TEST_VAR"] = "env_value"
        try:
            variables = clean_manager.get(ServiceType.VARIABLE_SERVICE)
            variables.set_variable("TEST_VAR", "memory_value")
            value = variables.get_variable("TEST_VAR")
            assert value == "memory_value"
        finally:
            del os.environ["TEST_VAR"]
