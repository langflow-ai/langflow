import asyncio
import random
from uuid import UUID

from loguru import logger
from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable
from langflow.services.deps import get_settings_service


async def get_vertex_builds_by_flow_id(
    db: AsyncSession, flow_id: UUID, limit: int | None = 1000
) -> list[VertexBuildTable]:
    """Get the most recent vertex builds for a given flow ID.

    This function retrieves vertex builds associated with a specific flow, ordered by timestamp.
    It uses a subquery to get the latest timestamp for each build ID to ensure we get the most
    recent versions.

    Args:
        db (AsyncSession): The database session for executing queries.
        flow_id (UUID): The unique identifier of the flow to get builds for. Can be string or UUID.
        limit (int | None, optional): Maximum number of builds to return. Defaults to 1000.

    Returns:
        list[VertexBuildTable]: List of vertex builds, ordered chronologically by timestamp.

    Note:
        If flow_id is provided as a string, it will be converted to UUID automatically.
    """
    if isinstance(flow_id, str):
        flow_id = UUID(flow_id)
    subquery = (
        select(VertexBuildTable.id, func.max(VertexBuildTable.timestamp).label("max_timestamp"))
        .where(VertexBuildTable.flow_id == flow_id)
        .group_by(VertexBuildTable.id)
        .subquery()
    )
    stmt = (
        select(VertexBuildTable)
        .join(
            subquery, (VertexBuildTable.id == subquery.c.id) & (VertexBuildTable.timestamp == subquery.c.max_timestamp)
        )
        .where(VertexBuildTable.flow_id == flow_id)
        .order_by(col(VertexBuildTable.timestamp))
        .limit(limit)
    )

    builds = await db.exec(stmt)
    return list(builds)


async def log_vertex_build(
    db: AsyncSession,
    vertex_build: VertexBuildBase,
    retry_count: int = 0,
) -> VertexBuildTable:
    """Log a vertex build into the database with retry logic.

    This function only inserts the vertex build record to avoid deadlocks.
    Includes retry logic with exponential backoff for SQLite concurrency issues.
    Cleanup of old vertex builds is handled separately by a periodic cleanup task.

    Args:
        db (AsyncSession): The database session for executing queries.
        vertex_build (VertexBuildBase): The vertex build data to log.
        retry_count (int): Current retry attempt count.

    Returns:
        VertexBuildTable: The newly created vertex build record.

    Raises:
        IntegrityError: If there's a database constraint violation.
        Exception: For any other database-related errors.
    """
    max_retries = 5
    base_delay = 0.1  # 100ms
    max_delay = 2.0  # 2 seconds

    table = VertexBuildTable(**vertex_build.model_dump())

    try:
        # Simply add the new entry without cleanup to avoid deadlocks
        db.add(table)
        await db.commit()
    except Exception as e:
        await db.rollback()

        # Check if it's a database lock error and retry with exponential backoff
        if "database is locked" in str(e) and retry_count < max_retries:
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2**retry_count) + random.uniform(0, 0.1), max_delay)  # noqa: S311
            logger.debug(
                f"Database locked, retrying vertex build insert in {delay:.2f}s "
                f"(attempt {retry_count + 1}/{max_retries})"
            )

            await asyncio.sleep(delay)

            # Create a fresh session for retry
            from langflow.services.database.utils import session_getter
            from langflow.services.deps import get_db_service

            async with session_getter(get_db_service()) as new_session:
                return await log_vertex_build(new_session, vertex_build, retry_count + 1)
        else:
            raise

    return table


async def log_vertex_builds_batch(
    db: AsyncSession, vertex_builds: list[VertexBuildBase]
) -> list[VertexBuildTable] | None:
    """Log multiple vertex builds in a single batch operation without cleanup.

    This function only inserts vertex builds to avoid deadlocks entirely.
    Cleanup should be handled by a separate background process or periodic task.

    Args:
        db: Database session
        vertex_builds: List of vertex build data to log

    Returns:
        List of created VertexBuildTable entries
    """
    if not vertex_builds:
        return None

    tables = []

    try:
        # Only add vertex builds, no cleanup during batch insert
        for vertex_build in vertex_builds:
            table = VertexBuildTable(**vertex_build.model_dump())
            db.add(table)
            tables.append(table)

        # Commit all insertions
        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return tables


async def cleanup_old_vertex_builds_for_flow(
    db: AsyncSession, flow_id: UUID, max_builds_to_keep: int | None = None, max_builds_per_vertex: int | None = None
) -> int:
    """Clean up old vertex builds for a specific flow.

    This function is designed to be called separately from vertex build logging
    to avoid deadlocks during concurrent operations.

    Args:
        db: Database session
        flow_id: The flow ID to clean up vertex builds for
        max_builds_to_keep: Maximum number of builds to keep globally (uses settings default if None)
        max_builds_per_vertex: Maximum number of builds to keep per vertex (uses settings default if None)

    Returns:
        Number of vertex builds deleted
    """
    settings = get_settings_service().settings
    max_global = max_builds_to_keep or settings.max_vertex_builds_to_keep
    max_per_vertex = max_builds_per_vertex or settings.max_vertex_builds_per_vertex

    total_deleted = 0

    try:
        # First, delete older builds per vertex, keeping newest max_per_vertex for each
        # Get all unique vertex IDs for this flow
        vertex_ids_stmt = select(VertexBuildTable.id).where(VertexBuildTable.flow_id == flow_id).distinct()
        vertex_ids_result = await db.exec(vertex_ids_stmt)
        vertex_ids = list(vertex_ids_result)

        # Clean up each vertex individually
        for vertex_id in vertex_ids:
            keep_vertex_subq = (
                select(VertexBuildTable.build_id)
                .where(
                    VertexBuildTable.flow_id == flow_id,
                    VertexBuildTable.id == vertex_id,
                )
                .order_by(col(VertexBuildTable.timestamp).desc(), col(VertexBuildTable.build_id).desc())
                .limit(max_per_vertex)
            )
            delete_vertex_older = delete(VertexBuildTable).where(
                VertexBuildTable.flow_id == flow_id,
                VertexBuildTable.id == vertex_id,
                col(VertexBuildTable.build_id).not_in(keep_vertex_subq),
            )
            result = await db.exec(delete_vertex_older)
            if result:
                total_deleted += result.rowcount or 0

        # Then delete older builds globally for this flow, keeping newest max_global
        keep_global_subq = (
            select(VertexBuildTable.build_id)
            .where(VertexBuildTable.flow_id == flow_id)
            .order_by(col(VertexBuildTable.timestamp).desc(), col(VertexBuildTable.build_id).desc())
            .limit(max_global)
        )
        delete_global_older = delete(VertexBuildTable).where(
            VertexBuildTable.flow_id == flow_id, col(VertexBuildTable.build_id).not_in(keep_global_subq)
        )
        result = await db.exec(delete_global_older)
        if result:
            total_deleted += result.rowcount or 0

        await db.commit()
        if total_deleted > 0:
            from loguru import logger

            logger.debug(f"Cleaned up {total_deleted} old vertex builds for flow {flow_id}")
    except Exception:
        await db.rollback()
        raise

    return total_deleted


async def delete_vertex_builds_by_flow_id(db: AsyncSession, flow_id: UUID) -> None:
    """Delete all vertex builds associated with a specific flow ID.

    Args:
        db (AsyncSession): The database session for executing queries.
        flow_id (UUID): The unique identifier of the flow whose builds should be deleted.

    Note:
        This operation is permanent and cannot be undone. Use with caution.
        The function commits the transaction automatically.
    """
    stmt = delete(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id)
    await db.exec(stmt)
