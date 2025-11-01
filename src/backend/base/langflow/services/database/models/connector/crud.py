from uuid import UUID

from lfx.log import logger
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from .model import ConnectorConnection, ConnectorOAuthToken, ConnectorSyncLog


async def create_connection(session: AsyncSession, connection_data: dict) -> ConnectorConnection:
    """Create a new connector connection."""
    connection = ConnectorConnection(**connection_data)
    session.add(connection)
    await session.commit()
    await session.refresh(connection)
    logger.info(f"Created connector connection {connection.id}")
    return connection


async def get_connection(
    session: AsyncSession, connection_id: UUID, user_id: UUID | None = None
) -> ConnectorConnection | None:
    """Get a connection by ID, optionally filtered by user."""
    statement = select(ConnectorConnection).where(ConnectorConnection.id == connection_id)

    if user_id:
        statement = statement.where(ConnectorConnection.user_id == user_id)

    result = await session.exec(statement)
    return result.first()


async def get_user_connections(
    session: AsyncSession, user_id: UUID, knowledge_base_id: str | None = None
) -> list[ConnectorConnection]:
    """Get all connections for a user."""
    statement = select(ConnectorConnection).where(ConnectorConnection.user_id == user_id)

    if knowledge_base_id:
        statement = statement.where(ConnectorConnection.knowledge_base_id == knowledge_base_id)

    result = await session.exec(statement)
    return list(result.all())


async def delete_connection(session: AsyncSession, connection_id: UUID, user_id: UUID) -> bool:
    """Delete a connection (only if owned by user)."""
    connection = await get_connection(session, connection_id, user_id)

    if not connection:
        return False

    await session.delete(connection)
    await session.commit()
    logger.info(f"Deleted connector connection {connection_id}")
    return True


async def update_connection(
    session: AsyncSession, connection_id: UUID, user_id: UUID, update_data: dict
) -> ConnectorConnection | None:
    """Update a connection."""
    connection = await get_connection(session, connection_id, user_id)

    if not connection:
        return None

    for key, value in update_data.items():
        if hasattr(connection, key):
            setattr(connection, key, value)

    session.add(connection)
    await session.commit()
    await session.refresh(connection)
    return connection


async def get_oauth_token(session: AsyncSession, connection_id: UUID) -> ConnectorOAuthToken | None:
    """Get OAuth token for a connection."""
    result = await session.exec(select(ConnectorOAuthToken).where(ConnectorOAuthToken.connection_id == connection_id))
    return result.first()


async def create_oauth_token(session: AsyncSession, token_data: dict) -> ConnectorOAuthToken:
    """Create new OAuth token for a connection."""
    token = ConnectorOAuthToken(**token_data)
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def update_oauth_token(
    session: AsyncSession, connection_id: UUID, token_data: dict
) -> ConnectorOAuthToken | None:
    """Update existing OAuth token for a connection."""
    result = await session.exec(select(ConnectorOAuthToken).where(ConnectorOAuthToken.connection_id == connection_id))
    existing = result.first()

    if not existing:
        return None

    for key, value in token_data.items():
        if hasattr(existing, key):
            setattr(existing, key, value)

    session.add(existing)
    await session.commit()
    await session.refresh(existing)
    return existing


async def create_sync_log(session: AsyncSession, log_data: dict) -> ConnectorSyncLog:
    """Create a new sync log entry."""
    sync_log = ConnectorSyncLog(**log_data)
    session.add(sync_log)
    await session.commit()
    await session.refresh(sync_log)
    return sync_log


# Dead Letter Queue CRUD operations
async def add_to_dlq(session: AsyncSession, dlq_data: dict):
    """Add a failed operation to the dead letter queue."""
    from .model import ConnectorDeadLetterQueue

    dlq_entry = ConnectorDeadLetterQueue(**dlq_data)
    session.add(dlq_entry)
    await session.commit()
    await session.refresh(dlq_entry)
    logger.info(f"Added operation to DLQ: {dlq_entry.id}")
    return dlq_entry


async def get_dlq_entries(
    session: AsyncSession,
    connection_id: UUID | None = None,
    status: str = "pending",
    limit: int = 100,
):
    """Get dead letter queue entries."""
    from .model import ConnectorDeadLetterQueue

    statement = select(ConnectorDeadLetterQueue)

    if connection_id:
        statement = statement.where(ConnectorDeadLetterQueue.connection_id == connection_id)

    if status:
        statement = statement.where(ConnectorDeadLetterQueue.status == status)

    statement = statement.limit(limit)

    result = await session.exec(statement)
    return list(result.all())


async def update_dlq_entry(session: AsyncSession, dlq_id: UUID, update_data: dict):
    """Update a dead letter queue entry."""
    from .model import ConnectorDeadLetterQueue

    result = await session.exec(select(ConnectorDeadLetterQueue).where(ConnectorDeadLetterQueue.id == dlq_id))
    dlq_entry = result.first()

    if not dlq_entry:
        return None

    for key, value in update_data.items():
        if hasattr(dlq_entry, key):
            setattr(dlq_entry, key, value)

    session.add(dlq_entry)
    await session.commit()
    await session.refresh(dlq_entry)
    return dlq_entry


async def get_retryable_dlq_entries(session: AsyncSession, limit: int = 10):
    """Get DLQ entries that are ready for retry."""
    from datetime import datetime, timezone

    from .model import ConnectorDeadLetterQueue

    now = datetime.now(timezone.utc)

    statement = (
        select(ConnectorDeadLetterQueue)
        .where(ConnectorDeadLetterQueue.status == "pending")
        .where(ConnectorDeadLetterQueue.retry_count < ConnectorDeadLetterQueue.max_retries)
        .where((ConnectorDeadLetterQueue.next_retry_at == None) | (ConnectorDeadLetterQueue.next_retry_at <= now))  # noqa: E711
        .limit(limit)
    )

    result = await session.exec(statement)
    return list(result.all())
