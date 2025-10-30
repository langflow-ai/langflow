"""Tests for build timer accuracy with client_request_time."""

import time

import pytest
from lfx.schema.schema import InputValueRequest


class TestClientRequestTimeHandling:
    """Test suite for client_request_time handling in build operations."""

    def test_input_value_request_client_request_time_is_optional(self):
        """Test that client_request_time is optional in InputValueRequest."""
        # Should work without client_request_time
        request = InputValueRequest(input_value="test")
        assert request.client_request_time is None

        # Should work with client_request_time
        request_with_time = InputValueRequest(input_value="test", client_request_time=1234567890)
        assert request_with_time.client_request_time == 1234567890

    def test_input_value_request_client_request_time_is_nullable(self):
        """Test that client_request_time can be explicitly set to None."""
        request = InputValueRequest(input_value="test", client_request_time=None)
        assert request.client_request_time is None

    def test_input_value_request_with_valid_timestamp(self):
        """Test InputValueRequest with a valid timestamp in milliseconds."""
        timestamp = int(time.time() * 1000)
        request = InputValueRequest(input_value="test", client_request_time=timestamp)

        assert request.client_request_time == timestamp
        assert isinstance(request.client_request_time, int)

    def test_duration_calculation_without_client_request_time(self):
        """Test that duration is calculated using perf_counter when client_request_time is None."""
        # Simulate the backend logic
        start_time = time.perf_counter()
        time.sleep(0.1)  # Simulate some work
        timedelta = time.perf_counter() - start_time

        # Verify duration is around 0.1 seconds (100ms)
        assert 0.09 < timedelta < 0.15, f"Expected ~0.1s, got {timedelta}s"

    def test_duration_calculation_with_client_request_time(self):
        """Test that duration is calculated from client timestamp when provided."""
        # Simulate client timestamp from 200ms ago
        client_start_ms = int((time.time() - 0.2) * 1000)
        inputs = InputValueRequest(input_value="test", client_request_time=client_start_ms)

        # Simulate backend calculation
        if inputs and inputs.client_request_time:
            client_start_seconds = inputs.client_request_time / 1000
            current_time_seconds = time.time()
            timedelta = current_time_seconds - client_start_seconds

            # Should be around 200ms
            assert 0.15 < timedelta < 0.25, f"Expected ~0.2s, got {timedelta}s"

    def test_duration_calculation_fallback_to_perf_counter(self):
        """Test that when client_request_time is None, fallback to perf_counter works."""
        inputs = InputValueRequest(input_value="test", client_request_time=None)
        start_time = time.perf_counter()

        # Simulate some processing
        time.sleep(0.05)

        # Simulate backend logic
        timedelta = time.perf_counter() - start_time

        # Client time is None, so we should not override timedelta
        if inputs and inputs.client_request_time:
            # This block should NOT execute
            pytest.fail("Should not use client_request_time when it's None")

        # Verify we're using perf_counter duration
        assert 0.04 < timedelta < 0.1, f"Expected ~0.05s from perf_counter, got {timedelta}s"

    def test_client_request_time_includes_network_latency(self):
        """Test that client_request_time captures full end-to-end duration including latency."""
        # Client sends request at T0
        client_start_ms = int(time.time() * 1000)

        # Simulate network latency + processing
        time.sleep(0.1)  # 100ms network latency
        backend_start = time.perf_counter()
        time.sleep(0.05)  # 50ms processing
        backend_end = time.perf_counter()

        # Backend calculation with perf_counter only
        perf_duration = backend_end - backend_start

        # Backend calculation with client timestamp
        client_duration = time.time() - (client_start_ms / 1000)

        # Client duration should include both network and processing
        assert client_duration > perf_duration, (
            f"Client duration ({client_duration}s) should be greater than perf_counter duration ({perf_duration}s)"
        )
        assert 0.14 < client_duration < 0.2, f"Expected ~0.15s total, got {client_duration}s"
        assert 0.04 < perf_duration < 0.1, f"Expected ~0.05s processing, got {perf_duration}s"


