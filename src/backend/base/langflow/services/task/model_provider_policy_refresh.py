"""Cross-worker refresh for the OSS model-provider deployment ceiling."""

from __future__ import annotations

import asyncio
import contextlib

from lfx.log.logger import logger
from lfx.services.deps import get_catalog_policy_service, get_model_provider_policy_service, get_policy_bundle_service
from lfx.services.model_provider_policy import ModelProviderPolicyService

from langflow.services.deps import get_settings_service, session_scope
from langflow.services.model_provider_policy import (
    ModelProviderPolicyNotInitializedError,
    apply_model_provider_policy_state,
    get_model_provider_policy_state,
)

DEFAULT_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_SECONDS = 10.0


class ModelProviderPolicyRefreshWorker:
    """Poll the durable policy version so every backend worker converges."""

    def __init__(self, *, interval: float | None = None) -> None:
        self._interval_override = interval
        self._active_interval = (
            interval if interval is not None else DEFAULT_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_SECONDS
        )
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start refreshes only for the built-in database-owned policy implementation."""
        if self._task is not None and not self._task.done():
            await logger.awarning("Model-provider policy refresh worker is already running")
            return
        if self._task is not None:
            # Retrieve any terminal exception before replacing the completed
            # task, avoiding an unobserved-task warning on restart.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                self._task.result()
            self._task = None
        service = get_model_provider_policy_service()
        if service.external_approved_provider_ids is not None:
            catalog_service = get_catalog_policy_service()
            if catalog_service.external_policy_snapshot is not None:
                await logger.adebug(
                    "Policy-bundle refresh worker not started: provider and catalog policies are externally managed"
                )
                return

        self._active_interval = (
            self._interval_override
            if self._interval_override is not None
            else get_settings_service().settings.model_provider_policy_refresh_interval_s
        )
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="model-provider-policy-refresh")
        await logger.adebug(
            "Started model-provider policy refresh worker (interval=%ss)",
            self._active_interval,
        )

    async def stop(self) -> None:
        """Stop the refresh task without waiting for a full polling interval."""
        task = self._task
        self._task = None
        if task is None:
            return
        self._stop_event.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    async def _run(self) -> None:
        # Startup hydration already loaded the current version.
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._active_interval)
            except asyncio.TimeoutError:
                try:
                    await self._run_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    # A malformed row, service implementation error, or other
                    # unexpected apply failure must not permanently kill the
                    # cross-worker convergence loop.
                    with contextlib.suppress(Exception):
                        await logger.aerror(f"Model-provider policy refresh iteration failed: {exc}")

    async def _run_once(self) -> bool:
        """Refresh one worker; transient database failures never stop polling."""
        deny_all_required = False
        try:
            async with session_scope() as session:
                state = await get_model_provider_policy_state(session)
            deny_all_required = bool(state.approved_provider_ids)
            return apply_model_provider_policy_state(state, invalidate_external=False)
        except Exception as exc:  # noqa: BLE001
            deny_all_required = deny_all_required or isinstance(exc, ModelProviderPolicyNotInitializedError)
            service = get_model_provider_policy_service()
            changed = False
            if isinstance(service, ModelProviderPolicyService) and service.external_approved_provider_ids is None:
                # Install deny-all synchronously before any logging await: a
                # broken async sink must never preserve broader stale policy.
                changed = service.fail_closed(deny_all_required=deny_all_required)
            elif service.external_approved_provider_ids is None:
                bundle_service = get_policy_bundle_service()
                if deny_all_required or bundle_service.snapshot.approved_provider_ids:
                    changed = bundle_service.mark_source_unavailable()
                    if changed:
                        service.invalidate()
            with contextlib.suppress(Exception):
                await logger.aerror(f"Model-provider policy refresh failed: {exc}")
            return changed


model_provider_policy_refresh_worker = ModelProviderPolicyRefreshWorker()


__all__ = [
    "DEFAULT_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_SECONDS",
    "ModelProviderPolicyRefreshWorker",
    "model_provider_policy_refresh_worker",
]
