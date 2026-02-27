from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from lfx.log import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.utils.core import has_api_terms, remove_api_keys
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow_history.crud import (
    create_flow_history_entry,
    delete_flow_history_entry,
    get_flow_history_counts_by_deployment_ids,
    get_flow_history_entry_or_raise,
    get_flow_history_list,
)
from langflow.services.database.models.flow_history.exceptions import (
    FlowHistoryDataTooLargeError,
    FlowHistoryError,
    FlowHistoryNotFoundError,
    FlowHistorySerializationError,
    FlowHistoryVersionConflictError,
)
from langflow.services.database.models.flow_history.model import (
    FlowHistory,
    FlowHistoryCreate,
    FlowHistoryListResponse,
    FlowHistoryRead,
    FlowHistoryReadWithData,
)
from langflow.services.deps import get_settings_service, get_variable_service

router = APIRouter(prefix="/flows/{flow_id}/history", tags=["Flow History"])
_VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def strip_history_data(data: dict | None) -> dict | None:
    """Strip API keys from a history entry's flow data dict.

    Returns None on unexpected failure to prevent secret leakage.
    """
    if data is None:
        return None
    data_copy = copy.deepcopy(data)
    try:
        return remove_api_keys({"data": data_copy}).get("data")
    except Exception:
        logger.warning(
            "Failed to strip API keys from history data — excluding data from export to prevent secret leakage",
            exc_info=True,
        )
        return None


def _is_valid_variable_reference_name(value: str) -> bool:
    return bool(_VARIABLE_NAME_RE.fullmatch(value))


def _restore_valid_global_variable_references(
    *,
    original_data: dict[str, Any] | None,
    stripped_data: dict[str, Any] | None,
    allowed_variable_names: set[str],
) -> dict[str, Any] | None:
    if not isinstance(original_data, dict) or not isinstance(stripped_data, dict):
        return stripped_data

    original_nodes = original_data.get("nodes")
    stripped_nodes = stripped_data.get("nodes")
    if not isinstance(original_nodes, list) or not isinstance(stripped_nodes, list):
        return stripped_data

    for original_node, stripped_node in zip(original_nodes, stripped_nodes, strict=False):
        if not isinstance(original_node, dict) or not isinstance(stripped_node, dict):
            continue

        original_template = original_node.get("data", {}).get("node", {}).get("template")
        stripped_template = stripped_node.get("data", {}).get("node", {}).get("template")
        if not isinstance(original_template, dict) or not isinstance(stripped_template, dict):
            continue

        for field_name, stripped_field in stripped_template.items():
            original_field = original_template.get(field_name)
            if not isinstance(stripped_field, dict) or not isinstance(original_field, dict):
                continue
            if not (
                isinstance(original_field.get("name"), str)
                and has_api_terms(original_field["name"])
                and original_field.get("password")
                and original_field.get("load_from_db") is True
            ):
                continue

            reference_value = original_field.get("value")
            if (
                isinstance(reference_value, str)
                and _is_valid_variable_reference_name(reference_value)
                and reference_value in allowed_variable_names
            ):
                stripped_field["value"] = reference_value

    return stripped_data


def _history_to_read(entry: FlowHistory) -> FlowHistoryRead:
    return FlowHistoryRead.model_validate(entry, from_attributes=True)


def _history_to_read_full(entry: FlowHistory, *, strip_keys: bool = False) -> FlowHistoryReadWithData:
    result = FlowHistoryReadWithData.model_validate(entry, from_attributes=True)
    if strip_keys:
        result.data = strip_history_data(result.data)
    return result


async def _get_user_flow(session: AsyncSession, flow_id: UUID, user_id: UUID) -> Flow:
    result = await session.exec(select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id))
    flow = result.first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


def _translate_history_error(exc: FlowHistoryError) -> HTTPException:
    """Translate a domain exception into an HTTPException."""
    if isinstance(exc, FlowHistorySerializationError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, FlowHistoryDataTooLargeError):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, FlowHistoryVersionConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, FlowHistoryNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/")
async def list_flow_history(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    deployment_ids: Annotated[list[UUID] | None, Query()] = None,
) -> FlowHistoryListResponse:
    normalized_deployment_ids = list(dict.fromkeys(deployment_ids or []))
    await _get_user_flow(session, flow_id, current_user.id)
    entries = await get_flow_history_list(
        session,
        flow_id,
        current_user.id,
        limit,
        offset,
        deployment_ids=normalized_deployment_ids or None,
    )
    deployment_counts: dict[str, int] | None = None
    if normalized_deployment_ids:
        counts = await get_flow_history_counts_by_deployment_ids(
            session,
            flow_id=flow_id,
            user_id=current_user.id,
            deployment_ids=normalized_deployment_ids,
        )
        deployment_counts = {str(deployment_uuid): 0 for deployment_uuid in normalized_deployment_ids}
        deployment_counts.update({str(deployment_uuid): count for deployment_uuid, count in counts.items()})
    max_entries = get_settings_service().settings.max_flow_history_entries_per_flow
    return FlowHistoryListResponse(
        entries=[_history_to_read(e) for e in entries],
        max_entries=max_entries,
        deployment_counts=deployment_counts,
    )


