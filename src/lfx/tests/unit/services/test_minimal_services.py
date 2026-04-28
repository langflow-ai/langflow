"""Tests for minimal service implementations in LFX."""

import os

import pytest
from lfx.services.storage.local import LocalStorageService
from lfx.services.telemetry.service import TelemetryService
from lfx.services.tracing.service import TracingService
from lfx.services.variable.service import VariableService


class TestLocalStorageService:
    """Tests for LocalStorageService."""

    @pytest.fixture
    def storage(self, mock_session_service, mock_settings_service):
        """Create a storage service with temp directory."""
        return LocalStorageService(mock_session_service, mock_settings_service)

    @pytest.mark.asyncio
    async def test_save_and_get_file(self, storage):
        """Test saving and retrieving a file."""
        data = b"test content"
        await storage.save_file("flow_123", "test.txt", data)

        retrieved = await storage.get_file("flow_123", "test.txt")
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_list_files(self, storage):
        """Test listing files in a flow."""
        await storage.save_file("flow_123", "file1.txt", b"content1")
        await storage.save_file("flow_123", "file2.txt", b"content2")

        files = await storage.list_files("flow_123")
        assert len(files) == 2
        assert "file1.txt" in files
        assert "file2.txt" in files

    @pytest.mark.asyncio
    async def test_delete_file(self, storage):
        """Test deleting a file."""
        await storage.save_file("flow_123", "test.txt", b"content")
        await storage.delete_file("flow_123", "test.txt")

        with pytest.raises(FileNotFoundError):
            await storage.get_file("flow_123", "test.txt")

    @pytest.mark.asyncio
    async def test_get_file_size(self, storage):
        """Test getting file size."""
        data = b"test content"
        await storage.save_file("flow_123", "test.txt", data)

        size = await storage.get_file_size("flow_123", "test.txt")
        assert size == len(data)

    @pytest.mark.asyncio
    async def test_get_nonexistent_file(self, storage):
        """Test getting a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            await storage.get_file("flow_123", "nonexistent.txt")

    def test_build_full_path(self, storage, mock_settings_service):
        """Test building full file path."""
        path = storage.build_full_path("flow_123", "test.txt")
        config_dir = mock_settings_service.settings.config_dir
        expected = f"{config_dir}/flow_123/test.txt"
        assert path == expected

    @pytest.mark.asyncio
    async def test_list_files_empty_flow(self, storage):
        """Test listing files in nonexistent flow."""
        files = await storage.list_files("nonexistent_flow")
        assert files == []

    def test_service_ready(self, storage):
        """Test that service is marked as ready."""
        assert storage.ready is True
        assert storage.name == "storage_service"

    @pytest.mark.asyncio
    async def test_teardown(self, storage):
        """Test service teardown."""
        await storage.teardown()
        # Should not raise


class TestTelemetryService:
    """Tests for TelemetryService."""

    @pytest.fixture
    def telemetry(self):
        """Create a telemetry service with do_not_track so it doesn't hit the network."""
        return TelemetryService(do_not_track=True)

    def test_service_ready(self, telemetry):
        """Test that service is ready."""
        assert telemetry.ready is True
        assert telemetry.name == "telemetry_service"

    def test_do_not_track_from_env(self):
        """Test DO_NOT_TRACK env var is respected."""
        os.environ["DO_NOT_TRACK"] = "1"
        try:
            svc = TelemetryService()
            assert svc.do_not_track is True
        finally:
            del os.environ["DO_NOT_TRACK"]

    def test_start_skipped_when_do_not_track(self, telemetry):
        """Start is a no-op when do_not_track is set."""
        telemetry.start()
        assert telemetry._running is False
        assert telemetry._worker_task is None
        assert telemetry._client is None

    @pytest.mark.asyncio
    async def test_start_and_stop_lifecycle(self):
        """Test that start creates worker/client and stop cleans them up."""
        svc = TelemetryService(base_url="http://localhost:0")
        svc.start()
        assert svc._running is True
        assert svc._worker_task is not None
        assert svc._client is not None

        await svc.stop()
        assert svc._running is False
        assert svc._client is None

    @pytest.mark.asyncio
    async def test_enqueue_skipped_when_do_not_track(self, telemetry):
        """Enqueue is a no-op when do_not_track is set."""
        from lfx.services.telemetry.schema import MCPToolPayload

        await telemetry.log_mcp_tool(MCPToolPayload(tool="test", success=True, ms=5))
        assert telemetry._queue.empty()

    @pytest.mark.asyncio
    async def test_flush_when_do_not_track(self, telemetry):
        """Flush should not raise when do_not_track is set."""
        await telemetry.flush()

    @pytest.mark.asyncio
    async def test_log_exception(self, telemetry):
        """Test logging an exception."""
        exc = ValueError("test error")
        await telemetry.log_exception(exc, "test_context")

    @pytest.mark.asyncio
    async def test_log_package_version(self, telemetry):
        """Test logging package version."""
        await telemetry.log_package_version()

    @pytest.mark.asyncio
    async def test_teardown(self, telemetry):
        """Test service teardown."""
        await telemetry.teardown()

    @pytest.mark.asyncio
    async def test_teardown_after_start(self):
        """Test that teardown properly stops a started service."""
        svc = TelemetryService(base_url="http://localhost:0")
        svc.start()
        assert svc._running is True
        await svc.teardown()
        assert svc._running is False
        assert svc._client is None


