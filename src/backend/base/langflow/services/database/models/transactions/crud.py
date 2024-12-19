from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.transactions.model import (
    TransactionBase,
    TransactionReadResponse,
    TransactionTable,
)


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


async def log_transaction(db: AsyncSession, transaction: TransactionBase) -> TransactionTable:
    table = TransactionTable(**transaction.model_dump())
    db.add(table)
    try:
        await db.commit()
        await db.refresh(table)
    except IntegrityError:
        await db.rollback()
        raise
    return table


def transform_transaction_table(
    transaction: list[TransactionTable] | TransactionTable,
) -> list[TransactionReadResponse]:
    if isinstance(transaction, list):
        return [TransactionReadResponse.model_validate(t, from_attributes=True) for t in transaction]
    return TransactionReadResponse.model_validate(transaction, from_attributes=True)
