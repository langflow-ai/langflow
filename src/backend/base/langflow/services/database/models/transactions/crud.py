from datetime import datetime, timezone
from typing import Optional, Union
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from langflow.services.database.models.transactions.model import TransactionBase, TransactionTable
from langflow.services.database.models.user.model import User, UserUpdate
from langflow.services.deps import get_session


def get_transactions_by_flow_id(db: Session, flow_id: UUID, limit: Optional[int] = 1000) -> list[TransactionTable]:
    stmt = (select(TransactionTable)
            .where(TransactionTable.flow_id == flow_id)
            .order_by(TransactionTable.timestamp)
            .limit(limit))

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
