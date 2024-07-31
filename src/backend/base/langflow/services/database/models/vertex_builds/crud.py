from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, col
from sqlalchemy import delete

from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable


def get_vertex_builds_by_flow_id(db: Session, flow_id: UUID, limit: Optional[int] = 1000) -> list[VertexBuildTable]:
    stmt = (
        select(VertexBuildTable)
        .where(VertexBuildTable.flow_id == flow_id)
        .order_by(col(VertexBuildTable.timestamp))
        .limit(limit)
    )

    builds = db.exec(stmt)
    return [t for t in builds]


def log_vertex_build(db: Session, vertex_build: VertexBuildBase) -> VertexBuildTable:
    table = VertexBuildTable(**vertex_build.model_dump())
    db.add(table)
    try:
        db.commit()
        return table
    except IntegrityError as e:
        db.rollback()
        raise e


def delete_vertex_builds_by_flow_id(db: Session, flow_id: UUID) -> None:
    delete(VertexBuildTable).where(VertexBuildTable.flow.has(id=flow_id))  # type: ignore
    db.commit()
