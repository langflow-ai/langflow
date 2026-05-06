"""Background task launched at FastAPI lifespan startup.

Ensures the bundled "Langflow Model" provider is ready (Ollama installed,
running, model pulled) by reusing the orchestrator from `lfx.services.local_model`.
Runs in the background — server startup is never blocked.

The orchestrator is gated by `LANGFLOW_DISABLE_LOCAL_MODEL_BOOTSTRAP=true` so
operators on managed/cloud deployments can opt out.
"""

from __future__ import annotations

import os

from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready
from loguru import logger


def _consent_yes(_url: str) -> bool:
    """Auto-consent at the server level: the operator running Langflow on their box implicitly agreed."""
    return True


# Why a stateful progress logger: pull_model emits hundreds of NDJSON chunks. We
# log the first chunk of every NEW status (e.g. "pulling manifest", "downloading
# sha256:abc...") so the operator can see real activity in the server log without
# being spammed by every byte counter.
class _StatusProgressLogger:
    def __init__(self) -> None:
        self._last_status: str | None = None

    def __call__(self, chunk: dict) -> None:
        status = chunk.get("status") if isinstance(chunk, dict) else None
        if status and status != self._last_status:
            self._last_status = status
            logger.info(f"local_model_pull_progress status={status}")


async def schedule_local_model_bootstrap() -> None:
    """Run ensure_local_model_ready in the background, swallowing all errors."""
    if os.getenv("LANGFLOW_DISABLE_LOCAL_MODEL_BOOTSTRAP", "").lower() in {"1", "true", "yes"}:
        logger.info("local_model_bootstrap_skipped reason=env_flag")
        return
    logger.info("local_model_bootstrap_starting")
    progress_logger = _StatusProgressLogger()
    try:
        outcome = await ensure_local_model_ready(_consent_yes, progress_logger)
    except Exception as exc:  # noqa: BLE001 — startup hook must NEVER crash the server
        logger.warning(f"local_model_bootstrap_failed error={exc.__class__.__name__} message={exc}")
        return
    if outcome.status == BootstrapStatus.READY:
        logger.info("local_model_bootstrap_ready")
    else:
        logger.info(f"local_model_bootstrap_finished status={outcome.status.value} message={outcome.message}")
