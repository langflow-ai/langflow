"""Read-mostly HTTP surface for the in-flow trigger feature.

Creation lives in the flow canvas: a user drops a CronTrigger
component, fills in its inputs, saves the flow. This module surfaces
the resulting state for a management UI:

    GET    /api/v1/triggers
           One row per CronTrigger component across the current user's
           flows. Combines live config (read from ``flow.data``) with
           the most recent ``trigger_job`` rows so the list view can
           render "next fire" and "last run" columns.

    DELETE /api/v1/triggers/{flow_id}/{component_id}
           Strip a single CronTrigger node from a flow. The lifecycle
           hook on the subsequent save cancels its queued job rows.
           Returns 404 when the flow or the component cannot be
           found for the current user.

    DELETE /api/v1/triggers
           Bulk strip: remove every CronTrigger node from every flow
           the current user owns. Idempotent — re-running on a
           cleaned-up set is a no-op and still returns 200.

    GET    /api/v1/triggers/{flow_id}/{component_id}/jobs
           Recent ``trigger_job`` rows for one component, descending
           ``scheduled_at``. Used by the per-trigger history drawer.

There are no POST / PATCH / PUT endpoints by design: the canvas is the
single editing surface for trigger configuration.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.crud import list_jobs_for_flow
from langflow.services.database.models.triggers.model import TriggerJobRead
from langflow.services.triggers.queries import (
    TriggerInstance,
    list_triggers_for_user,
)
from langflow.services.triggers.removal import (
    remove_all_cron_trigger_nodes,
    remove_cron_trigger_node,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


router = APIRouter(prefix="/triggers", tags=["Triggers"])


# --------------------------------------------------------------------------- #
#  Response schemas (kept minimal & inline — no separate Pydantic dance)
# --------------------------------------------------------------------------- #


def _serialize_instance(instance: TriggerInstance) -> dict:
    """``dataclasses.asdict`` plus JSON-friendly types for datetimes/UUIDs."""
    raw = asdict(instance)
    return {
        **raw,
        "flow_id": str(instance.flow_id),
        "next_fire_at": _iso(instance.next_fire_at),
        "last_finished_at": _iso(instance.last_finished_at),
        "last_finished_status": (
            instance.last_finished_status.value if instance.last_finished_status else None
        ),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# --------------------------------------------------------------------------- #
#  Helpers shared by the routes
# --------------------------------------------------------------------------- #


async def _get_owned_flow(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
) -> Flow:
    """Fetch a flow restricted to ``user_id``; 404 on miss.

    Centralises the ownership check so every route enforces it the
    same way and the response payloads do not need to redo the
    cross-user → 404 mapping inline.
    """
    statement = select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id)
    flow = (await session.exec(statement)).first()
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    return flow


async def _persist_flow_data_change(session: AsyncSession, flow: Flow) -> None:
    """Save the in-memory flow.data mutation back through the same hooks the API uses.

    Importing the helper inside the function avoids a hard module-load
    coupling between this route and ``flows_helpers`` (which itself
    imports from the triggers services package).
    """
    from langflow.api.v1.flows_helpers import _patch_flow
    from langflow.services.database.models.flow.model import FlowUpdate

    update = FlowUpdate(data=flow.data)
    from langflow.services.deps import get_storage_service

    storage_service = get_storage_service()
    await _patch_flow(
        session=session,
        db_flow=flow,
        flow=update,
        user_id=flow.user_id,
        storage_service=storage_service,
    )


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[dict])
async def list_triggers(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> list[dict]:
    """All CronTrigger components the current user has across all flows."""
    instances = await list_triggers_for_user(session, current_user.id)
    return [_serialize_instance(i) for i in instances]


@router.delete("/{flow_id}/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID,
    component_id: str,
) -> None:
    """Strip one CronTrigger node from a flow.

    The post-save lifecycle hook downgrades the trigger's queued jobs
    to ``cancelled``, so no manual cascade is needed here.
    """
    flow = await _get_owned_flow(session, flow_id, current_user.id)
    new_data, was_removed = remove_cron_trigger_node(flow.data, component_id)
    if not was_removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trigger component not found in this flow",
        )
    flow.data = new_data
    await _persist_flow_data_change(session, flow)


@router.delete("", response_model=dict, status_code=status.HTTP_200_OK)
async def delete_all_triggers(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> dict:
    """Remove every CronTrigger component from every flow the user owns.

    Returns ``{"flows_updated": int, "components_removed": int}`` so the
    UI can show a meaningful confirmation toast.
    """
    statement = select(Flow).where(Flow.user_id == current_user.id)
    flows = list((await session.exec(statement)).all())

    flows_updated = 0
    components_removed = 0
    for flow in flows:
        new_data, removed_ids = remove_all_cron_trigger_nodes(flow.data)
        if not removed_ids:
            continue
        flow.data = new_data
        await _persist_flow_data_change(session, flow)
        flows_updated += 1
        components_removed += len(removed_ids)

    return {"flows_updated": flows_updated, "components_removed": components_removed}


@router.get("/{flow_id}/{component_id}/jobs", response_model=list[TriggerJobRead])
async def list_trigger_jobs(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID,
    component_id: str,
    status_filter: JobStatus | None = None,
    limit: int = 50,
):
    """Recent trigger_jobs for one component on one flow."""
    await _get_owned_flow(session, flow_id, current_user.id)
    return await list_jobs_for_flow(
        session,
        flow_id,
        component_id=component_id,
        status=status_filter,
        limit=limit,
    )