# TODO: Full-history export endpoint (export flow with all history entries embedded).
# This is planned as a follow-up feature. The per-version export (exporting a single
# version as a standalone flow) is available via the GET /{history_id} endpoint.


@router.get("/{history_id}")
async def get_single_flow_history(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSessionReadOnly,
) -> FlowHistoryReadWithData:
    await _get_user_flow(session, flow_id, current_user.id)
    try:
        entry = await get_flow_history_entry_or_raise(session, history_id, current_user.id, flow_id=flow_id)
    except FlowHistoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="History entry not found") from exc
    result = _history_to_read_full(entry, strip_keys=True)
    if isinstance(entry.data, dict) and isinstance(result.data, dict):
        try:
            variable_names = await get_variable_service().list_variables(current_user.id, session)
            allowed_variable_names = {
                name for name in variable_names if isinstance(name, str) and _is_valid_variable_reference_name(name)
            }
            result.data = _restore_valid_global_variable_references(
                original_data=entry.data,
                stripped_data=result.data,
                allowed_variable_names=allowed_variable_names,
            )
        except Exception:
            logger.warning(
                "Failed to validate global-variable references in history response; returning masked data only",
                exc_info=True,
            )
    return result


@router.post("/", status_code=201)
async def create_snapshot(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    body: FlowHistoryCreate | None = None,
) -> FlowHistoryRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)
    description = body.description if body else None
    try:
        data = copy.deepcopy(flow.data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Flow data could not be copied for snapshot. The data may be corrupted.",
        ) from exc
    try:
        entry = await create_flow_history_entry(
            session,
            flow_id=flow.id,
            user_id=current_user.id,
            data=data,
            description=description,
        )
    except FlowHistoryError as exc:
        raise _translate_history_error(exc) from exc
    return _history_to_read(entry)


@router.post("/{history_id}/activate")
async def activate_version(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    *,
    save_draft: Annotated[bool, Query()] = True,
) -> FlowRead:
    flow = await _get_user_flow(session, flow_id, current_user.id)

    # Verify history entry belongs to this flow
    try:
        target_entry = await get_flow_history_entry_or_raise(session, history_id, current_user.id, flow_id=flow_id)
    except FlowHistoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="History entry not found") from exc

    # Guard against activating a version with no data (check before auto-snapshot)
    if target_entry.data is None:
        raise HTTPException(status_code=400, detail="Cannot activate a version with no data")

    # Capture copies of both data dicts before the savepoint to avoid stale
    # reads if pruning inside create_flow_history_entry deletes old entries.
    try:
        current_data = copy.deepcopy(flow.data) if save_draft else None
        target_data = copy.deepcopy(target_entry.data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Flow data could not be copied. The data may be corrupted.",
        ) from exc

    # Wrap auto-snapshot + flow overwrite in a single savepoint for atomicity.
    # If the flow update fails, the auto-snapshot is also rolled back.
    try:
        async with session.begin_nested():
            if save_draft and current_data is not None:
                await create_flow_history_entry(
                    session,
                    flow_id=flow.id,
                    user_id=current_user.id,
                    data=current_data,
                    description=f"Auto-saved before activating v{target_entry.version_number}",
                )

            flow.data = target_data
            flow.updated_at = datetime.now(timezone.utc)

            session.add(flow)
            await session.flush()
    except FlowHistoryError as exc:
        raise _translate_history_error(exc) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Could not activate version — the flow was modified concurrently. Please try again.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Database error while activating version. Please try again.",
        ) from exc

    await logger.adebug("Activated version %s (%s) for flow %s", history_id, f"v{target_entry.version_number}", flow_id)

    return FlowRead.model_validate(flow, from_attributes=True)


@router.delete("/{history_id}", status_code=204)
async def delete_history_entry(
    flow_id: UUID,
    history_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> None:
    await _get_user_flow(session, flow_id, current_user.id)

    # Verify entry belongs to this flow, then delete
    try:
        await get_flow_history_entry_or_raise(session, history_id, current_user.id, flow_id=flow_id)
        await delete_flow_history_entry(session, history_id, current_user.id)
    except FlowHistoryError as exc:
        raise _translate_history_error(exc) from exc
    await logger.adebug("Deleted history entry %s for flow %s", history_id, flow_id)
