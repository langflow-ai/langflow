"""The per-worker warm graph registry.

A process-local cache of pre-parsed flow graphs. Each entry is a built ``Graph``
template keyed by flow id, paired with a ``version`` string (the flow's
``updated_at`` isoformat) used by the reconcile loop to detect changes.

``get`` returns the shared template; callers deepcopy before running so the
template is never mutated (mirrors the ``lfx serve`` ``FlowRegistry`` pattern).
Building a template is expensive (``Graph.from_payload`` instantiates every
component), so it happens once at warm/reconcile time, not per request.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph


class FlowStoreUnavailableError(Exception):
    """The flow store could not be reached while (lazily) warming a flow.

    Distinguishes a transient availability failure (DB down / pool exhausted) from a
    genuine not-found, so the API layer can answer 503 (retryable) instead of 404
    (permanent). Raised by ``warm_one``; translated to an HTTP 503 by the host.
    """


class WarmGraphRegistry:
    """In-memory ``flow_id -> (Graph template, version)`` cache for one worker."""

    def __init__(self) -> None:
        # flow UUID (str) -> (built Graph template, version marker). One dict per
        # worker process; nothing is shared across processes/machines — the
        # reconcile loop against the shared DB is what keeps them converged.
        self._flows: dict[str, tuple[Graph, str]] = {}
        # Guards writers (add/evict) so concurrent reconcile/warm calls can't leave a
        # half-written dict. Reads (``get``) are plain dict lookups (atomic in CPython)
        # and take no lock, keeping the hot request path fast.
        self._lock = asyncio.Lock()

    @staticmethod
    def _build(flow_id: str, name: str | None, data: dict) -> Graph:
        """Parse ``flow.data`` into a run-ready ``Graph`` template.

        ``data`` is deepcopied first because ``from_payload`` rewrites the payload
        in place (legacy component migration), and the caller's dict may be the DB
        row's own mapping. ``user_id`` is intentionally not stamped here — the
        template is user-agnostic and shared; per-request user_id is applied later
        by ``run_workflow_sync``'s ``apply_run_defaults`` on the deepcopy.
        """
        from lfx.graph.graph.base import Graph

        return Graph.from_payload(deepcopy(data), flow_id=flow_id, flow_name=name)

    async def add(self, flow_id: str, name: str | None, data: dict, version: str) -> None:
        """Build ``data`` into a template and store it under ``flow_id`` at ``version``.

        The (expensive) build runs outside the lock; only the dict swap is guarded,
        so concurrent adds for other flows are not blocked by one slow build.
        ``Graph.from_payload`` is synchronous and CPU-heavy, so it runs in a worker
        thread — this yields the event loop during the build, keeping request handling
        and health checks responsive on a reconcile pass or a cache-miss warm.
        """
        graph = await asyncio.to_thread(self._build, flow_id, name, data)
        async with self._lock:
            self._flows[flow_id] = (graph, version)

    def get(self, flow_id: str) -> tuple[Graph, str] | None:
        """Return the shared ``(template, version)`` for ``flow_id`` or ``None``.

        The template is NOT copied here — the caller deepcopies before running.
        """
        return self._flows.get(flow_id)

    def version_of(self, flow_id: str) -> str | None:
        """Return just the cached version for ``flow_id`` (or ``None``) without the graph."""
        hit = self._flows.get(flow_id)
        return hit[1] if hit is not None else None

    async def evict(self, flow_id: str) -> None:
        """Drop ``flow_id`` from the cache (no-op if already gone)."""
        async with self._lock:
            self._flows.pop(flow_id, None)

    def active_ids(self) -> set[str]:
        """Snapshot of the currently cached flow ids (reconcile diffs this vs the DB manifest)."""
        return set(self._flows)

    def __len__(self) -> int:
        return len(self._flows)


_warm_registry: WarmGraphRegistry | None = None


def get_warm_registry() -> WarmGraphRegistry:
    """Return the process-local warm registry singleton, creating it on first use."""
    global _warm_registry  # noqa: PLW0603
    if _warm_registry is None:
        _warm_registry = WarmGraphRegistry()
        logger.debug("warm_registry: initialized process-local registry")
    return _warm_registry
