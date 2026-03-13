"""Tests for NoopTransactionService."""

import pytest
from lfx.services.interfaces import TransactionServiceProtocol
from lfx.services.transaction.service import NoopTransactionService


class TestNoopTransactionService:
    """Test suite for NoopTransactionService."""

    @pytest.fixture
    def service(self) -> NoopTransactionService:
        """Create a NoopTransactionService instance for testing."""
        return NoopTransactionService()

    def test_should_implement_protocol(self, service: NoopTransactionService) -> None:
        """Verify NoopTransactionService implements TransactionServiceProtocol."""
        assert isinstance(service, TransactionServiceProtocol)

    def test_should_return_false_for_is_enabled(self, service: NoopTransactionService) -> None:
        """Verify is_enabled always returns False for noop service."""
        assert service.is_enabled() is False

    @pytest.mark.asyncio
    async def test_should_not_raise_when_logging_transaction(self, service: NoopTransactionService) -> None:
        """Verify log_transaction completes without raising exceptions."""
        await service.log_transaction(
            flow_id="test-flow-id",
            vertex_id="test-vertex-id",
            inputs={"key": "value"},
            outputs={"result": "output"},
            status="success",
        )

    @pytest.mark.asyncio
    async def test_should_handle_none_inputs_and_outputs(self, service: NoopTransactionService) -> None:
        """Verify log_transaction handles None inputs and outputs gracefully."""
        await service.log_transaction(
            flow_id="test-flow-id",
            vertex_id="test-vertex-id",
            inputs=None,
            outputs=None,
            status="success",
        )

    @pytest.mark.asyncio
    async def test_should_handle_error_status(self, service: NoopTransactionService) -> None:
        """Verify log_transaction handles error status with error message."""
        await service.log_transaction(
            flow_id="test-flow-id",
            vertex_id="test-vertex-id",
            inputs={"key": "value"},
            outputs=None,
            status="error",
            error="Something went wrong",
        )

    @pytest.mark.asyncio
    async def test_should_handle_target_id(self, service: NoopTransactionService) -> None:
        """Verify log_transaction handles target_id parameter."""
        await service.log_transaction(
            flow_id="test-flow-id",
            vertex_id="test-vertex-id",
            inputs={"key": "value"},
            outputs={"result": "output"},
            status="success",
            target_id="target-vertex-id",
        )

    @pytest.mark.asyncio
    async def test_should_handle_all_parameters(self, service: NoopTransactionService) -> None:
        """Verify log_transaction handles all parameters together."""
        await service.log_transaction(
            flow_id="flow-123",
            vertex_id="vertex-456",
            inputs={"input_key": "input_value"},
            outputs={"output_key": "output_value"},
            status="success",
            target_id="target-789",
            error=None,
        )
