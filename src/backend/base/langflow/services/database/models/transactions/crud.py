import random
from uuid import UUID

from loguru import logger
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
    """Log a transaction and maintain a maximum number of transactions in the database.

    This function logs a new transaction into the database and ensures that the number of transactions
    does not exceed the maximum limit specified in the settings. If the number of transactions exceeds
    the limit, the oldest transactions are deleted to maintain the limit.

    To reduce deadlock frequency, cleanup is only performed based on a configurable probability
    (default 5%) using a random generator. This significantly reduces database contention while
    still maintaining data cleanup.

    Args:
        db: Database session
        transaction: Transaction data to log

    Returns:
        The created TransactionTable entry

    Raises:
        IntegrityError: If there is a database integrity error
    """
    if not transaction.flow_id:
        logger.debug("Transaction flow_id is None")
        return None
    table = TransactionTable(**transaction.model_dump())

    try:
        # Get settings
        settings = get_settings_service().settings
        max_entries = settings.max_transactions_to_keep
        cleanup_probability = settings.transaction_cleanup_probability
        # Add new entry first
        db.add(table)
        await db.flush()  # Flush to ensure the new record is visible

        # Only perform cleanup based on configurable probability to reduce deadlock frequency
        should_cleanup = random.random() < cleanup_probability  # noqa: S311

        if should_cleanup:
            logger.debug(
                f"Performing cleanup for flow {transaction.flow_id} ({cleanup_probability * 100:.1f}% trigger)"
            )

            # Get IDs of transactions to delete (older ones beyond the limit)
            # Use a separate query to avoid deadlocks
            ids_to_delete_stmt = (
                select(TransactionTable.id)
                .where(TransactionTable.flow_id == transaction.flow_id)
                .order_by(col(TransactionTable.timestamp).desc())
                .offset(max_entries)  # Skip the newest max_entries, delete the rest
            )

            ids_to_delete_result = await db.exec(ids_to_delete_stmt)
            ids_to_delete = list(ids_to_delete_result.all())

            # Delete older entries if any exist
            if ids_to_delete:
                delete_older = delete(TransactionTable).where(TransactionTable.id.in_(ids_to_delete))
                await db.exec(delete_older)
                logger.debug(f"Cleaned up {len(ids_to_delete)} old transactions for flow {transaction.flow_id}")

        await db.commit()

    except Exception:
        await db.rollback()
        raise
    return table


def transform_transaction_table(
    transaction: list[TransactionTable] | TransactionTable,
) -> list[TransactionReadResponse]:
    if isinstance(transaction, list):
        return [TransactionReadResponse.model_validate(t, from_attributes=True) for t in transaction]
    return TransactionReadResponse.model_validate(transaction, from_attributes=True)
