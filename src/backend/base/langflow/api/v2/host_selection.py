"""Deferred selection of the v2 workflow host (warm PROD registry vs DB-backed).

Which host serves ``POST /api/v2/workflows`` depends on the deployment profile
(``LANGFLOW_DEPLOYMENT_PROFILE=prod`` -> ``settings.deployment_profile``, the same
umbrella flag whose prod value the deployment-profile preflight fail-fast-validates:
enabling the warm/authz-lean host is gated behind that validated profile, not a
standalone switch). The problem: ``langflow.__main__`` imports the router module
(and therefore builds this router) *before* it runs ``load_dotenv(--env-file)``, so
reading the env — or the settings service — at import time would miss any value
supplied via ``--env-file``. That is exactly the ordering trap the extensions router
documents for ``LANGFLOW_ENABLE_EXTENSION_RELOAD``.

``DeferredWorkflowHost`` defers the choice to first use. By the time any workflow
route (or capability flag) is exercised, ``setup_app``/lifespan has initialized the
settings service from the fully-loaded environment, so the profile is correct. The
route *structure* is identical for both hosts (the shared router only reads
``supports_*`` at request time, and ``auto_register_job_routes=False`` neutralizes
the one mount-time read), so binding this single proxy at import changes nothing
structurally — only which concrete host each request lands on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.workflow.host import WorkflowHostBase

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import BackgroundTasks, Request, Response
    from lfx.schema.workflow import (
        ParsedWorkflowRun,
        WorkflowExecutionResponse,
        WorkflowJobResponse,
        WorkflowStopResponse,
    )
    from lfx.workflow.host import ResolvedFlow, WorkflowAction


def is_prod_deployment(settings: Any) -> bool:
    """True when the production deployment profile is active.

    Consumes ``settings.deployment_profile`` (env ``LANGFLOW_DEPLOYMENT_PROFILE``) —
    the umbrella flag owned by the deployment-profile preflight feature. Read
    defensively via ``getattr`` so this code is safe on branches where that setting
    does not exist yet: absent -> ``"dev"`` -> production behavior stays off. The
    warm registry + authz-lean host therefore activate only under the same ``prod``
    profile the preflight gate validates.
    """
    return getattr(settings, "deployment_profile", "dev") == "prod"


class DeferredWorkflowHost(WorkflowHostBase):
    """A ``WorkflowHost`` that picks the concrete host lazily from the deployment profile.

    Every member delegates to the resolved host. Resolution is cached only once the
    settings service is initialized, so an access during module import (before
    ``--env-file`` is loaded) never force-initializes settings nor caches a stale
    choice — it falls back transiently and re-resolves on the next call.
    """

    def __init__(self) -> None:
        self._host: WorkflowHostBase | None = None

    def _resolve(self) -> WorkflowHostBase:
        if self._host is not None:
            return self._host
        from langflow.api.v2.warm_workflow_host import WarmWorkflowHost
        from langflow.api.v2.workflow_host import LangflowWorkflowHost
        from langflow.services.deps import get_settings_service, is_settings_service_initialized

        # Do NOT force-initialize settings from a half-loaded environment at import
        # time (the router is built before ``load_dotenv(--env-file)``). Until the
        # settings service exists, fall back to the DB host WITHOUT caching so the
        # real choice is still made on the first post-startup call.
        if not is_settings_service_initialized():
            return LangflowWorkflowHost()
        host: WorkflowHostBase = (
            WarmWorkflowHost() if is_prod_deployment(get_settings_service().settings) else LangflowWorkflowHost()
        )
        self._host = host
        return host

    @property
    def supports_background(self) -> bool:
        return self._resolve().supports_background

    @property
    def supports_request_overrides(self) -> bool:
        return self._resolve().supports_request_overrides

    async def resolve_caller(self, request: Request) -> Any:
        return await self._resolve().resolve_caller(request)

    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow:
        return await self._resolve().get_flow(flow_id, caller)

    async def authorize(self, caller: Any, flow: ResolvedFlow, action: WorkflowAction) -> None:
        return await self._resolve().authorize(caller, flow, action)

    def session(self) -> AsyncIterator[Any | None]:
        # Returns the concrete host's async context manager (used as ``async with``).
        return self._resolve().session()

    async def run_sync(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        http_request: Request,
        background_tasks: BackgroundTasks,
    ) -> WorkflowExecutionResponse:
        return await self._resolve().run_sync(
            parsed, flow, caller, http_request=http_request, background_tasks=background_tasks
        )

    def stream_response(
        self,
        parsed: ParsedWorkflowRun,
        flow: ResolvedFlow,
        caller: Any,
        *,
        stream_protocol: str,
        http_request: Request,
        background_tasks: BackgroundTasks,
    ) -> Response:
        return self._resolve().stream_response(
            parsed,
            flow,
            caller,
            stream_protocol=stream_protocol,
            http_request=http_request,
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
        return await self._resolve().submit_background(parsed, flow, caller, stream_protocol=stream_protocol)

    async def get_job_status(
        self, job_id: str, caller: Any, session: Any
    ) -> WorkflowExecutionResponse | WorkflowJobResponse:
        return await self._resolve().get_job_status(job_id, caller, session)

    async def stop_job(self, job_id: str, caller: Any) -> WorkflowStopResponse:
        return await self._resolve().stop_job(job_id, caller)
