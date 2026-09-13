"""Task-local caller/admission session context without a database dependency."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True, slots=True)
class AuthorizationSession:
    session: Any
    owner: asyncio.Task[Any] | None
    admission: bool
    mutation: bool = False


_session: ContextVar[AuthorizationSession | None] = ContextVar("authorization_session", default=None)


def current_authorization_session() -> AuthorizationSession | None:
    """Never share an async session with a child task inheriting contextvars."""
    context = _session.get()
    return context if context is not None and context.owner is asyncio.current_task() else None


@contextmanager
def authorization_session(session: Any, *, admission: bool = False, mutation: bool = False) -> Iterator[None]:
    """Bind for exactly one caller-owned scope; transaction ownership stays with the caller."""
    current = current_authorization_session()
    admission = admission or (current is not None and current.session is session and current.admission)
    mutation = mutation or (current is not None and current.session is session and current.mutation)
    token = _session.set(AuthorizationSession(session, asyncio.current_task(), admission, mutation))
    try:
        yield
    finally:
        _session.reset(token)
