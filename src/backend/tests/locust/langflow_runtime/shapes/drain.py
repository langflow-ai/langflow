"""Drain-phase helpers for the performance suite."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
from tests.locust.langflow_runtime.metrics.registry import get_registry
from tests.locust.langflow_runtime.metrics.reports import set_report_context

logger = logging.getLogger(__name__)


def drain_remaining_s(elapsed_s: float, total_budget_s: float) -> float:
    """Seconds remaining before the drain deadline."""
    return max(0.0, total_budget_s - elapsed_s)


def stop_new_arrivals(environment: Any, *, enabled: bool = True) -> None:
    """Signal generators to stop submitting new work."""
    environment.stop_new_arrivals = enabled


def drain_tracked_work(environment: Any, deadline_s: float) -> dict[str, Any]:
    """Poll outstanding workflows until terminal or deadline; reconcile webhooks/HITL.

    Does not tear down the provisioned environment.
    """
    registry = get_registry()
    started = time.monotonic()
    poll_interval_s = 0.5
    run_context = getattr(environment, "run_context", None)
    if run_context is not None:
        poll_interval_s = float(run_context.profile.windows.poll_interval_s)

    client = _workflows_client_from_environment(environment)
    while True:
        remaining = deadline_s - (time.monotonic() - started)
        if remaining <= 0:
            break
        outstanding = registry.outstanding_workflows()
        outstanding_webhooks = registry.outstanding_webhooks()
        in_flight_webhooks = [row for row in outstanding_webhooks if row.in_flight > 0]
        if not outstanding and not in_flight_webhooks:
            break
        if client is not None:
            for job in outstanding:
                try:
                    status = client.get_status(job.job_id)
                except Exception as exc:
                    logger.debug("drain status poll failed for %s: %s", job.job_id, exc)
                    continue
                if status.terminal:
                    registry.update_workflow(
                        job.job_id,
                        status=status.status,
                        success=status.success,
                        terminal_at=datetime.now(UTC),
                    )
        # Keep waiting while Locust observers finish in-flight webhook SSE.
        time.sleep(min(poll_interval_s, max(0.05, remaining)))

    outstanding_webhooks = registry.outstanding_webhooks()
    residual_hitl = registry.residual_hitl()
    snapshot = registry.drain_snapshot()
    report = {
        "drain_time_s": round(time.monotonic() - started, 3),
        "deadline_s": deadline_s,
        "outstanding_workflows": snapshot["outstanding_workflows"],
        "outstanding_webhooks": snapshot["outstanding_webhooks"],
        "residual_hitl": snapshot["residual_hitl"],
        "outstanding_workflow_count": len(snapshot["outstanding_workflows"]),
        "outstanding_webhook_count": len(outstanding_webhooks),
        "residual_hitl_count": len(residual_hitl),
    }
    set_report_context(drain=report)
    environment.perf_drain_report = report
    if residual_hitl:
        logger.warning("drain residual HITL requests: %s", [row.request_id for row in residual_hitl])
    return report


def reset_movement_state(environment: Any) -> None:
    """Clear registries and release webhook leases; do not teardown provisioned env."""
    registry = get_registry()
    registry.clear_all()
    pool = getattr(environment, "webhook_pool", None)
    if pool is not None and hasattr(pool, "release_all"):
        pool.release_all()
    environment.stop_new_arrivals = False
    environment.perf_drain_started = False


def _workflows_client_from_environment(environment: Any) -> WorkflowsClient | None:
    run_context = getattr(environment, "run_context", None)
    state = getattr(run_context, "provision_state", None) if run_context else None
    if not isinstance(state, dict):
        return None
    api_key = state.get("api_key")
    host = getattr(run_context, "host", None) or getattr(environment, "host", None)
    if not api_key or not host:
        return None
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return None
    http = httpx.Client(base_url=str(host).rstrip("/"), timeout=30.0)
    # Keep client alive for the drain loop via environment attribute.
    environment._perf_drain_http = http
    return WorkflowsClient(http, base_url=str(host).rstrip("/"), api_key=str(api_key))
