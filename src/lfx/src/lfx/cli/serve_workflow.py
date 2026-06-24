"""The bare ``lfx serve`` host for the shared v2 workflow router.

Gives the standalone lfx runtime the same request/response contract as the
langflow backend ``POST /api/v2/workflows`` for the ``sync`` and ``stream``
execution modes, so a client integrates against one contract regardless of which
runtime serves it.

Background and public modes stay backend-only: they need a database, job queue,
and auth model that stateless ``lfx serve`` does not have. ``ServeWorkflowHost``
declares ``supports_background = False`` so the durable branch is structurally
unreachable and the router never registers job endpoints.

The env-neutral execution/SSE glue lives in :mod:`lfx.workflow.router`; this
module only supplies the serve-specific host (in-memory ``FlowRegistry`` lookup
plus api-key auth) and a thin route-registration helper.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from lfx.utils.flow_validation import validate_flow_for_current_settings
from lfx.workflow.host import ResolvedFlow, WorkflowHostBase

if TYPE_CHECKING:
    from fastapi import Request


class ServeWorkflowHost(WorkflowHostBase):
    """No-db, single-tenant host backed by the in-memory ``FlowRegistry``.

    ``supports_background = False`` makes the durable path unreachable;
    ``supports_request_overrides = False`` rejects tweaks/data/files/globals/
    partial-run boundaries with 422. ``authorize`` / ``session`` inherit the
    base no-op / yield-``None`` defaults.
    """

    supports_background = False
    supports_request_overrides = False

    def __init__(self, registry, verify_api_key) -> None:
        self._registry = registry
        self._verify_api_key = verify_api_key

    async def resolve_caller(self, request: Request) -> Any:
        """Validate the api key the same way the serve dependency does, returning the key.

        Reuses ``verify_api_key``'s ``APIKeyQuery`` / ``APIKeyHeader`` extraction
        by resolving them off the request, so the 401 behavior is identical.
        """
        from lfx.cli.serve_app import api_key_header, api_key_query

        query_param = await api_key_query(request)
        header_param = await api_key_header(request)
        return self._verify_api_key(query_param, header_param)

    async def get_flow(self, flow_id: str, caller: Any) -> ResolvedFlow:  # noqa: ARG002
        hit = self._registry.get(flow_id)
        if hit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "flow not found", "code": "FLOW_NOT_FOUND", "flow_id": flow_id},
            )
        graph, _meta = hit
        # Per-request isolation: never mutate the shared cached graph. deepcopy
        # drops graph.context, so re-stamp the registry's env policy.
        validate_flow_for_current_settings(graph)
        graph_copy = deepcopy(graph)
        self._registry.stamp(graph_copy)
        return ResolvedFlow(flow_id=flow_id, graph=graph_copy, session_id_default=flow_id)
