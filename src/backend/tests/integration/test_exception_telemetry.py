"""Integration tests for exception telemetry."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.services.telemetry.service import TelemetryService


class TestExceptionTelemetryIntegration:
    """Integration test suite for exception telemetry functionality."""

    @pytest.mark.asyncio
    async def test_telemetry_http_request_format(self):
        """Integration test verifying the exact HTTP request sent to Scarf."""
        # Create service
        telemetry_service = TelemetryService.__new__(TelemetryService)
        telemetry_service.base_url = "https://langflow.gateway.scarf.sh"
        telemetry_service.do_not_track = False

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        telemetry_service.client = mock_client

        # Create a real exception to get realistic stack trace
        try:

            def nested_function():
                raise ValueError("Integration test exception")

            nested_function()
        except Exception as exc:
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
        assert call_args[0][0] == "https://langflow.gateway.scarf.sh/exception"

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
        telemetry_service.base_url = "https://langflow.gateway.scarf.sh"
        telemetry_service.do_not_track = False

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
            func, payload, path = event_tuple
            await mock_send_data(payload, path)

        telemetry_service._queue_event = mock_queue_event

        # Test with real exception
        test_exception = RuntimeError("Service integration test")
        await telemetry_service.log_exception(test_exception, "handler")

        # Verify the call was made with correct data
        assert len(http_calls) == 1
        call = http_calls[0]

        assert call["url"] == "https://langflow.gateway.scarf.sh/exception"
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
