"""Unit tests for exception telemetry."""

import hashlib
import traceback
from unittest.mock import MagicMock

import pytest
from langflow.services.telemetry.schema import ExceptionPayload, RunPayload, VersionPayload
from langflow.services.telemetry.service import TelemetryService


class TestExceptionTelemetry:
    """Unit test suite for exception telemetry functionality."""

    def test_exception_payload_schema(self):
        """Test ExceptionPayload schema creation and serialization."""
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error message",
            exception_context="handler",
            stack_trace_hash="abc123def456",  # pragma: allowlist secret
        )

        # Test serialization with aliases
        data = payload.model_dump(by_alias=True, exclude_none=True)

        expected_fields = {
            "exceptionType": "ValueError",
            "exceptionMessage": "Test error message",
            "exceptionContext": "handler",
            "stackTraceHash": "abc123def456",  # pragma: allowlist secret
        }

        assert data == expected_fields

    @pytest.mark.asyncio
    async def test_log_exception_method(self):
        """Test the log_exception method creates proper payload."""
        # Create a minimal telemetry service for testing
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.do_not_track = False
        telemetry_service._stopping = False
        telemetry_service.client_type = "oss"

        # Mock the _queue_event method to capture calls
        captured_events = []

        async def mock_queue_event(event_tuple):
            captured_events.append(event_tuple)

        telemetry_service._queue_event = mock_queue_event

        # Test exception
        test_exception = RuntimeError("Test exception message")

        # Call log_exception
        await telemetry_service.log_exception(test_exception, "handler")

        # Verify event was queued
        assert len(captured_events) == 1

        _func, payload, path = captured_events[0]

        # Verify payload
        assert isinstance(payload, ExceptionPayload)
        assert payload.exception_type == "RuntimeError"
        assert payload.exception_message == "Test exception message"
        assert payload.exception_context == "handler"
        assert payload.stack_trace_hash is not None
        assert len(payload.stack_trace_hash) == 16  # SHA-256 hash truncated to 16 chars

        # Verify path
        assert path == "exception"

    @pytest.mark.asyncio
    async def test_send_telemetry_data_success(self):
        """Test successful telemetry event emission."""
        # Create minimal service
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }
        telemetry_service.ot = MagicMock()

        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error",
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        # Send telemetry
        await telemetry_service.send_telemetry_data(payload, "exception")

        telemetry_service.ot.emit_event.assert_called_once()
        event_name, attributes = telemetry_service.ot.emit_event.call_args.args
        assert event_name == "exception"
        assert telemetry_service.ot.emit_event.call_args.kwargs == {"error": True}
        assert attributes["exceptionType"] == "ValueError"
        assert attributes["exceptionMessage"] == "Test error"
        assert attributes["exceptionContext"] == "handler"
        assert attributes["stackTraceHash"] == "abc123"
        assert attributes["clientType"] == "oss"
        assert attributes["langflow_version"] == "1.0.0"
        assert attributes["platform"] == "python_package"
        assert attributes["os"] == "linux"
        assert attributes["telemetryPayload"] == "ExceptionPayload"
        assert attributes["telemetryPath"] == "exception"
        assert "timestamp" in attributes

    @pytest.mark.asyncio
    async def test_send_telemetry_data_respects_do_not_track(self):
        """Test that do_not_track setting prevents telemetry."""
        # Create service with do_not_track enabled
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.do_not_track = True
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }
        telemetry_service.ot = MagicMock()

        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error",
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        # Send telemetry - should be blocked
        await telemetry_service.send_telemetry_data(payload, "run")

        telemetry_service.ot.emit_event.assert_not_called()

    def test_stack_trace_hash_consistency(self):
        """Test that same exceptions produce same hash."""

        def create_test_exception():
            try:
                msg = "Consistent test message"
                raise ValueError(msg)
            except ValueError as e:
                return e

        exc1 = create_test_exception()
        exc2 = create_test_exception()

        # Generate hashes the same way as log_exception
        def get_hash(exc):
            stack_trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
            stack_trace_str = "".join(stack_trace)
            return hashlib.sha256(stack_trace_str.encode()).hexdigest()[:16]

        hash1 = get_hash(exc1)
        hash2 = get_hash(exc2)

        # Hashes should be the same for same exception type and location
        assert hash1 == hash2

    def test_build_telemetry_attributes_excludes_common_fields_for_version_payload(self):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

        payload = VersionPayload(
            package="langflow",
            version="1.0.0",
            platform="macOS-15",
            python="3.12",
            arch="arm64",
            auto_login=False,
            cache_type="async",
            backend_only=False,
        )

        attributes = telemetry_service._build_telemetry_attributes(payload, None)

        assert attributes["telemetryPayload"] == "VersionPayload"
        assert attributes["package"] == "langflow"
        assert attributes["version"] == "1.0.0"
        assert "langflow_version" not in attributes
        assert "telemetryPath" not in attributes
        assert "timestamp" in attributes

    @pytest.mark.asyncio
    async def test_send_telemetry_data_marks_failed_payload_as_error(self):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }
        telemetry_service.ot = MagicMock()

        payload = RunPayload(
            run_seconds=1,
            run_success=False,
            run_error_message="failed",
        )

        await telemetry_service.send_telemetry_data(payload, "exception")

        assert telemetry_service.ot.emit_event.call_args.kwargs == {"error": True}

    @pytest.mark.asyncio
    async def test_send_telemetry_data_handles_special_and_unicode_characters(self):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }
        telemetry_service.ot = MagicMock()

        message = "Error with special chars: &?=#@!$%^&*() 世界"
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message=message,
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        await telemetry_service.send_telemetry_data(payload, "exception")

        _, attributes = telemetry_service.ot.emit_event.call_args.args
        assert attributes["exceptionMessage"] == message
