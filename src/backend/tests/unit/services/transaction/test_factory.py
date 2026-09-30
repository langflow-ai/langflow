"""Tests for TransactionServiceFactory."""

from unittest.mock import MagicMock

import pytest
from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType
from langflow.services.transaction.factory import TransactionServiceFactory
from langflow.services.transaction.service import TransactionService


class TestTransactionServiceFactory:
    """Test suite for TransactionServiceFactory."""

    @pytest.fixture
    def factory(self) -> TransactionServiceFactory:
        """Create a TransactionServiceFactory instance for testing."""
        return TransactionServiceFactory()

    @pytest.fixture
    def mock_settings_service(self) -> MagicMock:
        """Create a mock settings service."""
        settings_service = MagicMock()
        settings_service.settings = MagicMock()
        settings_service.settings.transactions_storage_enabled = True
        return settings_service

    def test_should_extend_service_factory(self, factory: TransactionServiceFactory) -> None:
        """Verify TransactionServiceFactory extends ServiceFactory."""
        assert isinstance(factory, ServiceFactory)

    def test_should_have_correct_service_class(self, factory: TransactionServiceFactory) -> None:
        """Verify factory has correct service_class attribute."""
        assert factory.service_class is TransactionService

    def test_should_have_settings_service_dependency(self, factory: TransactionServiceFactory) -> None:
        """Verify factory has SETTINGS_SERVICE as dependency."""
        assert ServiceType.SETTINGS_SERVICE in factory.dependencies

    def test_should_create_transaction_service(
        self, factory: TransactionServiceFactory, mock_settings_service: MagicMock
    ) -> None:
        """Verify factory creates TransactionService instance."""
        service = factory.create(mock_settings_service)
        assert isinstance(service, TransactionService)

    def test_should_pass_settings_service_to_created_service(
        self, factory: TransactionServiceFactory, mock_settings_service: MagicMock
    ) -> None:
        """Verify factory passes settings_service to created service."""
        service = factory.create(mock_settings_service)
        assert service.settings_service is mock_settings_service

    def test_should_create_service_with_is_enabled_true(
        self, factory: TransactionServiceFactory, mock_settings_service: MagicMock
    ) -> None:
        """Verify created service has is_enabled=True when transactions enabled."""
        mock_settings_service.settings.transactions_storage_enabled = True
        service = factory.create(mock_settings_service)
        assert service.is_enabled() is True

    def test_should_create_service_with_is_enabled_false(
        self, factory: TransactionServiceFactory, mock_settings_service: MagicMock
    ) -> None:
        """Verify created service has is_enabled=False when transactions disabled."""
        mock_settings_service.settings.transactions_storage_enabled = False
        service = factory.create(mock_settings_service)
        assert service.is_enabled() is False
