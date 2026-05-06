"""Linux installer — runs the official Ollama install script with explicit consent.

The official Ollama install script is the documented and supported way to install
Ollama on Linux. We always invoke it via `sh -c "curl ... | sh"` with a fixed,
HTTPS, ollama.com URL — no caller-supplied data ever enters the subprocess args.
"""

from __future__ import annotations

import subprocess

from .protocol import ConsentCallback, InstallOutcome, InstallStatus

OLLAMA_LINUX_INSTALL_URL = "https://ollama.com/install.sh"

_INSTALL_TIMEOUT_S = 300  # 5 min — installer can pull ~50MB


class LinuxInstaller:
    """Linux installer using the official curl|sh script."""

    def install(self, consent_callback: ConsentCallback) -> InstallOutcome:
        if not consent_callback(OLLAMA_LINUX_INSTALL_URL):
            return InstallOutcome(status=InstallStatus.DECLINED, message="User declined")

        # Why a single fixed shell string built from a constant URL: the official
        # Ollama install instructions use `curl -fsSL <url> | sh`. The pipe is
        # required (the script reads from stdin). The string is built ONLY from a
        # module-level constant — never from caller input.
        cmd = ["sh", "-c", f"curl -fsSL {OLLAMA_LINUX_INSTALL_URL} | sh"]

        try:
            completed = subprocess.run(  # noqa: S603 — fixed cmd, no user input
                cmd,
                capture_output=True,
                text=True,
                timeout=_INSTALL_TIMEOUT_S,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return InstallOutcome(status=InstallStatus.FAILED, message=f"Install error: {exc.__class__.__name__}")

        if completed.returncode != 0:
            return InstallOutcome(
                status=InstallStatus.FAILED,
                message=f"Install script exited with code {completed.returncode}",
            )
        return InstallOutcome(status=InstallStatus.SUCCESS, message="Ollama installed via official script")
