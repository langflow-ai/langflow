"""Windows installer — downloads OllamaSetup.exe and runs it with UAC prompt.

Windows has no documented silent-install flag for OllamaSetup.exe outside of
enterprise distribution channels. We download to a temp directory and execute
the installer; the OS will surface a UAC prompt that the user must accept. If
they decline UAC, the subprocess returns non-zero and we report FAILED.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import httpx

from .protocol import ConsentCallback, InstallOutcome, InstallStatus

OLLAMA_WINDOWS_SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"

_DOWNLOAD_TIMEOUT_S = 300
_RUN_TIMEOUT_S = 600


class WindowsInstaller:
    """Windows installer that downloads OllamaSetup.exe and runs it."""

    def install(self, consent_callback: ConsentCallback) -> InstallOutcome:
        if not consent_callback(OLLAMA_WINDOWS_SETUP_URL):
            return InstallOutcome(status=InstallStatus.DECLINED, message="User declined")

        with tempfile.TemporaryDirectory() as tmp:
            installer_path = Path(tmp) / "OllamaSetup.exe"
            try:
                with httpx.stream("GET", OLLAMA_WINDOWS_SETUP_URL, timeout=_DOWNLOAD_TIMEOUT_S) as response:
                    response.raise_for_status()
                    with installer_path.open("wb") as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
            except httpx.HTTPError as exc:
                return InstallOutcome(status=InstallStatus.FAILED, message=f"Download error: {exc.__class__.__name__}")

            cmd = [str(installer_path)]
            try:
                completed = subprocess.run(  # noqa: S603 — fixed exe path under our tempdir
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=_RUN_TIMEOUT_S,
                    check=False,
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                return InstallOutcome(status=InstallStatus.FAILED, message=f"Setup error: {exc.__class__.__name__}")

        if completed.returncode != 0:
            return InstallOutcome(
                status=InstallStatus.FAILED,
                message=f"OllamaSetup.exe exited with code {completed.returncode}",
            )
        return InstallOutcome(status=InstallStatus.SUCCESS, message="Ollama installed via OllamaSetup.exe")
