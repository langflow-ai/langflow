"""Unit tests for exception telemetry."""

import hashlib
import traceback
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.services.telemetry.schema import (
    ComponentPayload,
    DeploymentPayload,
    ExceptionPayload,
    PlaygroundPayload,
    RunPayload,
)
from langflow.services.telemetry.service import TelemetryService
from lfx.services.telemetry.identity import get_hashed_user_id


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
        telemetry_service.base_url = "https://api.segment.test/v1/track"
        telemetry_service.segment_write_key = "segment-test-key"
        telemetry_service.anonymous_id = "test-installation"
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
        mock_client.post.return_value = mock_response
        telemetry_service.client = mock_client

        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error",
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        # Send telemetry
        user_id = get_hashed_user_id("alice")
        await telemetry_service.send_telemetry_data(payload, "exception", user_id)

        # Verify HTTP call was made
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        # Check URL
        assert call_args[0][0] == "https://api.segment.test/v1/track"
        assert call_args[1]["auth"] == ("segment-test-key", "")

        body = call_args[1]["json"]
        assert body["anonymousId"] == "test-installation"
        assert body["userId"] == get_hashed_user_id(f"test-installation:{user_id}")
        assert body["event"] == "Ended Process"
        assert body["messageId"]
        assert body["properties"]["exceptionType"] == "ValueError"
        assert "exceptionMessage" not in body["properties"]
        assert body["properties"]["exceptionContext"] == "handler"
        assert body["properties"]["stackTraceHash"] == "abc123"
        assert body["properties"]["clientType"] == "oss"
        assert body["properties"]["langflow_version"] == "1.0.0"
        assert body["properties"]["platform"] == "python_package"
        assert body["properties"]["os"] == "linux"
        assert body["properties"]["UT30"] == "30AS5"
        assert body["properties"]["productCode"] == "WW3151"
        assert body["properties"]["productCodeType"] == "WWPC"
        assert body["properties"]["productPlanName"] == "opensource"
        assert body["properties"]["productPlanType"] == "freemium"
        assert body["properties"]["productTitle"] == "Langflow"
        assert body["properties"]["instanceId"] == "test-installation"
        assert body["properties"]["subscriptionId"] == "test-installation"
        assert body["properties"]["object"] == "exception"
        assert body["properties"]["processType"] == "Langflow Exception"
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_named_user_id_is_scoped_to_installation(self):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://api.segment.test/v1/track"
        telemetry_service.segment_write_key = "segment-test-key"
        telemetry_service.anonymous_id = "installation-a"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {}
        telemetry_service.client = AsyncMock()
        telemetry_service.client.post.return_value.status_code = 200
        payload = RunPayload(run_seconds=1, run_success=True)
        opaque_user_id = get_hashed_user_id("alice@example.com")

        await telemetry_service.send_telemetry_data(payload, "run", opaque_user_id)
        first_user_id = telemetry_service.client.post.call_args.kwargs["json"]["userId"]
        telemetry_service.anonymous_id = "installation-b"
        await telemetry_service.send_telemetry_data(payload, "run", opaque_user_id)
        second_user_id = telemetry_service.client.post.call_args.kwargs["json"]["userId"]

        assert first_user_id == get_hashed_user_id(f"installation-a:{opaque_user_id}")
        assert second_user_id == get_hashed_user_id(f"installation-b:{opaque_user_id}")
        assert first_user_id != second_user_id

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("payload", "path", "message_field", "retained_field"),
        [
            (
                RunPayload(run_seconds=1, run_success=False, run_error_message="user input"),
                "run",
                "runErrorMessage",
                "runSuccess",
            ),
            (
                DeploymentPayload(
                    deployment_action="create",
                    deployment_provider="test",
                    deployment_seconds=1,
                    deployment_success=False,
                    deployment_error_message="SQL parameters",
                ),
                "deployment",
                "deploymentErrorMessage",
                "deploymentSuccess",
            ),
            (
                PlaygroundPayload(
                    playground_seconds=1,
                    playground_success=False,
                    playground_error_message="prompt text",
                ),
                "playground",
                "playgroundErrorMessage",
                "playgroundSuccess",
            ),
            (
                ComponentPayload(
                    component_name="Test",
                    component_id="test-id",
                    component_seconds=1,
                    component_success=False,
                    component_error_message="stored value",
                ),
                "component",
                "componentErrorMessage",
                "componentSuccess",
            ),
            (
                ExceptionPayload(
                    exception_type="ValueError",
                    exception_message="SQL statement and parameters",
                    exception_context="handler",
                    stack_trace_hash="abc123",
                ),
                "exception",
                "exceptionMessage",
                "exceptionType",
            ),
        ],
    )
    async def test_send_telemetry_data_removes_free_form_error_text(self, payload, path, message_field, retained_field):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://api.segment.test/v1/track"
        telemetry_service.segment_write_key = "segment-test-key"
        telemetry_service.anonymous_id = "test-installation"
        telemetry_service.do_not_track = False
        telemetry_service.client_type = "oss"
        telemetry_service.common_telemetry_fields = {}
        telemetry_service.client = AsyncMock()
        telemetry_service.client.post.return_value.status_code = 200

        await telemetry_service.send_telemetry_data(payload, path)

        properties = telemetry_service.client.post.call_args.kwargs["json"]["properties"]
        assert message_field not in properties
        assert retained_field in properties

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
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_telemetry_data_requires_segment_write_key(self):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.segment_write_key = None
        telemetry_service.do_not_track = False
        telemetry_service.client = AsyncMock()

        payload = ExceptionPayload(
            exception_type="ValueError",
            exception_message="Test error",
            exception_context="handler",
            stack_trace_hash="abc123",
        )

        await telemetry_service.send_telemetry_data(payload, "exception")

        telemetry_service.client.post.assert_not_called()

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
    async def test_sensitive_error_text_is_not_exported(self):
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://mock-telemetry.example.com"
        telemetry_service.segment_write_key = "segment-test-key"
        telemetry_service.anonymous_id = "test-installation"
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
        mock_client.post.return_value.status_code = 200
        telemetry_service.client = mock_client

        await telemetry_service.send_telemetry_data(payload, "exception")

        # Verify HTTP call was made
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        sensitive_patterns = ["secret123", "sk-abc123", "xyz789"]
        for pattern in sensitive_patterns:
            assert pattern not in str(call_args), f"Sensitive data '{pattern}' found in telemetry request"
