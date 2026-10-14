"""Resolving the person behind a row, for lists that show who did something.

Shared because two histories of the same flow answer the same question — version
history and the edit trail both name an actor — and a rule about who that is
(a deleted author, a display-name field, a caching decision) has to change in one
place or it changes in neither.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable
from uuid import UUID

from sqlmodel import col, select

from langflow.services.database.models.user.model import User

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlmodel.ext.asyncio.session import AsyncSession


@runtime_checkable
class AuthoredEntry(Protocol):
    """A read model that carries an actor and a place to render their name."""

    user_id: UUID | None
    username: str | None


TEntry = TypeVar("TEntry", bound=AuthoredEntry)


async def attach_usernames(session: AsyncSession, entries: Sequence[TEntry]) -> Sequence[TEntry]:
    """Fill in ``username`` for every entry, resolving all authors in one query.

    A lookup per entry would be a query per row on a list that can hold fifty.
    An author who has since been deleted resolves to None, which the interface
    renders as an unknown author rather than a blank cell or a crash.
    """
    user_ids = {entry.user_id for entry in entries if entry.user_id is not None}
    if not user_ids:
        return entries

    rows = (await session.exec(select(User.id, User.username).where(col(User.id).in_(user_ids)))).all()
    names = dict(rows)
    for entry in entries:
        entry.username = names.get(entry.user_id) if entry.user_id else None
    return entries