class TestTracingService:
    """Tests for minimal TracingService."""

    @pytest.fixture
    def tracing(self):
        """Create a tracing service."""
        return TracingService()

    def test_service_ready(self, tracing):
        """Test that service is ready."""
        assert tracing.ready is True
        assert tracing.name == "tracing_service"

    def test_add_log(self, tracing):
        """Test adding a log entry (outputs to debug)."""
        # Should not raise
        tracing.add_log("test_trace", {"message": "test log"})

    @pytest.mark.asyncio
    async def test_teardown(self, tracing):
        """Test service teardown."""
        await tracing.teardown()
        # Should not raise


class TestVariableService:
    """Tests for minimal VariableService."""

    @pytest.fixture
    def variables(self):
        """Create a variable service."""
        return VariableService()

    def test_service_ready(self, variables):
        """Test that service is ready."""
        assert variables.ready is True
        assert variables.name == "variable_service"

    def test_set_and_get_variable(self, variables):
        """Test setting and getting a variable."""
        variables.set_variable("test_key", "test_value")
        value = variables.get_variable("test_key")
        assert value == "test_value"

    def test_get_from_environment(self, variables):
        """Test getting variable from environment."""
        os.environ["TEST_ENV_VAR"] = "env_value"
        try:
            value = variables.get_variable("TEST_ENV_VAR")
            assert value == "env_value"
        finally:
            del os.environ["TEST_ENV_VAR"]

    def test_get_nonexistent_variable(self, variables):
        """Test getting a variable that doesn't exist."""
        value = variables.get_variable("nonexistent_key")
        assert value is None

    def test_delete_variable(self, variables):
        """Test deleting a variable."""
        variables.set_variable("test_key", "test_value")
        variables.delete_variable("test_key")
        value = variables.get_variable("test_key")
        assert value is None

    def test_list_variables(self, variables):
        """Test listing variables."""
        variables.set_variable("key1", "value1")
        variables.set_variable("key2", "value2")

        vars_list = variables.list_variables()
        assert "key1" in vars_list
        assert "key2" in vars_list

    def test_in_memory_overrides_env(self, variables):
        """Test that in-memory variables override environment."""
        os.environ["TEST_VAR"] = "env_value"
        try:
            variables.set_variable("TEST_VAR", "memory_value")
            value = variables.get_variable("TEST_VAR")
            assert value == "memory_value"
        finally:
            del os.environ["TEST_VAR"]

    @pytest.mark.asyncio
    async def test_teardown(self, variables):
        """Test service teardown clears variables."""
        variables.set_variable("test_key", "test_value")
        await variables.teardown()
        # Variables should be cleared (verify via public API)
        assert variables.list_variables() == []
        assert variables.get_variable("test_key") is None


class TestMinimalServicesIntegration:
    """Integration tests for minimal services working together."""

    @pytest.mark.asyncio
    async def test_all_minimal_services_initialize(self, mock_session_service, mock_settings_service):
        """Test that all minimal services can be initialized."""
        storage = LocalStorageService(mock_session_service, mock_settings_service)
        telemetry = TelemetryService()
        tracing = TracingService()
        variables = VariableService()

        assert storage.ready
        assert telemetry.ready
        assert tracing.ready
        assert variables.ready

    @pytest.mark.asyncio
    async def test_minimal_services_teardown_all(self, mock_session_service, mock_settings_service):
        """Test tearing down all minimal services."""
        storage = LocalStorageService(mock_session_service, mock_settings_service)
        telemetry = TelemetryService()
        tracing = TracingService()
        variables = VariableService()

        # Should all teardown without errors
        await storage.teardown()
        await telemetry.teardown()
        await tracing.teardown()
        await variables.teardown()

    @pytest.mark.asyncio
    async def test_storage_with_tracing(self, mock_session_service, mock_settings_service):
        """Test using storage with tracing."""
        storage = LocalStorageService(mock_session_service, mock_settings_service)
        tracing = TracingService()

        tracing.add_log("storage_test", {"operation": "save", "flow_id": "123"})
        await storage.save_file("flow_123", "test.txt", b"content")
        tracing.add_log("storage_test", {"operation": "saved", "flow_id": "123"})

        # Should complete without errors
        assert await storage.get_file("flow_123", "test.txt") == b"content"
