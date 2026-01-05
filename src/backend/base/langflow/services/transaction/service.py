"""Transaction service implementation for langflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.log.logger import logger
from lfx.services.deps import session_scope
from lfx.services.interfaces import TransactionServiceProtocol

from langflow.services.base import Service
from langflow.services.database.models.transactions.crud import log_transaction as crud_log_transaction
from langflow.services.database.models.transactions.model import TransactionBase

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class TransactionService(Service, TransactionServiceProtocol):
    """Concrete implementation of transaction logging service.

    This service handles logging of component execution transactions to the database,
    tracking inputs, outputs, and status of each vertex build.
    """

    name = "transaction_service"

    def __init__(self, settings_service: SettingsService):
        """Initialize the transaction service.

        Args:
            settings_service: The settings service for checking if transactions are enabled.
        """
        self.settings_service = settings_service

    async def log_transaction(
        self,
        flow_id: str,
        vertex_id: str,
        inputs: dict[str, Any] | None,
        outputs: dict[str, Any] | None,
        status: str,
        target_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Log a transaction record for a vertex execution.

        Args:
            flow_id: The flow ID (as string)
            vertex_id: The vertex/component ID
            inputs: Input parameters for the component
            outputs: Output results from the component
            status: Execution status (success/error)
            target_id: Optional target vertex ID
            error: Optional error message
        """
        if not self.is_enabled():
            return

        try:
            flow_uuid = UUID(flow_id) if isinstance(flow_id, str) else flow_id

            transaction = TransactionBase(
                vertex_id=vertex_id,
                target_id=target_id,
                inputs=inputs,
                outputs=outputs,
                status=status,
                error=error,
                flow_id=flow_uuid,
            )

            async with session_scope() as session:
                await crud_log_transaction(session, transaction)

        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Error logging transaction: {exc!s}")

    def is_enabled(self) -> bool:
        """Check if transaction logging is enabled.

        Returns:
            True if transaction logging is enabled, False otherwise.
        """
        return getattr(self.settings_service.settings, "transactions_storage_enabled", False)
