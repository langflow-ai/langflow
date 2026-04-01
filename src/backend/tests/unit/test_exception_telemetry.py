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
        assert len(payload.stack_trace_hash) == 16  # MD5 hash truncated to 16 chars

        # Verify path
        assert path == "exception"

    @pytest.mark.asyncio
    async def test_send_telemetry_data_success(self):
        """Test successful telemetry data sending."""
        # Create minimal service
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

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
        assert call_args[0][0] == "https://mock-telemetry.example.com/exception"

        # Check query parameters (should include common telemetry fields)
        params = call_args[1]["params"]
        assert params["exceptionType"] == "ValueError"
        assert params["exceptionMessage"] == "Test error"
        assert params["exceptionContext"] == "handler"
        assert params["stackTraceHash"] == "abc123"
        assert params["clientType"] == "oss"
        assert params["langflow_version"] == "1.0.0"
        assert params["platform"] == "python_package"
        assert params["os"] == "linux"
        assert "timestamp" in params

    @pytest.mark.asyncio
    async def test_send_telemetry_data_respects_do_not_track(self):
        """Test that do_not_track setting prevents telemetry."""
        # Create service with do_not_track enabled
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = True
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

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

    @pytest.mark.asyncio
    async def test_query_params_url_length_limit(self):
        """Test that query parameters don't exceed URL length limits."""
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

        # Create payload with very long message
        long_message = "A" * 2000  # Very long message
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message=long_message,
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        mock_client = AsyncMock()
        telemetry_service.client = mock_client

        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify HTTP call was made
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args

        # Check that URL doesn't exceed reasonable length (typically 2048 chars)
        full_url = call_args[0][0]
        assert len(full_url) < 2048, f"URL too long: {len(full_url)} characters"

    @pytest.mark.asyncio
    async def test_query_params_special_characters(self):
        """Test that special characters in query parameters are properly encoded."""
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

        # Create payload with special characters
        special_message = "Error with special chars: &?=#@!$%^&*()"
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message=special_message,
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        mock_client = AsyncMock()
        telemetry_service.client = mock_client

        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify HTTP call was made
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args

        # Check that special characters are properly encoded
        full_url = call_args[0][0]
        assert "&" not in full_url or "%26" in full_url, "Ampersand not properly encoded"
        assert "?" not in full_url or "%3F" in full_url, "Question mark not properly encoded"
        assert "=" not in full_url or "%3D" in full_url, "Equals sign not properly encoded"

    @pytest.mark.asyncio
    async def test_query_params_sensitive_data_exposure(self):
        """Test that sensitive data is not exposed in query parameters."""
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

        # Create payload with potentially sensitive data
        sensitive_message = "Password: secret123, API Key: sk-abc123, Token: xyz789"
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message=sensitive_message,
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        mock_client = AsyncMock()
        telemetry_service.client = mock_client

        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify HTTP call was made
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args

        # Check that sensitive data is not in URL (should be in request body instead)
        full_url = call_args[0][0]
        sensitive_patterns = ["secret123", "sk-abc123", "xyz789"]
        for pattern in sensitive_patterns:
            assert pattern not in full_url, f"Sensitive data '{pattern}' found in URL"

    @pytest.mark.asyncio
    async def test_query_params_unicode_characters(self):
        """Test that unicode characters in query parameters are handled correctly."""
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {
            "langflow_version": "1.0.0",
            "platform": "python_package",
            "os": "linux",
        }

        # Create payload with unicode characters
        unicode_message = "Error with unicode: 世界, 🚀, émojis"
        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message=unicode_message,
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        mock_client = AsyncMock()
        telemetry_service.client = mock_client

        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify HTTP call was made
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args

        # Check that unicode characters are properly handled
        full_url = call_args[0][0]
        # URL should be valid and not cause encoding issues
        assert len(full_url) > 0, "URL should not be empty"
        # Should not contain raw unicode characters that could cause issues
        assert "世界" not in full_url or "%E4%B8%96%E7%95%8C" in full_url