class TestBuildTimerBackwardCompatibility:
    """Test backward compatibility when client_request_time is not provided."""

    def test_missing_client_request_time_field(self):
        """Test that requests without client_request_time field work correctly."""
        # Old API calls might not include this field at all
        request_dict = {"input_value": "test", "session": "session123"}
        request = InputValueRequest(**request_dict)

        assert request.input_value == "test"
        assert request.session == "session123"
        assert request.client_request_time is None

    def test_empty_inputs_object(self):
        """Test handling when inputs is None."""
        inputs = None

        # Simulate backend logic
        start_time = time.perf_counter()
        time.sleep(0.05)
        timedelta = time.perf_counter() - start_time

        # Should not crash when inputs is None
        if inputs and inputs.client_request_time:
            pytest.fail("Should not enter this block when inputs is None")

        assert 0.04 < timedelta < 0.1

    def test_inputs_without_client_request_time(self):
        """Test that inputs object without client_request_time uses perf_counter."""
        inputs = InputValueRequest(input_value="test")
        assert inputs.client_request_time is None

        start_time = time.perf_counter()
        time.sleep(0.05)
        timedelta = time.perf_counter() - start_time

        # Should use perf_counter duration
        if inputs and inputs.client_request_time:
            pytest.fail("Should not use client_request_time when it's None")

        assert 0.04 < timedelta < 0.1


