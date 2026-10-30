"""Pin the exact flow version a run executes, and release it when no run needs it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.database.models.evaluation import EvaluationRun
from langflow.services.database.models.flow_version.crud import create_flow_version_entry, set_flow_version_retained
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.evaluations.errors import EvalsNotFoundError
from langflow.services.session.utils import compute_dict_hash

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow

RETAINED_REASON = "evaluation"
SNAPSHOT_DESCRIPTION = "Evaluation run"


async def _latest_version(session: AsyncSession, flow_id: UUID) -> FlowVersion | None:
    stmt = (
        select(FlowVersion)
        .where(FlowVersion.flow_id == flow_id)
        .order_by(col(FlowVersion.version_number).desc())
        .limit(1)
    )
    return (await session.exec(stmt)).first()


async def _retain(session: AsyncSession, version: FlowVersion) -> None:
    # A version already retained for another reason (a trigger pin, a deployment) keeps that reason.
    if not version.retained:
        await set_flow_version_retained(session, version.id, retained=True, reason=RETAINED_REASON)


async def pin_latest(session: AsyncSession, flow: Flow, user_id: UUID) -> FlowVersion:
    """Reuse the newest snapshot when it matches the draft, otherwise snapshot the draft."""
    latest = await _latest_version(session, flow.id)
    if (
        latest is not None
        and latest.data is not None
        and compute_dict_hash(latest.data) == compute_dict_hash(flow.data or {})
    ):
        await _retain(session, latest)
        return latest
    version = await create_flow_version_entry(
        session, flow.id, user_id, flow.data, description=SNAPSHOT_DESCRIPTION, prune=False
    )
    await _retain(session, version)
    return version


async def pin_history_version(session: AsyncSession, flow_id: UUID, version_id: UUID) -> FlowVersion:
    version = (
        await session.exec(select(FlowVersion).where(FlowVersion.id == version_id, FlowVersion.flow_id == flow_id))
    ).first()
    if version is None or version.data is None:
        msg = "Flow version not found"
        raise EvalsNotFoundError(msg)
    await _retain(session, version)
    return version


async def release_unused_versions(session: AsyncSession, version_ids: set[UUID]) -> None:
    """Clear the evaluation retention on versions no remaining run references."""
    if not version_ids:
        return
    still_used = set(
        (
            await session.exec(
                select(EvaluationRun.flow_version_id).where(col(EvaluationRun.flow_version_id).in_(list(version_ids)))
            )
        ).all()
    )
    for version_id in version_ids - still_used:
        version = (await session.exec(select(FlowVersion).where(FlowVersion.id == version_id))).first()
        if version is not None and version.retained and version.retained_reason == RETAINED_REASON:
            await set_flow_version_retained(session, version_id, retained=False)
