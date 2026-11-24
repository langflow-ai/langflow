"""Suggest end-user ids an administrator may be looking for, from the sessions Langflow stored."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from lfx.utils.util_strings import escape_like_pattern
from lfx.workflow.end_user_identity import SCOPE_SEPARATOR
from sqlalchemy import func
from sqlmodel import col, select

from langflow.services.data_subjects.identity import ANONYMOUS_PREFIX
from langflow.services.data_subjects.schemas import EndUserMatch
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import TraceTable

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

LIKE_ESCAPE = "\\"
SESSIONS_SCANNED = 2000


async def _sessions_matching(session: AsyncSession, column, term: str) -> list[tuple[str, int]]:
    pattern = f"%{escape_like_pattern(term)}%{escape_like_pattern(SCOPE_SEPARATOR)}%"
    stmt = (
        select(column, func.count())
        .where(col(column).ilike(pattern, escape=LIKE_ESCAPE))
        .group_by(column)
        .limit(SESSIONS_SCANNED)
    )
    return list((await session.exec(stmt)).all())


async def search_end_users(session: AsyncSession, term: str, limit: int) -> list[EndUserMatch]:
    """End-user ids containing ``term`` (case-insensitive), with how many messages each has.

    Only ids sent through the end-user header appear: they are the ``<id>::`` prefix of a session.
    """
    needle = term.strip().casefold()
    messages: Counter[str] = Counter()
    seen: set[str] = set()
    for column, counts_messages in ((MessageTable.session_id, True), (TraceTable.session_id, False)):
        for session_id, count in await _sessions_matching(session, column, term.strip()):
            end_user_id = session_id.split(SCOPE_SEPARATOR, 1)[0]
            if not end_user_id or end_user_id == ANONYMOUS_PREFIX or needle not in end_user_id.casefold():
                continue
            seen.add(end_user_id)
            if counts_messages:
                messages[end_user_id] += count
    return [EndUserMatch(end_user_id=value, messages=messages[value]) for value in sorted(seen)[:limit]]
