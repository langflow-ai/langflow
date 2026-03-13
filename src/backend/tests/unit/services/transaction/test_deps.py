"""Tests for transaction service dependency injection."""

from unittest.mock import MagicMock, patch

from lfx.services.deps import get_transaction_service
from lfx.services.interfaces import TransactionServiceProtocol
from lfx.services.transaction.service import NoopTransactionService


class TestGetTransactionService:
    """Test suite for get_transaction_service function."""

    def test_should_return_none_when_no_service_registered(self) -> None:
        """Verify returns None when no transaction service is registered."""
        with patch("lfx.services.deps.get_service", return_value=None):
            result = get_transaction_service()
            assert result is None

    def test_should_return_service_when_registered(self) -> None:
        """Verify returns the registered service instance."""
        mock_service = MagicMock(spec=TransactionServiceProtocol)
        with patch("lfx.services.deps.get_service", return_value=mock_service):
            result = get_transaction_service()
            assert result is mock_service

    def test_should_return_noop_service_when_noop_registered(self) -> None:
        """Verify returns NoopTransactionService when it's registered."""
        noop_service = NoopTransactionService()
        with patch("lfx.services.deps.get_service", return_value=noop_service):
            result = get_transaction_service()
            assert result is noop_service
            assert isinstance(result, TransactionServiceProtocol)

    def test_should_call_get_service_with_correct_type(self) -> None:
        """Verify get_service is called with TRANSACTION_SERVICE type."""
        from lfx.services.schema import ServiceType

        with patch("lfx.services.deps.get_service") as mock_get_service:
            mock_get_service.return_value = None
            get_transaction_service()
            mock_get_service.assert_called_once_with(ServiceType.TRANSACTION_SERVICE)
