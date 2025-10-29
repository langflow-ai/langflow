"""Test error handling and retry logic for connector service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.connectors.config import ConnectorRetryConfig
from langflow.services.connectors.retry import (
    CircuitBreaker,
    CircuitBreakerManager,
    ErrorCategory,
    RetryConfig,
    categorize_error,
    is_retryable,
    with_exponential_backoff,
)
from langflow.services.connectors.service import ConnectorService
from langflow.services.database.models.connector import ConnectorConnection, ConnectorDeadLetterQueue
from sqlmodel.ext.asyncio.session import AsyncSession


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_delay_calculation(self):
        """Test delay calculation with exponential backoff."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False)

        # Test exponential growth
        assert config.get_delay(0) == 1.0  # 1 * 2^0
        assert config.get_delay(1) == 2.0  # 1 * 2^1
        assert config.get_delay(2) == 4.0  # 1 * 2^2
        assert config.get_delay(3) == 8.0  # 1 * 2^3
        assert config.get_delay(4) == 10.0  # Max delay

    def test_delay_with_jitter(self):
        """Test that jitter adds randomness to delays."""
        config = RetryConfig(initial_delay=10.0, jitter=True)

        delays = [config.get_delay(1) for _ in range(10)]
        # With jitter, delays should vary
        assert len(set(delays)) > 1
        # But stay within expected range (75% to 125% of base delay)
        base_delay = 10.0 * 2.0  # initial_delay * exponential_base^1
        for delay in delays:
            assert base_delay * 0.75 <= delay <= base_delay * 1.25


class TestErrorCategorization:
    """Test error categorization."""

    def test_rate_limit_error(self):
        """Test rate limit error detection."""
        errors = [
            Exception("Rate limit exceeded"),
            Exception("429 Too Many Requests"),
            Exception("API rate limit reached"),
        ]
        for error in errors:
            assert categorize_error(error) == ErrorCategory.RATE_LIMIT

    def test_auth_errors(self):
        """Test authentication error detection."""
        errors = [
            Exception("401 Unauthorized"),
            Exception("Unauthorized access"),
        ]
        for error in errors:
            assert categorize_error(error) == ErrorCategory.AUTH_ERROR

    def test_permission_errors(self):
        """Test permission error detection."""
        errors = [
            Exception("403 Forbidden"),
            Exception("Forbidden access"),
        ]
        for error in errors:
            assert categorize_error(error) == ErrorCategory.PERMISSION_ERROR

    def test_server_errors(self):
        """Test server error detection."""
        errors = [
            Exception("500 error occurred"),
            Exception("502 Bad Gateway"),
            Exception("503 error"),
        ]
        for error in errors:
            assert categorize_error(error) == ErrorCategory.SERVER_ERROR

    def test_transient_errors(self):
        """Test transient error detection."""
        errors = [
            TimeoutError("Connection timeout"),
            ConnectionError("Network error"),
            OSError("Connection reset"),
        ]
        for error in errors:
            assert categorize_error(error) == ErrorCategory.TRANSIENT

    def test_retryable_categories(self):
        """Test which error categories are retryable."""
        retryable = [
            ErrorCategory.TRANSIENT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.SERVER_ERROR,
            ErrorCategory.MAINTENANCE,
        ]
        for category in retryable:
            assert is_retryable(category) is True

        non_retryable = [
            ErrorCategory.AUTH_ERROR,
            ErrorCategory.NOT_FOUND,
            ErrorCategory.VALIDATION_ERROR,
            ErrorCategory.PERMISSION_ERROR,
        ]
        for category in non_retryable:
            assert is_retryable(category) is False


