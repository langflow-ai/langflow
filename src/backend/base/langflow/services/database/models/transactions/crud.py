from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, col

from langflow.services.database.models.transactions.model import TransactionBase, TransactionTable


def get_transactions_by_flow_id(db: Session, flow_id: UUID, limit: Optional[int] = 1000) -> list[TransactionTable]:
    stmt = (
        select(TransactionTable)
        .where(TransactionTable.flow_id == flow_id)
        .order_by(col(TransactionTable.timestamp))
        .limit(limit)
    )

    transactions = db.exec(stmt)
    return [t for t in transactions]


def log_transaction(db: Session, transaction: TransactionBase) -> TransactionTable:
    table = TransactionTable(**transaction.model_dump())
    db.add(table)
    try:
        db.commit()
        return table
    except IntegrityError as e:
        db.rollback()
        raise e
