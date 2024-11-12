from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable


async def get_vertex_builds_by_flow_id(
    db: AsyncSession, flow_id: UUID, limit: int | None = 1000
) -> list[VertexBuildTable]:
    stmt = (
        select(VertexBuildTable)
        .where(VertexBuildTable.flow_id == flow_id)
        .order_by(col(VertexBuildTable.timestamp))
        .limit(limit)
    )

    builds = await db.exec(stmt)
    return list(builds)


def log_vertex_build(db: Session, vertex_build: VertexBuildBase) -> VertexBuildTable:
    table = VertexBuildTable(**vertex_build.model_dump())
    db.add(table)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    return table


def delete_vertex_builds_by_flow_id(db: Session, flow_id: UUID) -> None:
    db.exec(delete(VertexBuildTable).where(VertexBuildTable.flow_id == flow_id))
    db.commit()
