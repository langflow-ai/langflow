"""Routes that exist because two people can edit one flow.

Kept out of ``flows.py``: that module was already well past the file-size limit
before this feature, and these endpoints share no state with it.
"""

from __future__ import annotations

import copy
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.utils.mcp.flow_secrets import persist_and_strip_mcp_secrets
from langflow.api.v1.authz_route_dependencies import AuthorizedReadFlow, AuthorizedWriteFlow
from langflow.api.v1.flow_conflict import (
    FlowVersionState,
    build_version_state,
    claim_version_token,
    parse_if_match,
)
from langflow.api.v1.flow_fork import FlowFork, build_fork_payload
from langflow.api.v1.flows import _validate_catalog_policy_for_write
from langflow.api.v1.flows_helpers import _new_flow, _patch_flow
from langflow.services.audit.events import REASON_OVERWRITE
from langflow.services.database.models.flow.model import FlowRead, FlowUpdate
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.exceptions import FlowVersionError
from langflow.services.deps import get_catalog_policy_service, get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(prefix="/flows", tags=["Flows"])


@router.get("/{flow_id}/version-state", response_model=FlowVersionState, status_code=200)
async def read_flow_version_state(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001
    flow: AuthorizedReadFlow,
):
    """Report which version of a flow is current, and who last changed it."""
    return await build_version_state(session, flow)


@router.post("/{flow_id}/fork", response_model=FlowRead, status_code=201)
async def fork_flow(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001
    flow: AuthorizedReadFlow,
    fork: FlowFork,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Create an inert copy of a flow, optionally carrying a caller-supplied graph.

    Read access is deliberately enough: anyone who can open a flow can already
    export it and import the result, so requiring write here would block the
    conflict dialog's only exit without protecting anything. The copy is owned by
    whoever forked it and inherits no exposure from the source.
    """
    payload = build_fork_payload(flow, fork)
    _validate_catalog_policy_for_write(payload.data, snapshot=get_catalog_policy_service().snapshot)
    await persist_and_strip_mcp_secrets(payload.data, current_user.id, session)

    # Two forks that start together both read "no such name yet" and both try to
    # write it. Retrying inside this request deadlocks on SQLite -- the loser waits
    # on a write lock the winner only releases at commit -- so the collision is
    # reported as the conflict it is, and the client is the one that tries again.
    try:
        return await _new_flow(
            session=session,
            flow=payload,
            user_id=current_user.id,
            storage_service=storage_service,
            propagate_unhandled_errors=True,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Another copy took that name first. Try duplicating again.",
        ) from exc


class FlowOverwrite(BaseModel):
    """The merged graph a person chose to write over the version they reviewed."""

    data: dict


@router.post("/{flow_id}/overwrite", response_model=FlowRead, status_code=200)
async def overwrite_flow(
    *,
    session: DbSession,
    flow_id: UUID,  # noqa: ARG001
    flow: AuthorizedWriteFlow,
    overwrite: FlowOverwrite,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
):
    """Replace a flow with a merged graph, keeping the replaced version in history.

    This is the deliberate half of the conflict dialog, and it is still guarded.
    The caller sends the token it *reviewed*, not the stale one it was refused on
    and not nothing at all: writing unconditionally here would silently discard a
    fourth writer who landed while the dialog was open, reopening the lost update
    the whole feature exists to close. So the meaning is "replace the version I
    just looked at", and a flow that moved again is refused with a fresh 409.

    The archived entry is attributed to whoever last wrote the flow rather than to
    the caller, because it is their work being replaced -- attributing it here
    would put the caller's name on someone else's version and defeat the point of
    keeping it.

    The write right is claimed before anything is archived. Archiving first and
    letting the refusal roll it back does not work: version entries are written in
    a ``begin_nested()`` savepoint that survives the outer rollback, so a refused
    overwrite left an orphan version in someone's history. Claiming first means a
    stale caller is turned away before a single row is written.
    """
    expected = parse_if_match(if_match)
    if expected is None:
        raise HTTPException(
            status_code=428,
            detail=(
                "Overwriting requires an If-Match header naming the version you reviewed. "
                "Without it this write would silently discard anyone who saved in the meantime."
            ),
        )
    _validate_catalog_policy_for_write(overwrite.data, snapshot=get_catalog_policy_service().snapshot)

    try:
        replaced_data = copy.deepcopy(flow.data)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Flow data could not be copied before overwriting. The data may be corrupted.",
        ) from exc

    claimed = await claim_version_token(session, flow, expected)

    try:
        await create_flow_version_entry(
            session,
            flow_id=flow.id,
            user_id=flow.last_modified_by or flow.user_id,
            data=replaced_data,
            description="Replaced by a newer edit",
        )
    except FlowVersionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await persist_and_strip_mcp_secrets(overwrite.data, current_user.id, session)
    return await _patch_flow(
        session=session,
        db_flow=flow,
        flow=FlowUpdate(data=overwrite.data),
        user_id=current_user.id,
        storage_service=storage_service,
        expected_version_token=claimed,
        audit_reason=REASON_OVERWRITE,
    )
