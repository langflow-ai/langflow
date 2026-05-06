"""End-to-end orchestrator for the bundled "Langflow Model" provider.

`ensure_local_model_ready` runs the full pipeline:

  1. Refuse if running inside a container (DockerInstaller can't help here).
  2. If Ollama is missing, install it via the platform-specific Installer.
  3. Wait for the Ollama HTTP server to come up (short retry loop).
  4. If the curated model is not pulled, pull it.

Each step has a single, documented exit status (BootstrapStatus). Callers
(CLI, REST endpoint, frontend wizard) branch on the status and never on
intermediate state.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from lfx.base.models.langflow_local_constants import LANGFLOW_LOCAL_DEFAULT_MODEL

from .installer_factory import get_installer
from .installers.protocol import ConsentCallback, InstallStatus
from .model_puller import ProgressCallback, PullStatus, is_model_pulled, pull_model
from .ollama_binary import is_ollama_installed
from .ollama_health import is_ollama_running
from .platform_detection import is_docker

DEFAULT_BASE_URL = "http://localhost:11434"

_HEALTH_RETRIES = 5
_HEALTH_BACKOFF_S = 2.0
_DOCKER_GUIDANCE = (
    "Langflow is running inside a container. Auto-install of Ollama is not "
    "supported here. Run Ollama on the host (reachable via host.docker.internal) "
    "or add an `ollama/ollama` service to your docker-compose.yml."
)
_OLLAMA_NOT_RUNNING_MSG = (
    "Ollama was installed but its HTTP server is not responding. Start it with "
    "`ollama serve` (or open the Ollama app on macOS) and try again."
)


class BootstrapStatus(str, Enum):
    READY = "ready"
    DOCKER_GUIDANCE = "docker_guidance"
    INSTALL_DECLINED = "install_declined"
    INSTALL_FAILED = "install_failed"
    OLLAMA_NOT_RUNNING = "ollama_not_running"
    PULL_FAILED = "pull_failed"
    UNSUPPORTED_OS = "unsupported_os"


@dataclass(frozen=True)
class BootstrapOutcome:
    status: BootstrapStatus
    message: str = ""


async def ensure_local_model_ready(
    consent_callback: ConsentCallback,
    progress_callback: ProgressCallback,
    base_url: str = DEFAULT_BASE_URL,
    model_name: str = LANGFLOW_LOCAL_DEFAULT_MODEL,
) -> BootstrapOutcome:
    """Run the install → start → pull pipeline and return the final outcome."""
    if is_docker():
        return BootstrapOutcome(status=BootstrapStatus.DOCKER_GUIDANCE, message=_DOCKER_GUIDANCE)

    if not is_ollama_installed():
        install_outcome = get_installer().install(consent_callback)
        bootstrap_status = _map_install_status(install_outcome.status)
        if bootstrap_status is not None:
            return BootstrapOutcome(status=bootstrap_status, message=install_outcome.message)

    if not await _wait_for_ollama_running(base_url):
        return BootstrapOutcome(status=BootstrapStatus.OLLAMA_NOT_RUNNING, message=_OLLAMA_NOT_RUNNING_MSG)

    if await is_model_pulled(model_name, base_url):
        return BootstrapOutcome(status=BootstrapStatus.READY, message=f"{model_name} already pulled")

    pull_outcome = await pull_model(model_name, base_url, progress_callback)
    if pull_outcome.status in (PullStatus.SUCCESS, PullStatus.ALREADY_PRESENT):
        return BootstrapOutcome(status=BootstrapStatus.READY, message=pull_outcome.message)
    return BootstrapOutcome(status=BootstrapStatus.PULL_FAILED, message=pull_outcome.message)


def _map_install_status(status: InstallStatus) -> BootstrapStatus | None:
    """Translate an InstallStatus into a BootstrapStatus, or None to keep going."""
    if status in (InstallStatus.SUCCESS, InstallStatus.ALREADY_INSTALLED):
        return None
    if status == InstallStatus.DECLINED:
        return BootstrapStatus.INSTALL_DECLINED
    if status == InstallStatus.UNSUPPORTED:
        return BootstrapStatus.UNSUPPORTED_OS
    return BootstrapStatus.INSTALL_FAILED


async def _wait_for_ollama_running(base_url: str) -> bool:
    """Poll the Ollama health endpoint a few times after install to let it boot."""
    for _ in range(_HEALTH_RETRIES):
        if await is_ollama_running(base_url):
            return True
        await asyncio.sleep(_HEALTH_BACKOFF_S)
    return False
