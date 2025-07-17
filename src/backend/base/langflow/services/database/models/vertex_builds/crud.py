from uuid import UUID

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
    *,
    max_builds_to_keep: int | None = None,
    max_builds_per_vertex: int | None = None,
) -> VertexBuildTable:
    """Log a vertex build and maintain build history within specified limits.

    This function performs a series of operations in a single transaction:
    1. Inserts the new build record
    2. Enforces per-vertex build limit by removing older builds
    3. Enforces global build limit across all vertices
    4. Commits the transaction

    Args:
        db (AsyncSession): The database session for executing queries.
        vertex_build (VertexBuildBase): The vertex build data to log.
        max_builds_to_keep (int | None, optional): Maximum number of builds to keep globally.
            If None, uses system settings.
        max_builds_per_vertex (int | None, optional): Maximum number of builds to keep per vertex.
            If None, uses system settings.

    Returns:
        VertexBuildTable: The newly created vertex build record.

    Raises:
        IntegrityError: If there's a database constraint violation.
        Exception: For any other database-related errors.

    Note:
        The function uses a transaction to ensure atomicity of all operations.
        If any operation fails, all changes are rolled back.
    """
    table = VertexBuildTable(**vertex_build.model_dump())

    try:
        settings = get_settings_service().settings
        max_global = max_builds_to_keep or settings.max_vertex_builds_to_keep
        max_per_vertex = max_builds_per_vertex or settings.max_vertex_builds_per_vertex

        # 1) Insert and flush the new build so queries can see it
        db.add(table)
        await db.flush()

        # 2) Delete older builds for this vertex, keeping newest max_per_vertex
        keep_vertex_subq = (
            select(VertexBuildTable.build_id)
            .where(
                VertexBuildTable.flow_id == vertex_build.flow_id,
                VertexBuildTable.id == vertex_build.id,
            )
            .order_by(col(VertexBuildTable.timestamp).desc(), col(VertexBuildTable.build_id).desc())
            .limit(max_per_vertex)
        )
        delete_vertex_older = delete(VertexBuildTable).where(
            VertexBuildTable.flow_id == vertex_build.flow_id,
            VertexBuildTable.id == vertex_build.id,
            col(VertexBuildTable.build_id).not_in(keep_vertex_subq),
        )
        await db.exec(delete_vertex_older)

        # 3) Delete older builds globally, keeping newest max_global
        keep_global_subq = (
            select(VertexBuildTable.build_id)
            .order_by(col(VertexBuildTable.timestamp).desc(), col(VertexBuildTable.build_id).desc())
            .limit(max_global)
        )
        delete_global_older = delete(VertexBuildTable).where(col(VertexBuildTable.build_id).not_in(keep_global_subq))
        await db.exec(delete_global_older)

        # 4) Commit transaction
        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return table


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
