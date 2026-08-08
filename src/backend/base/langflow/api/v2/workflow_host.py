"""Langflow's DB/tenant-bound host for the shared v2 workflow router.

``lfx.workflow.router.create_workflow_router`` owns the env-neutral POST run
path; this host supplies the langflow-specific capabilities the router cannot
have in bare ``lfx serve``:

    - ``resolve_caller``: session-cookie / API-key auth, inside its OWN
      short-lived session (never the router's read-only request session) so the
      inline graph run does not contend with the auth connection on SQLite.
    - ``get_flow``: share-aware fetch + the langflow error-to-HTTP mapping
      (404 FLOW_NOT_FOUND, 503 DATABASE_ERROR, 500 sanitized).
    - ``authorize``: ``WorkflowAction`` -> ``FlowAction`` via
      ``ensure_flow_permission`` with the deny -> 404-privacy reframe.
    - ``run_sync`` / ``stream_response`` / ``submit_background``: the langflow
      sync (job-tracked, timeout-protected), live-stream (v1 build-vertex loop
      with agui side-channel + vertex-build persistence), and durable background
      paths.

The langflow router supplies ``supports_background=True`` (so POST
``mode="background"`` dispatches here) and ``supports_request_overrides=True``
(so the lfx no-overrides 422 stays off; langflow accepts tweaks/data/files/
globals/partial-run). It mounts with ``auto_register_job_routes=False`` and
provides its own GET status / POST stop / GET events handlers.

The orchestration body itself lives in :mod:`langflow.api.v2.workflow`; this
host references those module-level functions so the existing route tests (which
patch ``langflow.api.v2.workflow.*``) keep working unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.workflow.actions import WorkflowAction
from lfx.workflow.host import ResolvedFlow, WorkflowHostBase

if TYPE_CHECKING:
    from fastapi import BackgroundTasks, Request
    from lfx.schema.workflow import WorkflowExecutionResponse, WorkflowJobResponse
    from lfx.workflow.converters import ParsedWorkflowRun
    from starlette.responses import Response


class LangflowWorkflowHost(WorkflowHostBase):
    """DB-backed host: background runs and per-request overrides are supported."""

    supports_background = True
    supports_request_overrides = True

    async def resolve_caller(self, request: Request) -> Any:
        """Authenticate the caller in a short-lived session and return a ``UserRead``.

        Extracts the session token / api-key off the raw request and delegates
        to ``get_current_user_for_workflow``, which opens (and closes) its own
        ``session_scope``. Keeping that session separate from the router's
        read-only request session is required to avoid SQLite lock contention
        during the inline graph run.
        """
        from langflow.services.auth.utils import (
            api_key_header,
            api_key_query,
            get_current_user_for_workflow,
            oauth2_login,
        )

        token = await oauth2_login(request)
        query_param = await api_key_query(request)
        header_param = await api_key_header(request)
        return await get_current_user_for_workflow(token, query_param, header_param)

    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow:
        """Share-aware fetch + langflow error mapping; carries the ``FlowRead``.

        ``ResolvedFlow.graph`` holds the langflow ``FlowRead`` (not a pre-built
        ``Graph``): the sync, stream, and background paths each build their own
        graph from ``flow.data`` at run time (sync rebuilds with tweaks; stream/
        background build inside the v1 build-vertex loop), so no single prebuilt
        graph fits all three.
        """
        from langflow.api.v2.workflow import resolve_flow_for_execution

        flow = await resolve_flow_for_execution(flow_id, caller)
        return ResolvedFlow(flow_id=str(flow_id), graph=flow, session_id_default=str(flow.id))

    async def authorize(self, caller: Any, flow: ResolvedFlow, action: WorkflowAction) -> None:
        """Map the workflow action to a flow action and enforce it (deny -> 404)."""
        from langflow.api.v2.workflow import authorize_flow_action

        await authorize_flow_action(caller, flow.graph, action, requested_id=flow.flow_id)

    async def run_sync(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        http_request: Request,
        background_tasks: BackgroundTasks,
    ) -> WorkflowExecutionResponse:
        from langflow.api.v2.workflow import run_sync_with_mapping

        return await run_sync_with_mapping(
            parsed, flow.graph, caller, http_request=http_request, background_tasks=background_tasks
        )

    def stream_response(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
        http_request: Request,  # noqa: ARG002
        background_tasks: BackgroundTasks,
    ) -> Response:
        from langflow.api.v2.workflow import build_stream_response

        return build_stream_response(
            parsed,
            flow.graph,
            caller,
            stream_protocol=stream_protocol,
            background_tasks=background_tasks,
        )

    async def submit_background(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
    ) -> WorkflowJobResponse:
        from langflow.api.v2.workflow import submit_background_with_mapping

        return await submit_background_with_mapping(parsed, flow.graph, caller, stream_protocol=stream_protocol)
