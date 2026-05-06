"""Tests for installer_factory — selects the correct installer for the host.

Why a factory: the platform decision (Linux/macOS/Windows/Docker) is centralized
here so callers downstream (CLI, API endpoint, bootstrap) never branch on OS
themselves. New platforms = new strategy + one factory edit.

Strategy selection rules:
  is_docker()              → DockerInstaller       (refuses with guidance)
  system_name() == linux   → LinuxInstaller
  system_name() == macos   → MacOSInstaller
  system_name() == windows → WindowsInstaller
  system_name() == unknown → UnsupportedOSInstaller (returns UNSUPPORTED)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestFactorySelection:
    @pytest.mark.parametrize(
        ("system", "expected_class_name"),
        [
            ("linux", "LinuxInstaller"),
            ("macos", "MacOSInstaller"),
            ("windows", "WindowsInstaller"),
        ],
    )
    def test_should_pick_installer_for_each_supported_os(self, system, expected_class_name):
        from lfx.services.local_model.installer_factory import get_installer

        with (
            patch("lfx.services.local_model.installer_factory.is_docker", return_value=False),
            patch("lfx.services.local_model.installer_factory.system_name", return_value=system),
        ):
            installer = get_installer()

        assert type(installer).__name__ == expected_class_name

    def test_docker_takes_precedence_over_system_name(self):
        # Why: a Linux container detected as Docker MUST get DockerInstaller, not
        # LinuxInstaller. The order of the checks in the factory is load-bearing.
        from lfx.services.local_model.installer_factory import get_installer

        with (
            patch("lfx.services.local_model.installer_factory.is_docker", return_value=True),
            patch("lfx.services.local_model.installer_factory.system_name", return_value="linux"),
        ):
            installer = get_installer()

        assert type(installer).__name__ == "DockerInstaller"

    def test_unknown_system_returns_unsupported_installer(self):
        from lfx.services.local_model.installer_factory import get_installer
        from lfx.services.local_model.installers.protocol import InstallStatus

        with (
            patch("lfx.services.local_model.installer_factory.is_docker", return_value=False),
            patch("lfx.services.local_model.installer_factory.system_name", return_value="unknown"),
        ):
            installer = get_installer()

        from unittest.mock import MagicMock

        outcome = installer.install(MagicMock())
        assert outcome.status == InstallStatus.UNSUPPORTED


class TestFactoryReturnsValidInstallers:
    def test_every_returned_installer_satisfies_protocol(self):
        from lfx.services.local_model.installer_factory import get_installer
        from lfx.services.local_model.installers.protocol import Installer

        for system in ("linux", "macos", "windows", "unknown"):
            with (
                patch("lfx.services.local_model.installer_factory.is_docker", return_value=False),
                patch("lfx.services.local_model.installer_factory.system_name", return_value=system),
            ):
                installer = get_installer()
            assert isinstance(installer, Installer)

        # Plus Docker
        with patch("lfx.services.local_model.installer_factory.is_docker", return_value=True):
            installer = get_installer()
        assert isinstance(installer, Installer)
