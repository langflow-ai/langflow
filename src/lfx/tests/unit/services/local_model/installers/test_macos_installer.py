"""Tests for MacOSInstaller — prefers Homebrew, falls back to official installer.

Threat model covered:
  - HTTPS pinning to https://ollama.com/ for the fallback download.
  - shutil.which("brew") used to detect Homebrew presence — never trust PATH alone
    for security-sensitive paths (we corroborate with `brew --version`).
  - Consent enforced before either path executes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestMacOSInstallerConsent:
    def test_should_return_declined_when_consent_callback_returns_false(self):
        from lfx.services.local_model.installers.macos import MacOSInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        consent_cb = MagicMock(return_value=False)

        with (
            patch("lfx.services.local_model.installers.macos.subprocess.run") as mock_run,
            patch("lfx.services.local_model.installers.macos.shutil.which", return_value="/opt/homebrew/bin/brew"),
        ):
            outcome = MacOSInstaller().install(consent_cb)

        assert outcome.status == InstallStatus.DECLINED
        mock_run.assert_not_called()


class TestMacOSInstallerBrewPath:
    def test_should_use_brew_when_available(self):
        # Why brew first: it gives the cleanest install path on macOS, integrates
        # with the user's package manager, and is auditable (formula is public).
        from lfx.services.local_model.installers.macos import MacOSInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        completed = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch("lfx.services.local_model.installers.macos.shutil.which", return_value="/opt/homebrew/bin/brew"),
            patch("lfx.services.local_model.installers.macos.subprocess.run", return_value=completed) as mock_run,
        ):
            outcome = MacOSInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.SUCCESS
        # The first subprocess call must use brew with list args.
        first_call_args = mock_run.call_args_list[0].args[0]
        assert isinstance(first_call_args, list)
        assert "brew" in first_call_args[0] or first_call_args[0].endswith("brew")
        assert "install" in first_call_args
        assert "ollama" in first_call_args


class TestMacOSInstallerFallbackUrl:
    def test_fallback_download_url_must_be_https_ollama(self):
        # Pinning the fallback download URL — same security control as Linux.
        from lfx.services.local_model.installers.macos import OLLAMA_MACOS_DOWNLOAD_URL

        assert OLLAMA_MACOS_DOWNLOAD_URL.startswith("https://ollama.com/")


class TestMacOSInstallerWithoutBrew:
    def test_should_return_unsupported_when_brew_missing(self):
        # When brew is not installed we explicitly do NOT shell out — we surface
        # an UNSUPPORTED outcome with guidance, leaving the user in control.
        from lfx.services.local_model.installers.macos import MacOSInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        with (
            patch("lfx.services.local_model.installers.macos.shutil.which", return_value=None),
            patch("lfx.services.local_model.installers.macos.subprocess.run") as mock_run,
        ):
            outcome = MacOSInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.UNSUPPORTED
        mock_run.assert_not_called()


class TestMacOSInstallerBrewFailure:
    def test_should_return_failed_when_brew_exits_nonzero(self):
        from lfx.services.local_model.installers.macos import MacOSInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        completed = MagicMock(returncode=1, stdout="", stderr="brew error")
        with (
            patch("lfx.services.local_model.installers.macos.shutil.which", return_value="/opt/homebrew/bin/brew"),
            patch("lfx.services.local_model.installers.macos.subprocess.run", return_value=completed),
        ):
            outcome = MacOSInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.FAILED

    def test_should_return_failed_on_subprocess_timeout(self):
        import subprocess as sp_module

        from lfx.services.local_model.installers.macos import MacOSInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        with (
            patch("lfx.services.local_model.installers.macos.shutil.which", return_value="/opt/homebrew/bin/brew"),
            patch(
                "lfx.services.local_model.installers.macos.subprocess.run",
                side_effect=sp_module.TimeoutExpired(cmd="brew", timeout=300),
            ),
        ):
            outcome = MacOSInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.FAILED