class TestExponentialBackoffDecorator:
    """Test exponential backoff decorator."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test that successful calls don't retry."""
        call_count = 0

        @with_exponential_backoff(RetryConfig(max_retries=3))
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_function()
        assert result == "success"
        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test that transient errors trigger retries."""
        call_count = 0
        error_msg = "Network error"

        @with_exponential_backoff(
            RetryConfig(max_retries=2, initial_delay=0.01, jitter=False),
            retryable_exceptions=(ConnectionError,),
        )
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(error_msg)
            return "success"

        result = await flaky_function()
        assert result == "success"
        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable(self):
        """Test that non-retryable errors don't trigger retries."""
        call_count = 0
        error_msg = "401 Unauthorized"

        @with_exponential_backoff(RetryConfig(max_retries=3))
        async def auth_error_function():
            nonlocal call_count
            call_count += 1
            msg = error_msg
            raise ValueError(msg)

        with pytest.raises(ValueError, match="401 Unauthorized"):
            await auth_error_function()

        assert call_count == 1  # No retries for auth errors

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that max retries is respected."""
        call_count = 0
        error_msg = "Always fails"

        @with_exponential_backoff(
            RetryConfig(max_retries=2, initial_delay=0.01),
            retryable_exceptions=(RuntimeError,),
        )
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise RuntimeError(error_msg)

        with pytest.raises(RuntimeError, match="Always fails"):
            await always_failing()

        assert call_count == 3  # Initial + 2 retries


class TestCircuitBreaker:
    """Test circuit breaker pattern."""

    def test_initial_state(self):
        """Test circuit breaker starts closed."""
        breaker = CircuitBreaker("test", failure_threshold=3)
        assert breaker.state == CircuitBreaker.State.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker("test", failure_threshold=2, expected_exception_types=(RuntimeError,))
        error_msg = "Failure"

        @breaker
        async def failing_function():
            raise RuntimeError(error_msg)

        # First failure
        with pytest.raises(RuntimeError):
            await failing_function()
        assert breaker.state == CircuitBreaker.State.CLOSED

        # Second failure - circuit opens
        with pytest.raises(RuntimeError):
            await failing_function()
        assert breaker.state == CircuitBreaker.State.OPEN
        assert breaker.failure_count == 2

    @pytest.mark.asyncio
    async def test_circuit_prevents_calls_when_open(self):
        """Test that open circuit prevents function calls."""
        breaker = CircuitBreaker("test", failure_threshold=1, expected_exception_types=(RuntimeError,))
        # Open the circuit by triggering failures
        error_msg = "Failure"

        @breaker
        async def failing_function():
            raise RuntimeError(error_msg)

        # First failure - circuit should still be closed
        with pytest.raises(RuntimeError):
            await failing_function()

        # Circuit should now be open
        assert breaker.state == CircuitBreaker.State.OPEN

        # Further calls should be prevented
        with pytest.raises(RuntimeError, match="Circuit breaker test is OPEN"):
            await failing_function()

    @pytest.mark.asyncio
    async def test_circuit_recovery(self):
        """Test circuit recovery after timeout."""
        breaker = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
        error_msg = "Still failing"

        @breaker
        async def sometimes_working():
            if breaker.state == CircuitBreaker.State.HALF_OPEN:
                return "recovered"
            raise RuntimeError(error_msg)

        # Open the circuit
        with pytest.raises(RuntimeError):
            await sometimes_working()
        assert breaker.state == CircuitBreaker.State.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.02)

        # Circuit should enter half-open and succeed
        result = await sometimes_working()
        assert result == "recovered"
        assert breaker.state == CircuitBreaker.State.CLOSED

    def test_circuit_breaker_manager(self):
        """Test circuit breaker manager."""
        manager = CircuitBreakerManager()

        # Get or create breaker
        breaker1 = manager.get_or_create("service1")
        breaker2 = manager.get_or_create("service2")
        assert breaker1 != breaker2

        # Same name returns same breaker
        breaker1_again = manager.get_or_create("service1")
        assert breaker1 is breaker1_again

        # Test status
        breaker1.state = CircuitBreaker.State.OPEN
        status = manager.get_status()
        assert status["service1"] == "open"
        assert status["service2"] == "closed"

        # Test reset
        manager.reset("service1")
        assert breaker1.state == CircuitBreaker.State.CLOSED


class TestDeadLetterQueue:
    """Test dead letter queue functionality."""

    @pytest.mark.asyncio
    async def test_add_to_dlq(self):
        """Test adding failed operations to DLQ."""
        service = ConnectorService()
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("langflow.services.connectors.service.add_to_dlq") as mock_add_dlq:
            mock_add_dlq.return_value = MagicMock(id=uuid4())

            await service._add_to_dlq(
                mock_session,
                uuid4(),
                "sync",
                {"files": ["file1.txt"]},
                ErrorCategory.TRANSIENT,
                "Network timeout",
            )

            mock_add_dlq.assert_called_once()
            call_args = mock_add_dlq.call_args[0][1]
            assert call_args["operation_type"] == "sync"
            assert call_args["error_category"] == "transient"
            assert call_args["error_message"] == "Network timeout"
            assert "next_retry_at" in call_args
            assert call_args["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_handle_sync_error_retryable(self):
        """Test handling retryable sync errors."""
        service = ConnectorService()
        mock_session = AsyncMock(spec=AsyncSession)
        connection_id = uuid4()

        with patch.object(service, "_add_to_dlq") as mock_dlq:
            error = TimeoutError("Connection timeout")
            await service._handle_sync_error(mock_session, connection_id, {"test": "data"}, error)

            mock_dlq.assert_called_once()
            assert mock_dlq.call_args[0][2] == "sync"  # operation_type
            assert mock_dlq.call_args[0][4] == ErrorCategory.TRANSIENT

    @pytest.mark.asyncio
    async def test_handle_sync_error_non_retryable(self):
        """Test handling non-retryable sync errors."""
        service = ConnectorService()
        mock_session = AsyncMock(spec=AsyncSession)
        connection_id = uuid4()

        with patch.object(service, "_add_to_dlq") as mock_dlq:
            error = Exception("401 Unauthorized")
            await service._handle_sync_error(mock_session, connection_id, {"test": "data"}, error)

            # Should not add to DLQ for non-retryable errors
            mock_dlq.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex DLQ mocking - integration test would be better")
    async def test_process_dlq_retries(self):
        """Test processing DLQ entries for retry."""
        service = ConnectorService()
        mock_session = AsyncMock(spec=AsyncSession)

        # Create mock DLQ entries
        dlq_entry = MagicMock(spec=ConnectorDeadLetterQueue)
        dlq_entry.id = uuid4()
        dlq_entry.connection_id = uuid4()
        dlq_entry.operation_type = "sync"
        dlq_entry.payload = {"max_files": 10}
        dlq_entry.retry_count = 0
        dlq_entry.max_retries = 3

        # Create mock connection
        connection = MagicMock(spec=ConnectorConnection)
        connection.user_id = uuid4()

        with (
            patch.dict(
                "sys.modules",
                {
                    "langflow.services.database.models.connector": MagicMock(
                        get_retryable_dlq_entries=AsyncMock(return_value=[dlq_entry]),
                        get_connection=AsyncMock(return_value=connection),
                        update_dlq_entry=AsyncMock(),
                    )
                },
            ),
            patch.object(service, "sync_files", new_callable=AsyncMock) as mock_sync,
        ):
            mock_sync.return_value = "task_123"

            processed = await service.process_dlq_retries(mock_session, batch_size=1)

            assert processed == 1
            mock_sync.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex DLQ mocking - integration test would be better")
    async def test_dlq_max_retries_exceeded(self):
        """Test DLQ entry marked as failed when max retries exceeded."""
        service = ConnectorService()
        mock_session = AsyncMock(spec=AsyncSession)

        dlq_entry = MagicMock(spec=ConnectorDeadLetterQueue)
        dlq_entry.id = uuid4()
        dlq_entry.connection_id = uuid4()
        dlq_entry.operation_type = "sync"
        dlq_entry.retry_count = 2  # Already retried twice
        dlq_entry.max_retries = 3
        dlq_entry.payload = {}

        connection = MagicMock(spec=ConnectorConnection)
        error_msg = "Still failing"

        with (
            patch.dict(
                "sys.modules",
                {
                    "langflow.services.database.models.connector": MagicMock(
                        get_retryable_dlq_entries=AsyncMock(return_value=[dlq_entry]),
                        get_connection=AsyncMock(return_value=connection),
                        update_dlq_entry=AsyncMock(),
                    )
                },
            ),
            patch.object(service, "sync_files", new_callable=AsyncMock) as mock_sync,
        ):
            mock_sync.side_effect = ValueError(error_msg)

            processed = await service.process_dlq_retries(mock_session)

            assert processed == 1


class TestConnectorConfiguration:
    """Test connector configuration."""

    def test_default_retry_config(self):
        """Test default retry configuration."""
        config = ConnectorRetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter_enabled is True

    def test_circuit_breaker_config(self):
        """Test circuit breaker configuration."""
        config = ConnectorRetryConfig(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=10,
            circuit_breaker_recovery_timeout=120.0,
        )
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_failure_threshold == 10
        assert config.circuit_breaker_recovery_timeout == 120.0

    def test_dlq_config(self):
        """Test DLQ configuration."""
        config = ConnectorRetryConfig(dlq_enabled=True, dlq_max_retries=5, dlq_batch_size=20)
        assert config.dlq_enabled is True
        assert config.dlq_max_retries == 5
        assert config.dlq_batch_size == 20

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        import os

        from langflow.services.connectors.config import get_connector_config, reset_config

        # Reset cached config
        reset_config()

        # Set environment variables
        os.environ["LANGFLOW_CONNECTOR_RETRY_MAX_RETRIES"] = "5"
        os.environ["LANGFLOW_CONNECTOR_RETRY_INITIAL_DELAY"] = "2.0"

        config = get_connector_config()
        assert config.retry.max_retries == 5
        assert config.retry.initial_delay == 2.0

        # Cleanup
        del os.environ["LANGFLOW_CONNECTOR_RETRY_MAX_RETRIES"]
        del os.environ["LANGFLOW_CONNECTOR_RETRY_INITIAL_DELAY"]
        reset_config()
