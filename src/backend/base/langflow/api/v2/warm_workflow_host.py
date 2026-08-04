"""PROD execution-plane host: serve deployed flows from the warm registry.

This host is the ``--backend-only`` PROD counterpart to ``LangflowWorkflowHost``.
It is structurally closer to ``lfx``'s ``ServeWorkflowHost`` (a warm registry +
deepcopy per request, using the base lfx run primitives) than to the DB-heavy
langflow host — but it keeps langflow authentication so requests still resolve to
a real ``User`` for attribution and request-scoped globals.

Key differences from ``LangflowWorkflowHost``:
- ``get_flow`` resolves a pre-parsed ``Graph`` from the warm registry (deepcopy per
  request) instead of fetching the row and rebuilding with ``from_payload``. A flow
  that is not currently deployed/active -> 404 (the "flow was pulled" guard).
- ``authorize`` inherits the base **no-op**: per-flow RBAC (``ensure_flow_permission``)
  is intentionally skipped under the single-tenant trust model — any authenticated
  caller may run any deployed flow. (Do NOT use this host for a multi-tenant
  execution plane, or where per-user flow access differs.)
- ``run_sync`` / ``stream_response`` inherit the base lfx primitives (no job row or
  ``vertex_build`` writes), keeping the throughput plane lean.
- ``supports_background = False``: background/HITL stay on the DB-backed control plane.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

# Subclass WorkflowHostBase (lfx base), NOT LangflowWorkflowHost: the base
# run_sync/stream_response use the lean lfx primitives (no job row, no vertex_build
# writes), which is exactly what the throughput plane needs.
from lfx.workflow.host import ResolvedFlow, WorkflowHostBase

if TYPE_CHECKING:
    from fastapi import BackgroundTasks, Request
    from lfx.schema.workflow import ParsedWorkflowRun, WorkflowExecutionResponse


class WarmWorkflowHost(WorkflowHostBase):
    """Warm-registry-backed host for the PROD execution plane."""

    # Two capability flags the shared router reads. Background=False -> the durable/HITL
    # branch never dispatches here. request_overrides=False -> reject structural
    # tweaks/data/files (422), like lfx serve; the shared template can't be safely
    # re-parsed per request. (Request-level ``globals`` still apply — to the deepcopy's
    # context, not its structure.)
    supports_background = False
    supports_request_overrides = False

    async def resolve_caller(self, request: Request) -> Any:
        """Authenticate the caller (session cookie / API key) -> ``UserRead``.

        Authentication is kept: anonymous requests are rejected, and the resolved
        identity is threaded into the run for attribution and per-user globals.
        Only *authorization* (per-flow RBAC) is skipped on this host.
        """
        # Lazy import to keep module-load cost/cycles down. This is the same auth the DB
        # host uses — authentication is kept; only per-flow authorization is dropped.
        from langflow.services.auth.utils import (
            api_key_header,
            api_key_query,
            get_current_user_for_workflow,
            oauth2_login,
        )

        # A caller may present credentials three ways: an OAuth2 bearer/session token, an
        # api key in the query string, or an api key in a header.
        token = await oauth2_login(request)
        query_param = await api_key_query(request)
        header_param = await api_key_header(request)
        # Resolve to a real User (in its own short-lived DB session); 401 if none valid.
        return await get_current_user_for_workflow(token, query_param, header_param)

    def _run_user_id(self, caller: Any) -> str | None:
        """Thread the authenticated user id into the run (globals / tracing)."""
        # getattr(..., "id", None) is defensive: if ``caller`` isn't a user object
        # (e.g. auth off), return None instead of crashing.
        uid = getattr(caller, "id", None)
        return str(uid) if uid is not None else None

    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow:  # noqa: ARG002
        """Resolve a run-ready ``Graph`` from the warm registry (deepcopy per request).

        Lazily warms from the DB on a cache miss; a flow still absent (never deployed
        or already retired) -> 404. The deepcopy guarantees per-request isolation so
        the shared template is never mutated (``run_workflow_sync`` stamps user_id /
        globals onto the copy).
        """
        # ``caller`` is unused (ARG002 noqa): no per-user authorization — any
        # authenticated caller may run any deployed flow.
        from lfx.utils.flow_validation import validate_flow_for_current_settings

        from langflow.services.warm_registry.reconcile import warm_one
        from langflow.services.warm_registry.service import get_warm_registry

        # Fast path: in-memory registry hit; on a miss, warm_one() lazily loads that one
        # flow from the DB and caches it.
        hit = get_warm_registry().get(flow_id) or await warm_one(flow_id)
        # Still nothing -> not deployed (or retired/pulled). This is the "active-flow
        # guard": a flow removed from the DB can't be run even if still resident.
        if hit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "flow not found", "code": "FLOW_NOT_FOUND", "flow_id": flow_id},
            )
        template, _version = hit
        # Cheap pre-run check that the flow's components are valid under current server
        # settings (the same call lfx serve makes).
        validate_flow_for_current_settings(template)
        # The isolation step: deepcopy gives this request its own private graph so
        # run_workflow_sync can stamp user_id/globals without touching the shared
        # template other requests reuse.
        graph_copy = deepcopy(template)
        # Return a run-ready Graph (not a FlowRead) as ResolvedFlow, so the base
        # run_sync/stream can execute it directly — no from_payload rebuild on this path.
        return ResolvedFlow(flow_id=flow_id, graph=graph_copy, session_id_default=flow_id)

    async def run_sync(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        http_request: Request,
        background_tasks: BackgroundTasks,
    ) -> WorkflowExecutionResponse:
        """Run the graph with the langflow wall-clock ceiling enforced (408 on timeout).

        The lean base ``run_sync`` has no timeout, so a runaway flow on the execution
        plane would run unbounded and hold a worker forever. Wrap it in the configured
        ``workflow_execution_timeout`` and surface the same 408 contract the DB host
        uses. (Only per-flow RBAC + job/vertex-build writes stay dropped; the durable
        job-tracking and header-global/session mapping remain a separate adapter.)
        """
        from langflow.services.deps import get_settings_service

        timeout_seconds = get_settings_service().settings.workflow_execution_timeout
        try:
            return await asyncio.wait_for(
                super().run_sync(parsed, flow, caller, http_request=http_request, background_tasks=background_tasks),
                timeout=timeout_seconds,
            )
        except (TimeoutError, asyncio.TimeoutError):
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail={
                    "error": "Execution timeout",
                    "code": "EXECUTION_TIMEOUT",
                    "message": f"Workflow execution exceeded {timeout_seconds} seconds",
                    "flow_id": flow.flow_id,
                    "timeout_seconds": timeout_seconds,
                },
            ) from None
