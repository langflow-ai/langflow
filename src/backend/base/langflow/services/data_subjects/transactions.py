"""Which ``transaction`` rows belong to a data subject.

Rows written since the run attribution columns exist carry the run's message owner and session. Older
rows carry neither, so a chat vertex's own ``session_id`` input is the only key left for them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlmodel import col

from langflow.services.database.models.transactions.model import TransactionTable

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql.elements import ColumnElement

    from langflow.services.data_subjects.identity import EndUserKeys

LIKE_ESCAPE = "\\"


def end_user_transactions(keys: EndUserKeys, scope: tuple[UUID, ...] = ()) -> ColumnElement[bool]:
    pattern = keys.session_like_pattern
    attributed = and_(
        TransactionTable.user_id == keys.message_owner_id,
        col(TransactionTable.session_id).like(pattern, escape=LIKE_ESCAPE),
    )
    legacy = and_(
        col(TransactionTable.user_id).is_(None),
        col(TransactionTable.inputs)["session_id"].as_string().like(pattern, escape=LIKE_ESCAPE),
    )
    match = or_(attributed, legacy)
    if scope:
        return and_(match, col(TransactionTable.flow_id).in_(scope))
    return match


def builder_transactions(user_id: UUID) -> ColumnElement[bool]:
    return TransactionTable.user_id == user_id
