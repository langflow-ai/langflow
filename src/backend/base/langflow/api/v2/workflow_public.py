"""V2 public workflow endpoint.

Counterpart of ``/api/v1/build_public_tmp/{flow_id}/flow`` for the v2
streaming pipeline. The shareable playground POSTs here so visitors can
run a public flow without owning it.

The body is intentionally narrower than ``/api/v2/workflows`` (no
``data``, no ``tweaks``): visitors must never override the stored flow
definition. The handler also enforces the public-access mitigations:

- ``access_type == PUBLIC`` (others 403, checked before any policy
  validation so private flows leak nothing about themselves).
- Per-visitor ``virtual_flow_id = uuid5(identifier, flow_id)`` used as
  the storage flow_id, mirroring v1's build_public_tmp.
- Caller-supplied ``session_id`` namespaced under the virtual flow id
  (CVE-2026-33017).
- File-path validation (GHSA-rcjh-r59h-gq37).
- AUTO_LOGIN parity: when ``AUTO_LOGIN=true`` the backend ignores
  ``authenticated_user.id`` and uses ``client_id`` for the UUID v5
  derivation, matching the frontend's ``useGetFlowId`` so the popup's
  chat-view filter actually matches what the backend stores.
- Owner impersonation: the run executes under the flow owner's
  permissions, never the visitor's.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import EventSourceResponse
from lfx.schema.workflow import (
    WORKFLOW_EXECUTION_RESPONSES,
    PublicWorkflowRunRequest,
)
from lfx.utils.flow_validation import CustomComponentValidationError, validate_flow_for_current_settings

from langflow.api.utils.flow_utils import (
    scope_session_to_namespace,
    validate_public_files,
    verify_public_flow_and_get_user,
)
from langflow.api.v2.adapters import (
    STREAM_ADAPTERS,
    StreamAdapterContext,
    UnknownStreamProtocolError,
    available_protocols,
    get_stream_adapter,
)
from langflow.api.v2.converters import ParsedWorkflowRun
from langflow.services.auth.utils import get_current_user_optional
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import get_settings_service, session_scope

router = APIRouter(prefix="/workflows/public", tags=["Workflow (public)"])


@router.post(
    "",
    responses=WORKFLOW_EXECUTION_RESPONSES,
    summary="Execute Public Workflow",
    description=(
        "Stream a public flow on behalf of a shareable-playground visitor. "
        "Mirrors the security posture of /api/v1/build_public_tmp."
    ),
)
async def execute_public_workflow(
    request: PublicWorkflowRunRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    authenticated_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> EventSourceResponse:
    """Run a PUBLIC flow on behalf of a shareable-playground visitor.

    Stream-mode only. The handler enforces all of the public-access
    mitigations documented in the module docstring before any flow
    execution begins.
    """
    # Lazy-import to avoid the circular ``v2.workflow`` -> ``api.build`` ->
    # ``v1.chat`` -> ``api.build`` cycle that fires when ``v2.__init__`` is
    # collected at import time.
    from langflow.api.v2.workflow import _stream_event_frames, _unknown_protocol_http_exception

    real_flow_id = UUID(request.flow_id)

    # Mirror v1 ``build_public_tmp`` error contract: blocked-component
    # validation must surface as a sanitized 400 (the raw message names
    # the disabled component classes); other ValueErrors from the gate
    # sequence become 400 with the message preserved.
    try:
        # File path validation — done before any DB lookup so malformed
        # requests fail fast and don't touch the database (GHSA-rcjh-r59h-gq37).
        validate_public_files(request.files, real_flow_id)

        # Identifier resolution. The frontend's ``useGetFlowId`` uses
        # ``client_id`` for the UUID v5 derivation when AUTO_LOGIN is on,
        # so the backend must match here or the popup's chat-view filter
        # would drop every broadcast message.
        client_id = http_request.cookies.get("client_id")
        auth_settings = get_settings_service().auth_settings
        authenticated_user_id = authenticated_user.id if authenticated_user and not auth_settings.AUTO_LOGIN else None

        # access_type == PUBLIC + virtual_flow_id, run as the flow owner.
        owner_user, virtual_flow_id = await verify_public_flow_and_get_user(
            flow_id=real_flow_id,
            client_id=client_id,
            authenticated_user_id=authenticated_user_id,
        )

        # Defends CVE-2026-33017: scope caller's session into the (identifier, flow_id) namespace.
        scoped_session = (
            scope_session_to_namespace(request.session_id, str(virtual_flow_id))
            if request.session_id is not None
            else None
        )

        # Validate stored flow data after the public-access gate so private
        # flows never trigger validation side effects.
        async with session_scope() as session:
            flow = await session.get(Flow, real_flow_id)
            if flow and flow.data:
                validate_flow_for_current_settings(flow.data)
            flow_name = flow.name if flow else None
    except CustomComponentValidationError as exc:
        # The raw message embeds the blocked component class names; do
        # not leak it to an anonymous visitor.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This flow cannot be executed.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if request.stream_protocol not in STREAM_ADAPTERS:
        raise _unknown_protocol_http_exception(
            UnknownStreamProtocolError(request.stream_protocol, available_protocols())
        )

    job_id = uuid4()
    adapter = get_stream_adapter(
        request.stream_protocol,
        StreamAdapterContext(
            run_id=str(job_id),
            thread_id=scoped_session or str(virtual_flow_id),
        ),
    )

    # The narrower public schema has no ``data``/``tweaks`` fields; we
    # carry only the partial-run knobs into ParsedWorkflowRun.
    parsed = ParsedWorkflowRun(
        flow_id=str(virtual_flow_id),
        input_value=request.input_value,
        session_id=scoped_session,
        run_id=None,
        mode="stream",
        start_component_id=request.start_component_id,
        stop_component_id=request.stop_component_id,
        data=None,
        files=request.files,
    )

    owner_user_read = UserRead.model_validate(owner_user, from_attributes=True)

    async def _frames_only() -> AsyncIterator[bytes]:
        async for frame, _event_type in _stream_event_frames(
            adapter=adapter,
            flow_id=virtual_flow_id,
            flow_name=flow_name,
            background_tasks=background_tasks,
            parsed=parsed,
            current_user=owner_user_read,
            source_flow_id=real_flow_id,
        ):
            yield frame

    return EventSourceResponse(
        _frames_only(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
