"""Cross-worker refresh for the OSS model-provider deployment ceiling."""

from __future__ import annotations

import asyncio
import contextlib

from lfx.log.logger import logger
from lfx.services.deps import get_model_provider_policy_service
from lfx.services.model_provider_policy import ModelProviderPolicyService

from langflow.services.deps import session_scope
from langflow.services.model_provider_policy import (
    apply_model_provider_policy_state,
    get_model_provider_policy_state,
)

DEFAULT_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_SECONDS = 1.0


class ModelProviderPolicyRefreshWorker:
    """Poll the durable policy version so every backend worker converges."""

    def __init__(self, *, interval: float = DEFAULT_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_SECONDS) -> None:
        self._interval = interval
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start refreshes only for the built-in OSS policy implementation."""
        if self._task is not None:
            await logger.awarning("Model-provider policy refresh worker is already running")
            return
        if not isinstance(get_model_provider_policy_service(), ModelProviderPolicyService):
            await logger.adebug("Model-provider policy refresh worker not started: external policy service active")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="model-provider-policy-refresh")
        await logger.adebug(
            "Started model-provider policy refresh worker (interval=%ss)",
            self._interval,
        )

    async def stop(self) -> None:
        """Stop the refresh task without waiting for a full polling interval."""
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        # Startup hydration already loaded the current version.
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                await self._run_once()

    async def _run_once(self) -> bool:
        """Refresh one worker; transient database failures never stop polling."""
        try:
            async with session_scope() as session:
                state = await get_model_provider_policy_state(session)
        except Exception as exc:  # noqa: BLE001
            service = get_model_provider_policy_service()
            changed = False
            if isinstance(service, ModelProviderPolicyService):
                # Install deny-all synchronously before any logging await: a
                # broken async sink must never preserve broader stale policy.
                changed = service.fail_closed()
            with contextlib.suppress(Exception):
                await logger.aerror(f"Model-provider policy refresh failed: {exc}")
            return changed
        return apply_model_provider_policy_state(state, invalidate_external=False)


model_provider_policy_refresh_worker = ModelProviderPolicyRefreshWorker()


__all__ = [
    "DEFAULT_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_SECONDS",
    "ModelProviderPolicyRefreshWorker",
    "model_provider_policy_refresh_worker",
]
