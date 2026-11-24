"""Shared Alembic state probes for application startup."""

from collections.abc import Sequence

from alembic.migration import MigrationContext
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_current_alembic_heads(session: AsyncSession) -> Sequence[str]:
    """Return current database revisions without treating a missing table as an error.

    Alembic's ``MigrationContext`` returns an empty tuple when its version table
    does not exist and supports multiple current heads. Connection and driver
    failures are intentionally allowed to propagate to the caller.
    """
    async_connection = await session.connection()
    heads = await async_connection.run_sync(
        lambda connection: MigrationContext.configure(connection).get_current_heads()
    )
    return heads or ()
