"""Shared session-scope logic, parameterized by a database service.

Option B of the two-tier service design promotes ``session_scope`` /
``session_scope_readonly`` onto the DatabaseService *port* (they become methods a
Tier 2 service calls on its injected ``database_service``), rather than only
existing as module-level functions that reach for a global service.

To keep exactly one copy of the commit/rollback semantics, that logic lives here
as free functions parameterized by the db service. Both the port methods
(``DatabaseService.session_scope``) and the back-compat module-level helpers in
``lfx.services.deps`` delegate here, so there is a single source of truth and no
behavioral drift between "call the method on my injected dependency" and "call
the global function".
"""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Any, Protocol

from fastapi import HTTPException

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


class _SupportsWithSession(Protocol):
    """Minimal surface the scope helpers need from a database service."""

    def _with_session(self) -> Any: ...


@asynccontextmanager
async def session_scope_for(db_service: _SupportsWithSession) -> AsyncGenerator[AsyncSession, None]:
    """Async write session scope over ``db_service`` with auto-commit/rollback.

    Commits if the body completes without error; rolls back on exception.
    ``HTTPException`` is treated as FastAPI control flow (rolled back but not
    logged as an error); any other exception is logged then re-raised.
    """
    async with db_service._with_session() as session:  # noqa: SLF001
        try:
            yield session
            await session.commit()
        except HTTPException:
            # HTTPExceptions are control flow in FastAPI (returning 4xx/5xx responses),
            # not actual errors. Don't log them - FastAPI's exception handlers will
            # take care of the HTTP response. Just rollback any uncommitted changes.
            if session.is_active:
                from sqlalchemy.exc import InvalidRequestError

                with suppress(InvalidRequestError):
                    await session.rollback()
            raise
        except Exception as e:
            # Actual application/database errors - log at error level
            await logger.aexception("An error occurred during the session scope.", exception=e)

            # Only rollback if session is still in a valid state
            if session.is_active:
                from sqlalchemy.exc import InvalidRequestError

                with suppress(InvalidRequestError):
                    # Session was already rolled back by SQLAlchemy
                    await session.rollback()
            raise
        # No explicit close needed - _with_session() handles it


@asynccontextmanager
async def session_scope_readonly_for(db_service: _SupportsWithSession) -> AsyncGenerator[AsyncSession, None]:
    """Async read-only session scope over ``db_service`` (no commit, no rollback)."""
    async with db_service._with_session() as session:  # noqa: SLF001
        yield session
        # No commit - read-only
        # No clean up - client is responsible (plus, read only sessions are not committed)
        # No explicit close needed - _with_session() handles it
