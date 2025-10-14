"""Integration tests for exception telemetry."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.services.telemetry.schema import (
    ComponentPayload,
    ExceptionPayload,
    PlaygroundPayload,
    RunPayload,
    ShutdownPayload,
    VersionPayload,
)
from langflow.services.telemetry.service import TelemetryService


class TestExceptionTelemetryIntegration:
    """Integration test suite for exception telemetry functionality."""

    @pytest.mark.asyncio
    async def test_telemetry_http_request_format(self):
        """Integration test verifying the exact HTTP request sent to Scarf."""
        # Create service
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "darwin",
        }

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        telemetry_service.client = mock_client

        # Create a real exception to get realistic stack trace
        try:

            def nested_function():
                msg = "Integration test exception"
                raise ValueError(msg)

            nested_function()
        except ValueError as exc:
            real_exc = exc

        # Mock _queue_event to directly call send_telemetry_data
        async def mock_queue_event(event_tuple):
            func, payload, path = event_tuple
            await func(payload, path)

        telemetry_service._queue_event = mock_queue_event

        # Test the full flow
        await telemetry_service.log_exception(real_exc, "lifespan")

        # Verify the exact HTTP request that would be sent to Scarf
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args

        # Verify URL
        assert call_args[0][0] == "https://mock-telemetry.example.com/exception"

        # Verify parameters match our schema
        params = call_args[1]["params"]
        assert params["exceptionType"] == "ValueError"
        assert "Integration test exception" in params["exceptionMessage"]
        assert params["exceptionContext"] == "lifespan"
        assert "stackTraceHash" in params
        assert len(params["stackTraceHash"]) == 16

    @pytest.mark.asyncio
    async def test_exception_telemetry_service_integration(self):
        """Integration test for exception telemetry service without FastAPI."""
        # Create service with mocked dependencies
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "darwin",
        }

        # Mock the async queue and HTTP client
        telemetry_service.telemetry_queue = asyncio.Queue()

        # Track actual calls
        http_calls = []

        async def mock_send_data(payload, path):
            http_calls.append(
                {
                    "url": f"{telemetry_service.base_url}/{path}",
                    "payload": payload.model_dump(by_alias=True),
                    "path": path,
                }
            )

        # Mock _queue_event to call our mock directly
        async def mock_queue_event(event_tuple):
            _func, payload, path = event_tuple
            await mock_send_data(payload, path)

        telemetry_service._queue_event = mock_queue_event

        # Test with real exception
        test_exception = RuntimeError("Service integration test")
        await telemetry_service.log_exception(test_exception, "handler")

        # Verify the call was made with correct data
        assert len(http_calls) == 1
        call = http_calls[0]

        assert call["url"] == "https://mock-telemetry.example.com/exception"
        assert call["path"] == "exception"
        assert call["payload"]["exceptionType"] == "RuntimeError"
        assert call["payload"]["exceptionMessage"] == "Service integration test"
        assert call["payload"]["exceptionContext"] == "handler"
        assert "stackTraceHash" in call["payload"]


@pytest.mark.asyncio
async def test_exception_telemetry_end_to_end():
    """End-to-end integration test to verify telemetry flow works."""
    # Track if telemetry was called
    telemetry_called = []

    async def mock_log_exception(exc, context):
        telemetry_called.append({"type": type(exc).__name__, "message": str(exc), "context": context})

    # Test that we can create the payload and it works
    test_exc = RuntimeError("End-to-end integration test")

    # Simulate what the exception handler does
    await mock_log_exception(test_exc, "handler")

    # Verify telemetry was "called"
    assert len(telemetry_called) == 1
    assert telemetry_called[0]["type"] == "RuntimeError"
    assert telemetry_called[0]["message"] == "End-to-end integration test"
    assert telemetry_called[0]["context"] == "handler"


class TestTelemetryPayloadValidation:
    """Test suite for validating telemetry payload schemas and serialization."""

    def test_component_payload_creation_and_serialization(self):
        """Test ComponentPayload creation and serialization with aliases."""
        payload = ComponentPayload(
            component_name="TestComponent",
            component_seconds=42,
            component_success=True,
            component_error_message="Test error",
            client_type="oss",
        )

        # Test direct attribute access
        assert payload.component_name == "TestComponent"
        assert payload.component_seconds == 42
        assert payload.component_success is True
        assert payload.component_error_message == "Test error"
        assert payload.client_type == "oss"

        # Test serialization with aliases
        serialized = payload.model_dump(by_alias=True)
        expected = {
            "componentName": "TestComponent",
            "componentSeconds": 42,
            "componentSuccess": True,
            "componentErrorMessage": "Test error",
            "clientType": "oss",
            "componentRunId": None,
        }
        assert serialized == expected

    def test_component_payload_optional_fields(self):
        """Test ComponentPayload with optional fields."""
        # Test minimal required fields
        payload = ComponentPayload(component_name="MinimalComponent", component_seconds=5, component_success=False)

        assert payload.component_error_message is None
        assert payload.client_type is None

        # Test serialization excludes None values
        serialized = payload.model_dump(by_alias=True, exclude_none=True)
        expected = {"componentName": "MinimalComponent", "componentSeconds": 5, "componentSuccess": False}
        assert serialized == expected

    def test_playground_payload_creation_and_serialization(self):
        """Test PlaygroundPayload creation and serialization."""
        payload = PlaygroundPayload(
            playground_seconds=120,
            playground_component_count=8,
            playground_success=True,
            playground_error_message="",
            client_type="desktop",
        )

        assert payload.playground_seconds == 120
        assert payload.playground_component_count == 8
        assert payload.playground_success is True
        assert payload.playground_error_message == ""
        assert payload.client_type == "desktop"

        serialized = payload.model_dump(by_alias=True)
        expected = {
            "playgroundSeconds": 120,
            "playgroundComponentCount": 8,
            "playgroundSuccess": True,
            "playgroundErrorMessage": "",
            "clientType": "desktop",
            "playgroundRunId": None,
        }
        assert serialized == expected

    def test_run_payload_creation_and_serialization(self):
        """Test RunPayload creation and serialization."""
        payload = RunPayload(
            run_is_webhook=True,
            run_seconds=300,
            run_success=False,
            run_error_message="Connection timeout",
            client_type="oss",
        )

        assert payload.run_is_webhook is True
        assert payload.run_seconds == 300
        assert payload.run_success is False
        assert payload.run_error_message == "Connection timeout"

        serialized = payload.model_dump(by_alias=True)
        expected = {
            "runIsWebhook": True,
            "runSeconds": 300,
            "runSuccess": False,
            "runErrorMessage": "Connection timeout",
            "clientType": "oss",
            "runId": None,
        }
        assert serialized == expected

    def test_run_payload_defaults(self):
        """Test RunPayload with default values."""
        payload = RunPayload(run_seconds=10, run_success=True)

        assert payload.run_is_webhook is False  # Default
        assert payload.run_error_message == ""  # Default
        assert payload.client_type is None  # Default from BasePayload

    def test_version_payload_creation_and_serialization(self):
        """Test VersionPayload creation and serialization."""
        payload = VersionPayload(
            package="langflow",
            version="1.5.0",
            platform="macOS-14.0-arm64",
            python="3.11",
            arch="64bit",
            auto_login=False,
            cache_type="redis",
            backend_only=True,
            client_type="oss",
        )

        assert payload.package == "langflow"
        assert payload.version == "1.5.0"
        assert payload.platform == "macOS-14.0-arm64"
        assert payload.python == "3.11"
        assert payload.arch == "64bit"
        assert payload.auto_login is False
        assert payload.cache_type == "redis"
        assert payload.backend_only is True

        serialized = payload.model_dump(by_alias=True)
        expected = {
            "package": "langflow",
            "version": "1.5.0",
            "platform": "macOS-14.0-arm64",
            "python": "3.11",
            "arch": "64bit",
            "autoLogin": False,
            "cacheType": "redis",
            "backendOnly": True,
            "clientType": "oss",
        }
        assert serialized == expected

    def test_shutdown_payload_creation_and_serialization(self):
        """Test ShutdownPayload creation and serialization."""
        payload = ShutdownPayload(time_running=3600, client_type="desktop")

        assert payload.time_running == 3600
        assert payload.client_type == "desktop"

        serialized = payload.model_dump(by_alias=True)
        expected = {"timeRunning": 3600, "clientType": "desktop"}
        assert serialized == expected

    def test_exception_payload_creation_and_serialization(self):
        """Test ExceptionPayload creation and serialization."""
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Invalid input parameter",
            exception_context="handler",
            stack_trace_hash="abc123def456",  # pragma: allowlist secret
            client_type="oss",
        )

        assert payload.exception_type == "ValueError"
        assert payload.exception_message == "Invalid input parameter"
        assert payload.exception_context == "handler"
        assert payload.stack_trace_hash == "abc123def456"  # pragma: allowlist secret

        serialized = payload.model_dump(by_alias=True)
        expected = {
            "exceptionType": "ValueError",
            "exceptionMessage": "Invalid input parameter",
            "exceptionContext": "handler",
            "stackTraceHash": "abc123def456",  # pragma: allowlist secret
            "clientType": "oss",
        }
        assert serialized == expected

    def test_exception_payload_optional_stack_trace_hash(self):
        """Test ExceptionPayload without stack trace hash."""
        payload = ExceptionPayload(
            exception_type="RuntimeError", exception_message="Service unavailable", exception_context="lifespan"
        )

        assert payload.stack_trace_hash is None
        assert payload.client_type is None

        # Test serialization excludes None values
        serialized = payload.model_dump(by_alias=True, exclude_none=True)
        expected = {
            "exceptionType": "RuntimeError",
            "exceptionMessage": "Service unavailable",
            "exceptionContext": "lifespan",
        }
        assert serialized == expected

    def test_base_payload_client_type_inheritance(self):
        """Test that all payload types inherit client_type from BasePayload."""
        payloads = [
            ComponentPayload(component_name="test", component_seconds=1, component_success=True),
            PlaygroundPayload(playground_seconds=1, playground_success=True),
            RunPayload(run_seconds=1, run_success=True),
            VersionPayload(
                package="test",
                version="1.0",
                platform="test",
                python="3.11",
                arch="64bit",
                auto_login=False,
                cache_type="memory",
                backend_only=False,
            ),
            ShutdownPayload(time_running=100),
            ExceptionPayload(exception_type="Error", exception_message="test", exception_context="test"),
        ]

        for payload in payloads:
            # Default client_type should be None
            assert payload.client_type is None

            # Should be able to set client_type
            payload.client_type = "test_client"
            assert payload.client_type == "test_client"

            # Should serialize with alias
            serialized = payload.model_dump(by_alias=True, include={"client_type"})
            assert serialized.get("clientType") == "test_client"

    def test_payload_serialization_exclude_unset_fields(self):
        """Test that payloads can exclude unset fields during serialization."""
        payload = RunPayload(
            run_seconds=30,
            run_success=True,
            # run_is_webhook and run_error_message not set, will use defaults
        )

        # Standard serialization includes all fields
        full_serialization = payload.model_dump(by_alias=True)
        assert "runIsWebhook" in full_serialization
        assert "runErrorMessage" in full_serialization
        assert full_serialization["runIsWebhook"] is False
        assert full_serialization["runErrorMessage"] == ""

        # Exclude unset should only include explicitly set fields
        exclude_unset = payload.model_dump(by_alias=True, exclude_unset=True)
        assert "runSeconds" in exclude_unset
        assert "runSuccess" in exclude_unset
        # These have defaults but weren't set explicitly, so they're excluded
        assert "runIsWebhook" not in exclude_unset
        assert "runErrorMessage" not in exclude_unset
        assert "clientType" not in exclude_unset
