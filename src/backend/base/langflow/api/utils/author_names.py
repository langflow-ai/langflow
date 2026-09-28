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
    from collections.abc import Callable, Sequence

    from sqlmodel.ext.asyncio.session import AsyncSession


@runtime_checkable
class AuthoredEntry(Protocol):
    """A read model that carries an actor and a place to render their name."""

    user_id: UUID | None
    username: str | None


TEntry = TypeVar("TEntry", bound=AuthoredEntry)


async def attach_usernames(
    session: AsyncSession,
    entries: Sequence[TEntry],
    *,
    author_id: Callable[[TEntry], UUID | None] = lambda entry: entry.user_id,
) -> Sequence[TEntry]:
    """Fill in ``username`` for every entry, resolving all authors in one query.

    A lookup per entry would be a query per row on a list that can hold fifty.
    An author who has since been deleted resolves to None, which the interface
    renders as an unknown author rather than a blank cell or a crash.
    ``author_id`` picks the actor when it is not the entry's ``user_id``.
    """
    authors = {id(entry): author_id(entry) for entry in entries}
    user_ids = {user_id for user_id in authors.values() if user_id is not None}
    if not user_ids:
        return entries

    rows = (await session.exec(select(User.id, User.username).where(col(User.id).in_(user_ids)))).all()
    names = dict(rows)
    for entry in entries:
        user_id = authors[id(entry)]
        entry.username = names.get(user_id) if user_id else None
    return entries
