"""Selects the correct Installer for the current host.

Decision order (load-bearing):
  1. is_docker()              → DockerInstaller
  2. system_name() per OS     → matching installer
  3. fallback                 → UnsupportedOSInstaller
"""

from __future__ import annotations

from .installers.docker import DockerInstaller
from .installers.linux import LinuxInstaller
from .installers.macos import MacOSInstaller
from .installers.protocol import ConsentCallback, Installer, InstallOutcome, InstallStatus
from .installers.windows import WindowsInstaller
from .platform_detection import is_docker, system_name


class _UnsupportedOSInstaller:
    """Returned when system_name() is 'unknown'."""

    def install(self, consent_callback: ConsentCallback) -> InstallOutcome:  # noqa: ARG002
        return InstallOutcome(
            status=InstallStatus.UNSUPPORTED,
            message="Operating system not supported for automatic Ollama install.",
        )


def get_installer() -> Installer:
    """Return the Installer strategy appropriate for the current host."""
    if is_docker():
        return DockerInstaller()
    name = system_name()
    if name == "linux":
        return LinuxInstaller()
    if name == "macos":
        return MacOSInstaller()
    if name == "windows":
        return WindowsInstaller()
    return _UnsupportedOSInstaller()
