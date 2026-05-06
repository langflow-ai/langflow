"""REST endpoints for the bundled local-model bootstrap pipeline.

  - GET  /local_model/status — non-mutating snapshot of detection state.
  - POST /local_model/setup  — kicks off ensure_local_model_ready in the background.

Heavy lifting lives in lfx.services.local_model; this router only adapts the
async pipeline to HTTP and enforces auth + explicit consent.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_DEFAULT_MODEL
from lfx.services.local_model.bootstrap import DEFAULT_BASE_URL, ensure_local_model_ready
from lfx.services.local_model.model_puller import is_model_pulled
from lfx.services.local_model.ollama_binary import is_ollama_installed
from lfx.services.local_model.ollama_health import is_ollama_running
from lfx.services.local_model.platform_detection import is_docker
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser

router = APIRouter(prefix="/local_model", tags=["Local Model"])


class LocalModelStatus(BaseModel):
    is_docker: bool
    is_ollama_installed: bool
    is_ollama_running: bool
    is_model_pulled: bool
    default_model: str
    ready: bool


class SetupRequest(BaseModel):
    consent: bool


class SetupAccepted(BaseModel):
    accepted: bool


def _always_consent(_url: str) -> bool:
    """Consent shim for the background path — the user already consented at the HTTP layer."""
    return True


def _noop_progress(_chunk: dict) -> None:
    """Progress shim for the background path — frontend polls /status for now."""


async def _run_bootstrap_in_background() -> None:
    await ensure_local_model_ready(
        consent_callback=_always_consent,
        progress_callback=_noop_progress,
        base_url=DEFAULT_BASE_URL,
        model_name=LANGFLOW_LOCAL_DEFAULT_MODEL,
    )


@router.get("/status", response_model=LocalModelStatus, status_code=200)
async def get_local_model_status(current_user: CurrentActiveUser) -> LocalModelStatus:  # noqa: ARG001
    """Return a snapshot of the current local-model bootstrap state."""
    in_docker = is_docker()
    installed = is_ollama_installed()
    running = await is_ollama_running(DEFAULT_BASE_URL) if installed else False
    pulled = await is_model_pulled(LANGFLOW_LOCAL_DEFAULT_MODEL, DEFAULT_BASE_URL) if running else False

    return LocalModelStatus(
        is_docker=in_docker,
        is_ollama_installed=installed,
        is_ollama_running=running,
        is_model_pulled=pulled,
        default_model=LANGFLOW_LOCAL_DEFAULT_MODEL,
        ready=installed and running and pulled and not in_docker,
    )


@router.post("/setup", response_model=SetupAccepted, status_code=202)
async def setup_local_model(
    body: SetupRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentActiveUser,  # noqa: ARG001
) -> SetupAccepted:
    """Kick off the local-model bootstrap pipeline in a background task."""
    if not body.consent:
        raise HTTPException(status_code=400, detail="Explicit consent required")
    background_tasks.add_task(_run_bootstrap_in_background)
    return SetupAccepted(accepted=True)
