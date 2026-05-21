"""HTTP surface for the in-flow trigger feature.

Triggers live as CronTrigger components inside flow.data; this module
exposes a read-mostly surface plus a single creation endpoint that
materialises a CronTrigger node inside a target flow on behalf of
the user (the same effect as dragging the component on the canvas
and saving).

    GET    /api/v1/triggers
           One row per CronTrigger component across the current user's
           flows. Combines live config (read from ``flow.data``) with
           the most recent ``trigger_job`` rows so the list view can
           render "next fire" and "last run" columns.

    POST   /api/v1/triggers
           Create a CronTrigger node inside a target flow. Returns the
           ``TriggerInstance`` for the freshly-created node. 409 if
           the target flow already has a CronTrigger (singleton).

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

The canvas remains the primary editing surface for trigger
configuration; this POST endpoint just spares the user the
canvas round-trip when they only need to schedule an existing flow.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from lfx.components.triggers.constants import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
    MAX_ATTEMPTS_LIMIT,
)
from lfx.components.triggers.cron_builder import (
    INTERVAL_UNITS,
    UNIT_MINUTES,
    compose_cron,
)
from pydantic import BaseModel, Field
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.crud import list_jobs_for_flow
from langflow.services.database.models.triggers.model import TriggerJobRead
from langflow.services.triggers.discovery import find_cron_trigger_nodes
from langflow.services.triggers.node_factory import (
    CronTriggerNodeConfig,
    append_node_to_flow_data,
    build_cron_trigger_node,
)
from langflow.services.triggers.queries import (
    TriggerInstance,
    list_triggers_for_user,
)
from langflow.services.triggers.removal import (
    remove_all_cron_trigger_nodes,
    remove_cron_trigger_node,
)
from langflow.services.triggers.scheduler import (
    InvalidTriggerConfigError,
    validate_trigger_config,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


router = APIRouter(prefix="/triggers", tags=["Triggers"])


# --------------------------------------------------------------------------- #
#  Request / response schemas (kept inline — no separate Pydantic dance)
# --------------------------------------------------------------------------- #


class TriggerCreateRequest(BaseModel):
    """Body of ``POST /api/v1/triggers``.

    Mirrors the canvas component's controls one-to-one so the modal
    on the frontend can submit the same shape it edits.
    """

    flow_id: UUID
    at_specific_time: bool = False
    interval_value: int = Field(5, ge=1, le=59)
    interval_unit: str = UNIT_MINUTES
    time_of_day: str = "09:00"
    timezone: str = DEFAULT_TIMEZONE
    max_attempts: int = Field(DEFAULT_MAX_ATTEMPTS, ge=1, le=MAX_ATTEMPTS_LIMIT)


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


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    body: TriggerCreateRequest,
) -> dict:
    """Append a CronTrigger node to an existing flow.

    Same effect as dragging the component on the canvas and saving:
    the lifecycle hook in ``flows_helpers`` picks the new node up and
    enqueues the first ``trigger_job`` row at the next fire time.

    Validation:
      * 404 — flow not found (or not owned by ``current_user``).
      * 409 — flow already contains a CronTrigger node (singleton).
      * 400 — bad ``interval_unit``, unparseable time / timezone, or
        any combination ``compose_cron`` rejects.
    """
    if body.interval_unit not in INTERVAL_UNITS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"interval_unit must be one of {list(INTERVAL_UNITS)}",
        )

    flow = await _get_owned_flow(session, body.flow_id, current_user.id)
    if find_cron_trigger_nodes(flow.data):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Flow already has a Cron Trigger",
        )

    # Reuse the canvas-side cron builder so the derived cron matches
    # exactly what the same controls would produce on the canvas.
    cron_expression = compose_cron(
        at_specific_time=body.at_specific_time,
        interval_value=body.interval_value,
        interval_unit=body.interval_unit,
        time_of_day=body.time_of_day,
    )
    try:
        validate_trigger_config(
            cron_expression=cron_expression,
            timezone_name=body.timezone,
        )
    except InvalidTriggerConfigError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    config = CronTriggerNodeConfig(
        at_specific_time=body.at_specific_time,
        interval_value=body.interval_value,
        interval_unit=body.interval_unit,
        time_of_day=body.time_of_day,
        timezone=body.timezone,
        max_attempts=body.max_attempts,
    )
    node = build_cron_trigger_node(config)
    flow.data = append_node_to_flow_data(flow.data, node)
    await _persist_flow_data_change(session, flow)

    # Return the newly-materialised TriggerInstance so the client can
    # render the new row without re-fetching the whole list.
    instances = await list_triggers_for_user(session, current_user.id)
    fresh = next(
        (i for i in instances if i.flow_id == body.flow_id and i.component_id == node["id"]),
        None,
    )
    if fresh is None:
        # Defensive: persist + lifecycle should always leave the new
        # node visible to the aggregator. Treat the absence as an
        # internal error so the caller knows the resource is in an
        # unexpected state.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trigger created but could not be located in the aggregator",
        )
    return _serialize_instance(fresh)


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