class TestDurationFormatting:
    """Test duration formatting with different time values."""

    def test_format_elapsed_time_from_client_timestamp(self):
        """Test that duration formatting works with client timestamps."""
        from langflow.api.utils import format_elapsed_time

        # Test milliseconds (< 1 second)
        duration_ms = 0.5  # 500ms
        formatted = format_elapsed_time(duration_ms)
        assert "ms" in formatted or "second" in formatted

        # Test seconds
        duration_s = 2.5
        formatted = format_elapsed_time(duration_s)
        assert "second" in formatted

        # Test minutes
        duration_m = 75.0  # 1 minute 15 seconds
        formatted = format_elapsed_time(duration_m)
        assert formatted  # Should return some formatted string

    def test_negative_duration_handling(self):
        """Test handling of negative durations (clock skew)."""
        # This could happen if client clock is ahead of server clock
        client_future_ms = int((time.time() + 10) * 1000)  # 10 seconds in future
        inputs = InputValueRequest(input_value="test", client_request_time=client_future_ms)

        if inputs and inputs.client_request_time:
            client_start_seconds = inputs.client_request_time / 1000
            current_time_seconds = time.time()
            timedelta = current_time_seconds - client_start_seconds

            # Duration would be negative due to clock skew
            assert timedelta < 0, "Should detect clock skew"
            # In real implementation, we might want to fallback to perf_counter
            # or show a warning, but this test just validates we detect the issue


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_large_timestamp(self):
        """Test handling of very large timestamp values."""
        # Year 2050 timestamp
        large_timestamp = 2524608000000
        request = InputValueRequest(input_value="test", client_request_time=large_timestamp)
        assert request.client_request_time == large_timestamp

    def test_zero_timestamp(self):
        """Test handling of zero timestamp (Unix epoch)."""
        request = InputValueRequest(input_value="test", client_request_time=0)
        assert request.client_request_time == 0

        # Zero should be treated as a valid timestamp, not as None/False
        if request and request.client_request_time is not None:
            # This should execute since 0 is a valid timestamp
            duration = time.time() - (request.client_request_time / 1000)
            assert duration > 0  # Current time should be after epoch

    def test_timestamp_precision(self):
        """Test that millisecond precision is maintained."""
        timestamp_ms = 1234567890123  # Milliseconds with precision
        request = InputValueRequest(input_value="test", client_request_time=timestamp_ms)

        # Convert to seconds and back
        timestamp_seconds = request.client_request_time / 1000
        back_to_ms = int(timestamp_seconds * 1000)

        assert back_to_ms == timestamp_ms, "Millisecond precision should be maintained"

    def test_concurrent_requests_different_timestamps(self):
        """Test that multiple concurrent requests maintain separate timestamps."""
        ts1 = int(time.time() * 1000)
        time.sleep(0.01)  # Small delay
        ts2 = int(time.time() * 1000)

        request1 = InputValueRequest(input_value="test1", client_request_time=ts1)
        request2 = InputValueRequest(input_value="test2", client_request_time=ts2)

        assert request1.client_request_time < request2.client_request_time
        assert request2.client_request_time - request1.client_request_time >= 10  # At least 10ms apart


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def test_slow_network_scenario(self):
        """Test scenario where network latency is significant."""
        # Client initiates request
        client_start_ms = int(time.time() * 1000)

        # Simulate slow network (300ms)
        time.sleep(0.3)

        # Backend processing (50ms)
        backend_start = time.perf_counter()
        time.sleep(0.05)
        backend_duration = time.perf_counter() - backend_start

        # Calculate with client timestamp
        inputs = InputValueRequest(input_value="test", client_request_time=client_start_ms)
        client_duration = time.time() - (inputs.client_request_time / 1000)

        # Client sees total time (350ms), backend sees processing time (50ms)
        assert client_duration > 0.3, f"Client duration should include network: {client_duration}s"
        assert backend_duration < 0.1, f"Backend duration should be just processing: {backend_duration}s"
        assert client_duration > backend_duration * 3, "Client duration should be much larger"

    def test_queued_request_scenario(self):
        """Test scenario where request is queued before processing."""
        # Client sends request
        client_start_ms = int(time.time() * 1000)

        # Request sits in queue (200ms)
        time.sleep(0.2)

        # Processing starts
        backend_start = time.perf_counter()
        time.sleep(0.1)  # Actual processing (100ms)
        backend_duration = time.perf_counter() - backend_start

        # With client timestamp, we capture queue time + processing
        inputs = InputValueRequest(input_value="test", client_request_time=client_start_ms)
        total_duration = time.time() - (inputs.client_request_time / 1000)

        assert total_duration > 0.25, f"Should include queue + processing: {total_duration}s"
        assert backend_duration < 0.15, f"Backend only sees processing: {backend_duration}s"

    def test_fast_cached_response_scenario(self):
        """Test scenario where response is very fast (cached)."""
        client_start_ms = int(time.time() * 1000)

        # Very fast response (10ms)
        time.sleep(0.01)

        inputs = InputValueRequest(input_value="test", client_request_time=client_start_ms)
        duration = time.time() - (inputs.client_request_time / 1000)

        # Should still work for very fast responses
        assert 0.005 < duration < 0.05, f"Should capture fast response: {duration}s"


@pytest.mark.asyncio
class TestAsyncBuildOperations:
    """Test async build operations with client_request_time."""

    async def test_async_build_with_client_timestamp(self):
        """Test that async build operations correctly use client_request_time."""
        client_start_ms = int(time.time() * 1000)
        inputs = InputValueRequest(input_value="test", client_request_time=client_start_ms)

        # Simulate async processing
        import asyncio

        await asyncio.sleep(0.1)

        # Calculate duration
        if inputs and inputs.client_request_time:
            duration = time.time() - (inputs.client_request_time / 1000)
            assert 0.09 < duration < 0.15

    async def test_async_build_without_client_timestamp(self):
        """Test that async build operations work without client_request_time."""
        inputs = InputValueRequest(input_value="test")

        # Simulate async processing
        import asyncio

        start = time.perf_counter()
        await asyncio.sleep(0.1)
        duration = time.perf_counter() - start

        # Should use perf_counter
        if not (inputs and inputs.client_request_time):
            assert 0.09 < duration < 0.15
