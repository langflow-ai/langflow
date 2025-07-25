"""Unit tests for exception telemetry."""

import hashlib
import traceback
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.services.telemetry.schema import ExceptionPayload
from langflow.services.telemetry.service import TelemetryService


class TestExceptionTelemetry:
    """Unit test suite for exception telemetry functionality."""

    def test_exception_payload_schema(self):
        """Test ExceptionPayload schema creation and serialization."""
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error message",
            exception_context="handler",
            stack_trace_hash="abc123def456",
        )

        # Test serialization with aliases
        data = payload.model_dump(by_alias=True, exclude_none=True)

        expected_fields = {
            "exceptionType": "ValueError",
            "exceptionMessage": "Test error message",
            "exceptionContext": "handler",
            "stackTraceHash": "abc123def456",
        }

        assert data == expected_fields

    @pytest.mark.asyncio
    async def test_log_exception_method(self):
        """Test the log_exception method creates proper payload."""
        # Create a minimal telemetry service for testing
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.do_not_track = False
        telemetry_service._stopping = False

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

        func, payload, path = captured_events[0]

        # Verify payload
        assert isinstance(payload, ExceptionPayload)
        assert payload.exception_type == "RuntimeError"
        assert payload.exception_message == "Test exception message"
        assert payload.exception_context == "handler"
        assert payload.stack_trace_hash is not None
        assert len(payload.stack_trace_hash) == 16  # MD5 hash truncated to 16 chars

        # Verify path
        assert path == "exception"

    @pytest.mark.asyncio
    async def test_send_telemetry_data_success(self):
        """Test successful telemetry data sending."""
        # Create minimal service
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://langflow.gateway.scarf.sh"
        telemetry_service.do_not_track = False

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        telemetry_service.client = mock_client

        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error",
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        # Send telemetry
        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify HTTP call was made
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args

        # Check URL
        assert call_args[0][0] == "https://langflow.gateway.scarf.sh/exception"

        # Check query parameters
        expected_params = {
            "exceptionType": "ValueError",
            "exceptionMessage": "Test error",
            "exceptionContext": "handler",
            "stackTraceHash": "abc123",
        }
        assert call_args[1]["params"] == expected_params

    @pytest.mark.asyncio
    async def test_send_telemetry_data_respects_do_not_track(self):
        """Test that do_not_track setting prevents telemetry."""
        # Create service with do_not_track enabled
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://langflow.gateway.scarf.sh"
        telemetry_service.do_not_track = True

        # Mock HTTP client
        mock_client = AsyncMock()
        telemetry_service.client = mock_client

        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error",
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        # Send telemetry - should be blocked
        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify no HTTP call was made
        mock_client.get.assert_not_called()

    def test_stack_trace_hash_consistency(self):
        """Test that same exceptions produce same hash."""

        def create_test_exception():
            try:
                raise ValueError("Consistent test message")
            except Exception as e:
                return e

        exc1 = create_test_exception()
        exc2 = create_test_exception()

        # Generate hashes the same way as log_exception
        def get_hash(exc):
            stack_trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
            stack_trace_str = "".join(stack_trace)
            return hashlib.md5(stack_trace_str.encode()).hexdigest()[:16]

        hash1 = get_hash(exc1)
        hash2 = get_hash(exc2)

        # Hashes should be the same for same exception type and location
        assert hash1 == hash2
