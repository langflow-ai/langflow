"""V2 public workflow endpoint.

Counterpart of ``/api/v1/build_public_tmp/{flow_id}/flow`` for the v2
streaming pipeline. The shareable playground POSTs here so visitors can
run a public flow without owning it.

The body is intentionally narrower than ``/api/v2/workflows`` (no
``data``, no ``tweaks``): visitors must never override the stored flow
definition. The handler also enforces the public-access mitigations:

- A canonical PUBLIC share or compatibility grant (others 404, checked before any policy
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
- Anonymous principal isolation: the run never inherits the flow owner's
  variables, credentials, files, or knowledge bases.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import EventSourceResponse
from lfx.log.logger import logger
from lfx.schema.workflow import (
    WORKFLOW_EXECUTION_RESPONSES,
    PublicWorkflowRunRequest,
)
from lfx.utils.flow_validation import (
    PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE,
    CatalogPolicyIdentityUnavailableError,
    CustomComponentValidationError,
    prepare_public_flow_build,
    validate_catalog_policy_for_flow,
    validate_public_flow_no_code_execution,
)
from lfx.workflow.adapters import (
    STREAM_ADAPTERS,
    StreamAdapterContext,
    UnknownStreamProtocolError,
    available_protocols,
    get_stream_adapter,
)
from lfx.workflow.converters import ParsedWorkflowRun
from limits import parse

from langflow.api.utils.core import strip_secret_field_values
from langflow.api.utils.flow_utils import (
    scope_session_to_namespace,
    validate_public_files,
    verify_public_flow_and_get_user,
)
from langflow.services.auth.utils import get_current_user_optional
from langflow.services.authorization.public_access import (
    PUBLIC_FLOW_NOT_FOUND_DETAIL,
    PublicResourceAction,
    authorize_public_flow_access,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope

router = APIRouter(prefix="/workflows/public", tags=["Workflow (public)"], include_in_schema=False)


def _enforce_public_rate_limit(http_request: Request) -> None:
    """Throttle anonymous public-flow runs per client IP.

    Each run consumes real CPU/DB/provider capacity, so an
    unauthenticated caller must not be able to spin up unbounded concurrent
    executions. Mirrors the manual limiter check the login endpoint uses, but
    keyed to its own configurable per-minute limit under a dedicated namespace so
    it never shares a bucket with login. No-op when rate limiting is disabled.
    """
    settings = get_settings_service().settings
    if not settings.rate_limit_enabled:
        return
    limiter = http_request.app.state.limiter
    limit_item = parse(f"{settings.public_flow_rate_limit_per_minute}/minute")
    # hit() returns False once the window is exhausted for this (namespace, ip) key.
    if not limiter._limiter.hit(limit_item, "public-workflow", limiter._key_func(http_request)):  # noqa: SLF001
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Too many requests",
                "code": "RATE_LIMITED",
                "message": "Too many public workflow runs from this client. Please retry shortly.",
            },
        )


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
    from langflow.api.v2.workflow import _unknown_protocol_http_exception
    from langflow.api.v2.workflow_execution import _stream_event_frames

    # Throttle before any DB lookup or flow execution so an anonymous flood is
    # rejected cheaply, not after spending the flow owner's resources.
    _enforce_public_rate_limit(http_request)

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
        settings_service = get_settings_service()
        settings = settings_service.settings
        auth_settings = settings_service.auth_settings
        authenticated_user_id = authenticated_user.id if authenticated_user and not auth_settings.AUTO_LOGIN else None

        # Direct-link grant + virtual flow id + stable anonymous runtime principal.
        public_user, virtual_flow_id = await verify_public_flow_and_get_user(
            flow_id=real_flow_id,
            client_id=client_id,
            authenticated_user_id=authenticated_user_id,
            request_host=http_request.url.hostname,
        )

        # Defends CVE-2026-33017: scope caller's session into the (identifier, flow_id) namespace.
        scoped_session = (
            scope_session_to_namespace(request.session_id, str(virtual_flow_id))
            if request.session_id is not None
            else None
        )

        # Validate stored flow data after the public-access gate so private
        # flows never trigger validation side effects.
        sanitized_public_data: dict | None = None
        async with session_scope() as session:
            flow = await session.get(Flow, real_flow_id)
            if flow is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=PUBLIC_FLOW_NOT_FOUND_DETAIL)
            # Authorize the same snapshot that is validated, scrubbed, detached,
            # and streamed below; the admission helper used a separate session and
            # its earlier snapshot may have been revoked in the meantime.
            await authorize_public_flow_access(
                flow=flow,
                action=PublicResourceAction.EXECUTE,
                request_host=http_request.url.hostname,
                session=session,
            )
            if flow.data is None:
                msg = "Public flow has no executable data"
                raise ValueError(msg)

            # The default public path sanitizes code directly and must not apply the global
            # stored-code hash gate first: that would reject drifted built-ins before their code
            # can be replaced. Enforce catalog policy explicitly, matching v1. The public custom-
            # code opt-in delegates to the unified validator inside prepare_public_flow_build.
            if not settings.allow_public_custom_components:
                validate_catalog_policy_for_flow(flow.data)
            # Block unauthenticated execution of flows that run arbitrary code
            # (Python interpreter/REPL, legacy Python Code Structured tool,
            # Smart Transform lambda). Without this, any public flow containing
            # such a component is an unauthenticated code-execution primitive.
            validate_public_flow_no_code_execution(flow.data)
            # Mirror v1's public build: substitute trusted server component
            # source and reject unknown custom components before the graph is
            # built. The explicit custom-code opt-in may preserve approved code,
            # but the detached graph is always secret-scrubbed below.
            prepared_public_data = await prepare_public_flow_build(flow.data)
            sanitized_public_data = strip_secret_field_values(
                prepared_public_data if prepared_public_data is not None else flow.data
            )
            flow_name = flow.name
            source_flow_owner_id = flow.user_id
    except CatalogPolicyIdentityUnavailableError as exc:
        await logger.awarning("Public workflow component identities are temporarily unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE,
        ) from exc
    except CustomComponentValidationError as exc:
        # The raw message embeds the blocked component class names; do
        # not leak it to an anonymous visitor.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This flow cannot be executed.") from exc
    except ValueError as exc:
        await logger.awarning("Public workflow validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This flow cannot be executed.") from exc

    if request.stream_protocol not in STREAM_ADAPTERS:
        raise _unknown_protocol_http_exception(
            UnknownStreamProtocolError(request.stream_protocol, available_protocols())
        )

    run_id = str(uuid4())
    adapter = get_stream_adapter(
        request.stream_protocol,
        StreamAdapterContext(
            run_id=run_id,
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
        # Always build from a detached secret-scrubbed graph. The default policy
        # additionally substitutes trusted server code; the explicit custom-code
        # opt-in preserves approved code without restoring owner credentials.
        data=sanitized_public_data,
        files=request.files,
    )

    async def _frames_only() -> AsyncIterator[bytes]:
        async for frame, _event_type in _stream_event_frames(
            adapter=adapter,
            flow_id=virtual_flow_id,
            flow_name=flow_name,
            background_tasks=background_tasks,
            parsed=parsed,
            current_user=public_user,
            provider_policy_flow=flow,
            source_flow_id=real_flow_id,
            source_flow_owner_id=source_flow_owner_id,
            run_id=run_id,
            # Anonymous shared-link traffic, kept apart from signed-in v2 runs the same way
            # playground.public is kept apart from playground.
            protocol="v2.public",
            expose_error_details=False,
        ):
            yield frame

    return EventSourceResponse(
        _frames_only(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
