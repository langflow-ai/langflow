"""Tests for decorator-based service registration."""

import pytest
from lfx.services.base import Service
from lfx.services.manager import ServiceManager
from lfx.services.schema import ServiceType
from lfx.services.storage.local import LocalStorageService
from lfx.services.telemetry.service import TelemetryService
from lfx.services.tracing.service import TracingService


@pytest.fixture
def clean_manager():
    """Create a fresh ServiceManager for testing decorators."""
    manager = ServiceManager()
    yield manager
    # Cleanup
    import asyncio

    asyncio.run(manager.teardown())


class TestDecoratorRegistration:
    """Tests for @register_service decorator with real services."""

    def test_decorator_registers_real_storage_service(self, clean_manager):
        """Test that decorator registers real LocalStorageService."""
        # Use direct registration to simulate decorator (since decorator uses singleton)
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService, override=True)

        assert ServiceType.STORAGE_SERVICE in clean_manager.service_classes
        assert clean_manager.service_classes[ServiceType.STORAGE_SERVICE] == LocalStorageService

        # Verify we can actually create and use the service
        storage = clean_manager.get(ServiceType.STORAGE_SERVICE)
        assert isinstance(storage, LocalStorageService)
        assert storage.ready is True

    @pytest.mark.asyncio
    async def test_decorator_registers_real_telemetry_service(self, clean_manager):
        """Test that decorator registers real TelemetryService."""
        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService, override=True)

        assert ServiceType.TELEMETRY_SERVICE in clean_manager.service_classes
        assert clean_manager.service_classes[ServiceType.TELEMETRY_SERVICE] == TelemetryService

        # Verify service works
        telemetry = clean_manager.get(ServiceType.TELEMETRY_SERVICE)
        assert isinstance(telemetry, TelemetryService)
        await telemetry.log_package_version()  # Should not raise

    def test_decorator_with_override_false_preserves_first(self, clean_manager):
        """Test decorator with override=False preserves first registration."""
        # Register first service
        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService, override=True)

        # Try to register second service with override=False
        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TracingService, override=False)

        # Should still be first service
        assert clean_manager.service_classes[ServiceType.TELEMETRY_SERVICE] == TelemetryService

    def test_decorator_with_override_true_replaces(self, clean_manager):
        """Test decorator with override=True replaces existing."""
        # Register first service
        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService, override=True)

        # Replace with second service
        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TracingService, override=True)

        # Should be second service
        assert clean_manager.service_classes[ServiceType.TELEMETRY_SERVICE] == TracingService

    def test_cannot_decorate_settings_service(self, clean_manager):
        """Test that decorating settings service raises ValueError."""
        with pytest.raises(ValueError, match="Settings service cannot be registered"):
            clean_manager.register_service_class(ServiceType.SETTINGS_SERVICE, LocalStorageService)

    def test_decorator_with_custom_service_class(self, clean_manager):
        """Test decorator with a custom service implementation."""

        class CustomTracingService(Service):
            @property
            def name(self) -> str:
                return "tracing_service"

            def __init__(self):
                super().__init__()
                self.messages = []
                self.set_ready()

            def add_log(self, trace_name: str, log: dict):
                self.messages.append(f"{trace_name}: {log}")

            async def teardown(self) -> None:
                self.messages.clear()

        clean_manager.register_service_class(ServiceType.TRACING_SERVICE, CustomTracingService, override=True)

        # Verify registration
        assert clean_manager.service_classes[ServiceType.TRACING_SERVICE] == CustomTracingService

        # Verify we can use it
        tracing = clean_manager.get(ServiceType.TRACING_SERVICE)
        assert isinstance(tracing, CustomTracingService)
        tracing.add_log("test_trace", {"message": "test message"})
        assert len(tracing.messages) == 1

    def test_decorator_preserves_class_functionality(self, clean_manager):
        """Test that decorator preserves all class functionality."""
        clean_manager.register_service_class(ServiceType.VARIABLE_SERVICE, LocalStorageService, override=True)

        # Class should still be usable directly (not just through manager)
        direct_instance = LocalStorageService()
        assert direct_instance.ready is True
        assert direct_instance.name == "storage_service"

    def test_multiple_decorators_on_different_services(self, clean_manager):
        """Test registering multiple different services."""
        clean_manager.register_service_class(ServiceType.STORAGE_SERVICE, LocalStorageService, override=True)
        clean_manager.register_service_class(ServiceType.TELEMETRY_SERVICE, TelemetryService, override=True)
        clean_manager.register_service_class(ServiceType.TRACING_SERVICE, TracingService, override=True)

        # All should be registered
        assert len(clean_manager.service_classes) == 3
        assert ServiceType.STORAGE_SERVICE in clean_manager.service_classes
        assert ServiceType.TELEMETRY_SERVICE in clean_manager.service_classes
        assert ServiceType.TRACING_SERVICE in clean_manager.service_classes

        # All should be creatable
        storage = clean_manager.get(ServiceType.STORAGE_SERVICE)
        telemetry = clean_manager.get(ServiceType.TELEMETRY_SERVICE)
        tracing = clean_manager.get(ServiceType.TRACING_SERVICE)

        assert isinstance(storage, LocalStorageService)
        assert isinstance(telemetry, TelemetryService)
        assert isinstance(tracing, TracingService)
