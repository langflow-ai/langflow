"""Database service implementations for lfx package."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, ClassVar

from lfx.services.capabilities import Capability, Tier

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


class NoopDatabaseService:
    """No-operation database service for standalone lfx usage.

    This provides a database service interface that always returns NoopSession,
    allowing lfx to work without a real database connection.

    As a Tier 1 (infrastructure) service it declares no capabilities: a
    ``NoopSession`` neither persists across restarts nor shares state across
    processes. A Tier 2 service that ``Requires`` the database with
    ``{PERSISTENT}`` therefore fails ``validate_wiring()`` against this
    implementation — which is the desired loud-at-boot behavior instead of
    silent no-op writes.
    """

    # Tier 1 infrastructure port. NoopSession is in-process and ephemeral, so no
    # capability is advertised. (The chat-memory service requires the database to
    # be *present*, not PERSISTENT, so it still wires successfully over this.)
    tier: ClassVar[Tier] = Tier.INFRASTRUCTURE
    capabilities: ClassVar[frozenset[Capability]] = frozenset()

    @asynccontextmanager
    async def _with_session(self):
        """Internal method to create a session. DO NOT USE DIRECTLY.

        Use session_scope() for write operations or session_scope_readonly() for read operations.
        This method does not handle commits - it only provides a raw session.
        """
        from lfx.services.session import NoopSession

        async with NoopSession() as session:
            yield session

    def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Write session scope over this service (auto-commit/rollback).

        Part of the Tier 1 database port: Tier 2 services call this on their
        injected ``database_service`` rather than reaching for a global.
        """
        from lfx.services.database.session import session_scope_for

        return session_scope_for(self)

    def session_scope_readonly(self) -> AsyncGenerator[AsyncSession, None]:
        """Read-only session scope over this service (no commit/rollback)."""
        from lfx.services.database.session import session_scope_readonly_for

        return session_scope_readonly_for(self)
