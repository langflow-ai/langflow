"""Transaction service implementations for lfx."""

from __future__ import annotations

from typing import Any

from lfx.services.interfaces import TransactionServiceProtocol


class NoopTransactionService(TransactionServiceProtocol):
    """No-operation transaction service for standalone lfx mode.

    This service is used when lfx runs without a concrete transaction
    service implementation (e.g., without langflow). All operations
    are no-ops and transaction logging is disabled.
    """

    async def log_transaction(
        self,
        flow_id: str,  # noqa: ARG002
        vertex_id: str,  # noqa: ARG002
        inputs: dict[str, Any] | None,  # noqa: ARG002
        outputs: dict[str, Any] | None,  # noqa: ARG002
        status: str,  # noqa: ARG002
        target_id: str | None = None,  # noqa: ARG002
        error: str | None = None,  # noqa: ARG002
    ) -> None:
        """No-op implementation of transaction logging.

        In standalone mode, transactions are not persisted.
        """

    def is_enabled(self) -> bool:
        """Transaction logging is disabled in noop mode."""
        return False
