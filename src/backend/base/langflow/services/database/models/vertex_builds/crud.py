from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable
from langflow.services.deps import get_settings_service


async def get_vertex_builds_by_flow_id(
    db: AsyncSession, flow_id: UUID, limit: int | None = 1000
) -> list[VertexBuildTable]:
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


async def log_vertex_build(db: AsyncSession, vertex_build: VertexBuildBase) -> VertexBuildTable:
    """Log a vertex build and maintain maximum builds globally and per vertex.

    Args:
        db: Database session
        vertex_build: Vertex build data to log

    Returns:
        The created VertexBuildTable entry

    Raises:
        IntegrityError: If there is a database integrity error
    """
    table = VertexBuildTable(**vertex_build.model_dump())

    try:
        settings = get_settings_service().settings
        max_global = settings.max_vertex_builds_to_keep
        max_per_vertex = settings.max_vertex_builds_per_vertex

        # Create a CTE for global builds ranking
        global_ranks = select(
            VertexBuildTable.id, func.row_number().over(order_by=VertexBuildTable.timestamp.desc()).label("rn")
        ).cte("global_ranks")

        # Create a CTE for per-vertex builds ranking
        vertex_ranks = (
            select(
                VertexBuildTable.build_id,
                func.row_number()
                .over(
                    partition_by=[VertexBuildTable.flow_id, VertexBuildTable.id],
                    order_by=VertexBuildTable.timestamp.desc(),
                )
                .label("rn"),
            )
            .where(VertexBuildTable.flow_id == vertex_build.flow_id, VertexBuildTable.id == vertex_build.id)
            .cte("vertex_ranks")
        )

        # Delete older entries globally
        delete_global = delete(VertexBuildTable).where(
            VertexBuildTable.id.in_(select(global_ranks.c.id).where(global_ranks.c.rn >= max_global))
        )

        # Delete older entries per vertex
        delete_per_vertex = delete(VertexBuildTable).where(
            VertexBuildTable.build_id.in_(select(vertex_ranks.c.build_id).where(vertex_ranks.c.rn >= max_per_vertex))
        )

        # Execute both deletes and add new entry in same transaction
        db.add(table)
        await db.exec(delete_global)
        await db.exec(delete_per_vertex)
        await db.commit()
        await db.refresh(table)

    except IntegrityError:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    return table


async def delete_vertex_builds_by_flow_id(db: AsyncSession, flow_id: UUID) -> None:
    stmt = delete(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id)
    await db.exec(stmt)
    await db.commit()
