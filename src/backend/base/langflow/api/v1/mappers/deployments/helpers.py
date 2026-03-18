"""Shared mapper helpers for deployment flow-version resolution."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.schema import BaseFlowArtifact
from sqlalchemy import and_, literal, union_all
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion


async def build_flow_artifacts_from_flow_versions(
    *,
    db,
    flow_version_ids: list[UUID],
) -> list[tuple[UUID, int, BaseFlowArtifact]]:
    """Resolve flow version ids into artifacts preserving input order."""
    if not flow_version_ids:
        return []

    indexed_selects = [
        select(literal(index).label("position"), literal(flow_version_id).label("flow_version_id"))
        for index, flow_version_id in enumerate(flow_version_ids)
    ]
    indexed_flow_version_ids_cte = (
        indexed_selects[0] if len(indexed_selects) == 1 else union_all(*indexed_selects)
    ).cte("indexed_flow_version_ids")

    statement = (
        select(
            indexed_flow_version_ids_cte.c.position,
            FlowVersion.id.label("flow_version_id"),
            FlowVersion.data.label("flow_version_data"),
            FlowVersion.version_number.label("flow_version_number"),
            Flow.id.label("flow_id"),
            Flow.name.label("flow_name"),
            Flow.description.label("flow_description"),
            Flow.tags.label("flow_tags"),
            Flow.folder_id.label("project_id"),
        )
        .select_from(indexed_flow_version_ids_cte)
        .join(FlowVersion, and_(FlowVersion.id == indexed_flow_version_ids_cte.c.flow_version_id))
        .join(Flow, and_(Flow.id == FlowVersion.flow_id))
        .order_by(indexed_flow_version_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(flow_version_ids):
        msg = "One or more flow version ids are invalid."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    artifacts: list[tuple[UUID, int, BaseFlowArtifact]] = []
    for row in rows:
        if row.flow_version_data is None:
            msg = f"Flow version {row.flow_version_id} has no data (snapshot may be corrupted)."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        artifacts.append(
            (
                row.flow_version_id,
                row.flow_version_number,
                BaseFlowArtifact(
                    id=row.flow_id,
                    name=row.flow_name,
                    description=row.flow_description,
                    data=row.flow_version_data,
                    tags=row.flow_tags,
                    provider_data={"project_id": str(row.project_id)},
                ),
            )
        )
    return artifacts
