from uuid import UUID

from lfx.log.logger import logger
from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.transactions.model import (
    TransactionBase,
    TransactionReadResponse,
    TransactionTable,
)
from langflow.services.deps import get_settings_service


async def get_transactions_by_flow_id(
    db: AsyncSession, flow_id: UUID, limit: int | None = 1000
) -> list[TransactionTable]:
    stmt = (
        select(TransactionTable)
        .where(TransactionTable.flow_id == flow_id)
        .order_by(col(TransactionTable.timestamp))
        .limit(limit)
    )

    transactions = await db.exec(stmt)
    return list(transactions)


async def log_transaction(db: AsyncSession, transaction: TransactionBase) -> TransactionTable | None:
    """Log a transaction into the database.

    This function logs a new transaction into the database. Cleanup of old transactions
    is handled separately to avoid deadlocks during concurrent flow execution.

    Args:
        db: Database session
        transaction: Transaction data to log

    Returns:
        The created TransactionTable entry

    Raises:
        IntegrityError: If there is a database integrity error
    """
    if not transaction.flow_id:
        await logger.adebug("Transaction flow_id is None")
        return None
    table = TransactionTable(**transaction.model_dump())

    try:
        # Simply add the new entry without cleanup
        db.add(table)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return table


async def log_transactions_batch(db: AsyncSession, transactions: list[TransactionBase]) -> list[TransactionTable]:
    """Log multiple transactions in a single batch operation without cleanup.

    This function only inserts transactions to avoid deadlocks entirely.
    Cleanup should be handled by a separate background process or periodic task.

    Args:
        db: Database session
        transactions: List of transaction data to log

    Returns:
        List of created TransactionTable entries
    """
    if not transactions:
        return []

    tables = []

    try:
        # Only add transactions, no cleanup during batch insert
        for transaction in transactions:
            if transaction.flow_id:
                table = TransactionTable(**transaction.model_dump())
                db.add(table)
                tables.append(table)

        # Commit all insertions
        await db.commit()
        logger.debug(f"Batch inserted {len(tables)} transactions")

    except Exception:
        await db.rollback()
        raise

    return tables


async def cleanup_old_transactions_for_flow(db: AsyncSession, flow_id: UUID, max_entries: int | None = None) -> int:
    """Clean up old transactions for a specific flow.

    This function is designed to be called separately from transaction logging
    to avoid deadlocks during concurrent operations.

    Args:
        db: Database session
        flow_id: The flow ID to clean up transactions for
        max_entries: Maximum number of transactions to keep (uses settings default if None)

    Returns:
        Number of transactions deleted
    """
    if max_entries is None:
        max_entries = get_settings_service().settings.max_transactions_to_keep

    try:
        # Delete older entries, keeping only the newest max_entries.
        # More portable and deterministic: keep top-N by (timestamp DESC, id DESC)
        newest_ids_stmt = (
            select(TransactionTable.id)
            .where(TransactionTable.flow_id == flow_id)
            .order_by(col(TransactionTable.timestamp).desc(), col(TransactionTable.id).desc())
            .limit(max_entries)
        )
        delete_stmt = delete(TransactionTable).where(
            TransactionTable.flow_id == flow_id,
            col(TransactionTable.id).notin_(newest_ids_stmt),
        )

        result = await db.exec(delete_stmt)
        await db.commit()
        deleted_count = result.rowcount if result else 0
        if deleted_count > 0:
            logger.debug(f"Cleaned up {deleted_count} old transactions for flow {flow_id}")
    except Exception:
        await db.rollback()
        raise
    return deleted_count


def transform_transaction_table(
    transaction: list[TransactionTable] | TransactionTable,
) -> list[TransactionReadResponse]:
    if isinstance(transaction, list):
        return [TransactionReadResponse.model_validate(t, from_attributes=True) for t in transaction]
    return TransactionReadResponse.model_validate(transaction, from_attributes=True)
