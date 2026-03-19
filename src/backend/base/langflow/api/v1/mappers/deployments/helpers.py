"""Shared mapper helpers for deployment flow-version resolution."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from lfx.services.adapters.deployment.schema import BaseFlowArtifact
from sqlalchemy import and_, literal, union_all
from sqlmodel import func, select

from langflow.services.database.models.deployment.model import Deployment
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion


def parse_flow_version_reference_ids(reference_ids: list[UUID | str]) -> list[UUID]:
    """Normalize UUID/string references into validated flow-version UUIDs."""
    flow_version_ids: list[UUID] = []
    for flow_version_ref in reference_ids:
        if isinstance(flow_version_ref, UUID):
            flow_version_ids.append(flow_version_ref)
            continue
        flow_version_ref_str = str(flow_version_ref).strip()
        try:
            flow_version_ids.append(UUID(flow_version_ref_str))
        except ValueError as exc:
            msg = f"Invalid flow version id: {flow_version_ref}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg) from exc
    return flow_version_ids


def _build_indexed_flow_version_ids_cte(*, flow_version_ids: list[UUID]):
    indexed_selects = [
        select(literal(index).label("position"), literal(flow_version_id).label("flow_version_id"))
        for index, flow_version_id in enumerate(flow_version_ids)
    ]
    return (indexed_selects[0] if len(indexed_selects) == 1 else union_all(*indexed_selects)).cte(
        "indexed_flow_version_ids"
    )


async def build_flow_artifacts_from_flow_versions(
    *,
    db,
    user_id: UUID,
    deployment_db_id: UUID,
    flow_version_ids: list[UUID],
) -> list[tuple[UUID, int, UUID, BaseFlowArtifact]]:
    """Resolve deployment-scoped flow version ids into artifacts preserving input order."""
    if not flow_version_ids:
        return []

    indexed_flow_version_ids_cte = _build_indexed_flow_version_ids_cte(flow_version_ids=flow_version_ids)

    statement = (
        select(
            indexed_flow_version_ids_cte.c.position,
            FlowVersion.id.label("flow_version_id"),
            FlowVersion.data.label("flow_version_data"),
            FlowVersion.version_number.label("flow_version_number"),
            Flow.folder_id.label("project_id"),
            Flow.id.label("flow_id"),
            Flow.name.label("flow_name"),
            Flow.description.label("flow_description"),
            Flow.tags.label("flow_tags"),
        )
        .select_from(indexed_flow_version_ids_cte)
        .join(
            FlowVersion,
            and_(
                FlowVersion.id == indexed_flow_version_ids_cte.c.flow_version_id,
                FlowVersion.user_id == user_id,
            ),
        )
        .join(
            Flow,
            and_(
                Flow.id == FlowVersion.flow_id,
                Flow.user_id == user_id,
            ),
        )
        .join(
            Deployment,
            and_(
                Deployment.id == deployment_db_id,
                Deployment.user_id == user_id,
                Deployment.project_id == Flow.folder_id,
            ),
        )
        .order_by(indexed_flow_version_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(flow_version_ids):
        msg = "One or more flow version ids are invalid."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    artifacts: list[tuple[UUID, int, UUID, BaseFlowArtifact]] = []
    for row in rows:
        if row.flow_version_data is None:
            msg = f"Flow version {row.flow_version_id} has no data (snapshot may be corrupted)."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        artifacts.append(
            (
                row.flow_version_id,
                row.flow_version_number,
                row.project_id,
                BaseFlowArtifact(
                    id=row.flow_id,
                    name=row.flow_name,
                    description=row.flow_description,
                    data=row.flow_version_data,
                    tags=row.flow_tags,
                ),
            )
        )
    return artifacts


async def build_project_scoped_flow_artifacts_from_flow_versions(
    *,
    db,
    user_id: UUID,
    project_id: UUID,
    reference_ids: list[UUID | str],
) -> list[tuple[UUID, BaseFlowArtifact]]:
    """Resolve project-scoped flow version references preserving input order."""
    flow_version_ids = parse_flow_version_reference_ids(reference_ids)
    if not flow_version_ids:
        return []
    indexed_flow_version_ids_cte = _build_indexed_flow_version_ids_cte(flow_version_ids=flow_version_ids)

    statement = (
        select(
            indexed_flow_version_ids_cte.c.position,
            FlowVersion.id.label("flow_version_id"),
            FlowVersion.data.label("flow_version_data"),
            Flow.id.label("flow_id"),
            Flow.name.label("flow_name"),
            Flow.description.label("flow_description"),
            Flow.tags.label("flow_tags"),
        )
        .select_from(indexed_flow_version_ids_cte)
        .join(
            FlowVersion,
            and_(
                FlowVersion.user_id == user_id,
                FlowVersion.id == indexed_flow_version_ids_cte.c.flow_version_id,
            ),
        )
        .join(
            Flow,
            and_(
                Flow.id == FlowVersion.flow_id,
                Flow.user_id == user_id,
                Flow.folder_id == project_id,
            ),
        )
        .order_by(indexed_flow_version_ids_cte.c.position)
    )
    rows = list((await db.exec(statement)).all())
    if len(rows) < len(flow_version_ids):
        msg = "One or more flow version ids are not checkpoints of flows in the selected project."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    artifacts: list[tuple[UUID, BaseFlowArtifact]] = []
    for row in rows:
        if row.flow_version_data is None:
            msg = f"Flow version {row.flow_version_id} has no data (snapshot may be corrupted)."
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
        artifacts.append(
            (
                row.flow_version_id,
                BaseFlowArtifact(
                    id=row.flow_id,
                    name=row.flow_name,
                    description=row.flow_description,
                    data=row.flow_version_data,
                    tags=row.flow_tags,
                ),
            )
        )
    return artifacts


async def validate_project_scoped_flow_version_ids(
    *,
    flow_version_ids: list[UUID],
    user_id: UUID,
    project_id: UUID,
    db,
) -> None:
    """Ensure all flow-version ids belong to flows in a specific project."""
    if not flow_version_ids:
        return
    unique_flow_version_ids = list(dict.fromkeys(flow_version_ids))
    matched_count = int(
        (
            await db.exec(
                select(func.count(FlowVersion.id))
                .select_from(FlowVersion)
                .join(
                    Flow,
                    and_(
                        Flow.id == FlowVersion.flow_id,
                        Flow.user_id == user_id,
                        Flow.folder_id == project_id,
                    ),
                )
                .where(
                    FlowVersion.user_id == user_id,
                    FlowVersion.id.in_(unique_flow_version_ids),
                )
            )
        ).one()
        or 0
    )
    if matched_count != len(unique_flow_version_ids):
        msg = "One or more flow version ids are not checkpoints of flows in the selected project."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
