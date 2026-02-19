"""Tests for TransactionService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langflow.services.transaction.service import TransactionService
from lfx.services.interfaces import TransactionServiceProtocol


class TestTransactionService:
    """Test suite for TransactionService."""

    @pytest.fixture
    def mock_settings_service(self) -> MagicMock:
        """Create a mock settings service."""
        settings_service = MagicMock()
        settings_service.settings = MagicMock()
        settings_service.settings.transactions_storage_enabled = True
        return settings_service

    @pytest.fixture
    def mock_settings_service_disabled(self) -> MagicMock:
        """Create a mock settings service with transactions disabled."""
        settings_service = MagicMock()
        settings_service.settings = MagicMock()
        settings_service.settings.transactions_storage_enabled = False
        return settings_service

    @pytest.fixture
    def service(self, mock_settings_service: MagicMock) -> TransactionService:
        """Create a TransactionService instance for testing."""
        return TransactionService(mock_settings_service)

    @pytest.fixture
    def service_disabled(self, mock_settings_service_disabled: MagicMock) -> TransactionService:
        """Create a TransactionService instance with transactions disabled."""
        return TransactionService(mock_settings_service_disabled)

    def test_should_implement_protocol(self, service: TransactionService) -> None:
        """Verify TransactionService implements TransactionServiceProtocol."""
        assert isinstance(service, TransactionServiceProtocol)

    def test_should_have_correct_name(self, service: TransactionService) -> None:
        """Verify service has correct name attribute."""
        assert service.name == "transaction_service"

    def test_should_return_true_for_is_enabled_when_enabled(self, service: TransactionService) -> None:
        """Verify is_enabled returns True when transactions are enabled."""
        assert service.is_enabled() is True

    def test_should_return_false_for_is_enabled_when_disabled(self, service_disabled: TransactionService) -> None:
        """Verify is_enabled returns False when transactions are disabled."""
        assert service_disabled.is_enabled() is False

    @pytest.mark.asyncio
    async def test_should_not_log_when_disabled(self, service_disabled: TransactionService) -> None:
        """Verify log_transaction does nothing when transactions are disabled."""
        with patch("langflow.services.transaction.service.session_scope") as mock_session:
            await service_disabled.log_transaction(
                flow_id="test-flow-id",
                vertex_id="test-vertex-id",
                inputs={"key": "value"},
                outputs={"result": "output"},
                status="success",
            )
            mock_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_log_transaction_when_enabled(self, service: TransactionService) -> None:
        """Verify log_transaction creates a transaction record when enabled."""
        mock_session = AsyncMock()
        mock_crud = AsyncMock()

        with (
            patch("langflow.services.transaction.service.session_scope") as mock_session_scope,
            patch("langflow.services.transaction.service.crud_log_transaction", mock_crud) as mock_log,
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)

            await service.log_transaction(
                flow_id="550e8400-e29b-41d4-a716-446655440000",
                vertex_id="test-vertex-id",
                inputs={"key": "value"},
                outputs={"result": "output"},
                status="success",
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            transaction = call_args[0][1]
            assert transaction.vertex_id == "test-vertex-id"
            assert transaction.status == "success"
            assert transaction.flow_id == UUID("550e8400-e29b-41d4-a716-446655440000")

    @pytest.mark.asyncio
    async def test_should_handle_string_flow_id(self, service: TransactionService) -> None:
        """Verify log_transaction handles string flow_id correctly."""
        mock_session = AsyncMock()
        mock_crud = AsyncMock()

        with (
            patch("langflow.services.transaction.service.session_scope") as mock_session_scope,
            patch("langflow.services.transaction.service.crud_log_transaction", mock_crud),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)

            await service.log_transaction(
                flow_id="550e8400-e29b-41d4-a716-446655440000",
                vertex_id="test-vertex-id",
                inputs=None,
                outputs=None,
                status="success",
            )

            call_args = mock_crud.call_args
            transaction = call_args[0][1]
            assert isinstance(transaction.flow_id, UUID)

    @pytest.mark.asyncio
    async def test_should_handle_error_status_with_message(self, service: TransactionService) -> None:
        """Verify log_transaction handles error status with error message."""
        mock_session = AsyncMock()
        mock_crud = AsyncMock()

        with (
            patch("langflow.services.transaction.service.session_scope") as mock_session_scope,
            patch("langflow.services.transaction.service.crud_log_transaction", mock_crud),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)

            await service.log_transaction(
                flow_id="550e8400-e29b-41d4-a716-446655440000",
                vertex_id="test-vertex-id",
                inputs={"key": "value"},
                outputs=None,
                status="error",
                error="Something went wrong",
            )

            call_args = mock_crud.call_args
            transaction = call_args[0][1]
            assert transaction.status == "error"
            assert transaction.error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_should_handle_target_id(self, service: TransactionService) -> None:
        """Verify log_transaction handles target_id parameter."""
        mock_session = AsyncMock()
        mock_crud = AsyncMock()

        with (
            patch("langflow.services.transaction.service.session_scope") as mock_session_scope,
            patch("langflow.services.transaction.service.crud_log_transaction", mock_crud),
        ):
            mock_session_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_scope.return_value.__aexit__ = AsyncMock(return_value=None)

            await service.log_transaction(
                flow_id="550e8400-e29b-41d4-a716-446655440000",
                vertex_id="test-vertex-id",
                inputs={"key": "value"},
                outputs={"result": "output"},
                status="success",
                target_id="target-vertex-id",
            )

            call_args = mock_crud.call_args
            transaction = call_args[0][1]
            assert transaction.target_id == "target-vertex-id"

    @pytest.mark.asyncio
    async def test_should_not_raise_on_database_error(self, service: TransactionService) -> None:
        """Verify log_transaction handles database errors gracefully."""
        with patch("langflow.services.transaction.service.session_scope") as mock_session_scope:
            mock_session_scope.side_effect = Exception("Database error")

            # Should not raise
            await service.log_transaction(
                flow_id="550e8400-e29b-41d4-a716-446655440000",
                vertex_id="test-vertex-id",
                inputs={"key": "value"},
                outputs={"result": "output"},
                status="success",
            )
