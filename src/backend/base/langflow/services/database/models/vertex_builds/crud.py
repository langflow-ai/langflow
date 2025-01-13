from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable
from langflow.services.settings.manager import get_settings_service


async def get_vertex_builds_by_flow_id(
    db: AsyncSession, flow_id: UUID, limit: int | None = 1000
) -> list[VertexBuildTable]:
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
    """Log a vertex build and maintain maximum builds per vertex.

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
        # Get max entries setting
        max_entries = get_settings_service().settings.max_vertex_builds_per_vertex

        # Delete older entries in a single transaction
        delete_older = delete(VertexBuildTable).where(
            VertexBuildTable.flow_id == vertex_build.flow_id,
            VertexBuildTable.id == vertex_build.id,
            VertexBuildTable.build_id.in_(
                select(VertexBuildTable.build_id)
                .where(VertexBuildTable.flow_id == vertex_build.flow_id, VertexBuildTable.id == vertex_build.id)
                .order_by(VertexBuildTable.timestamp.desc())
                .offset(max_entries - 1)  # Keep newest max_entries-1 plus the one we're adding
            ),
        )

        # Add new entry and execute delete in same transaction
        db.add(table)
        await db.exec(delete_older)
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
