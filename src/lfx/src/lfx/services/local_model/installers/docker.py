"""Docker "installer" — refuses to install inside a container.

Auto-installing system packages inside an arbitrary container is unsafe (no
guaranteed privileges, no GPU passthrough, no systemd) and bad UX (the user
likely wants Ollama on the host, not in this container). We refuse explicitly
and emit guidance on how to wire Ollama up via docker-compose or host.docker.internal.
"""

from __future__ import annotations

from .protocol import ConsentCallback, InstallOutcome, InstallStatus

_DOCKER_GUIDANCE = (
    "Detected Langflow running inside a container. Auto-install of Ollama is not "
    "supported in Docker. Run Ollama on the host (reachable via host.docker.internal) "
    "or add an `ollama/ollama` service to your docker-compose.yml."
)


class DockerInstaller:
    """Refuses to install; emits guidance for the docker-compose / host setup."""

    def install(self, consent_callback: ConsentCallback) -> InstallOutcome:  # noqa: ARG002
        return InstallOutcome(status=InstallStatus.UNSUPPORTED, message=_DOCKER_GUIDANCE)
