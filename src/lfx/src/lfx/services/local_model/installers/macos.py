"""macOS installer — Homebrew first, then official download as fallback.

Why brew first: it is the most common package manager on macOS and the cleanest
audit trail for the user. The fallback download is documented but reserved for
machines without brew.
"""

from __future__ import annotations

import shutil
import subprocess

from .protocol import ConsentCallback, InstallOutcome, InstallStatus

OLLAMA_MACOS_DOWNLOAD_URL = "https://ollama.com/download/Ollama-darwin.zip"

_BREW_TIMEOUT_S = 300


class MacOSInstaller:
    """macOS installer that prefers Homebrew."""

    def install(self, consent_callback: ConsentCallback) -> InstallOutcome:
        brew_path = shutil.which("brew")
        target_url = brew_path or OLLAMA_MACOS_DOWNLOAD_URL

        if not consent_callback(target_url):
            return InstallOutcome(status=InstallStatus.DECLINED, message="User declined")

        if brew_path is None:
            # Slice 3 stops at brew. The .zip-fallback download path is intentionally
            # left as a documented limitation so this slice ships without an
            # untested manual-download flow. Falls back to UNSUPPORTED with guidance.
            return InstallOutcome(
                status=InstallStatus.UNSUPPORTED,
                message="Homebrew not found. Install brew or download Ollama manually from https://ollama.com",
            )

        cmd = [brew_path, "install", "ollama"]
        try:
            completed = subprocess.run(  # noqa: S603 — fixed cmd, brew_path from shutil.which
                cmd,
                capture_output=True,
                text=True,
                timeout=_BREW_TIMEOUT_S,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return InstallOutcome(status=InstallStatus.FAILED, message=f"brew error: {exc.__class__.__name__}")

        if completed.returncode != 0:
            return InstallOutcome(
                status=InstallStatus.FAILED,
                message=f"brew install ollama exited with code {completed.returncode}",
            )
        return InstallOutcome(status=InstallStatus.SUCCESS, message="Ollama installed via Homebrew")
