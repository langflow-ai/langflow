"""Tests for LinuxInstaller — uses the official curl|sh script with explicit consent.

Threat model covered:
  - URL pinning to https://ollama.com/ — reject any other source.
  - Consent: NO subprocess executed if consent_callback returns False.
  - Subprocess hardening: list args (or shell=True only when piping curl|sh in a
    *fixed* string built from a constant URL — never interpolated user input).
  - Timeout enforcement.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch


class TestLinuxInstallerConsent:
    def test_should_return_declined_when_consent_callback_returns_false(self):
        from lfx.services.local_model.installers.linux import LinuxInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        consent_cb = MagicMock(return_value=False)

        with patch("lfx.services.local_model.installers.linux.subprocess.run") as mock_run:
            outcome = LinuxInstaller().install(consent_cb)

        assert outcome.status == InstallStatus.DECLINED
        # Critical: no subprocess executed when consent is denied.
        mock_run.assert_not_called()

    def test_consent_callback_receives_install_url_for_user_review(self):
        from lfx.services.local_model.installers.linux import LinuxInstaller

        consent_cb = MagicMock(return_value=False)
        with patch("lfx.services.local_model.installers.linux.subprocess.run"):
            LinuxInstaller().install(consent_cb)

        # The callback must be told what URL we are about to pipe to sh.
        # This lets a UI present "About to run: <url>" to the user.
        consent_cb.assert_called_once()
        passed_url = consent_cb.call_args.args[0] if consent_cb.call_args.args else consent_cb.call_args.kwargs.get(
            "url"
        )
        assert isinstance(passed_url, str)
        assert passed_url.startswith("https://ollama.com/")


class TestLinuxInstallerUrlPinning:
    def test_install_url_must_be_https_and_ollama_domain(self):
        # Why: this is the load-bearing security control. The constant must be
        # locked down. If someone changes it to http:// or another domain in a
        # future PR, this test fails the build.
        from lfx.services.local_model.installers.linux import OLLAMA_LINUX_INSTALL_URL

        assert OLLAMA_LINUX_INSTALL_URL.startswith("https://ollama.com/")
        assert "install.sh" in OLLAMA_LINUX_INSTALL_URL


class TestLinuxInstallerSubprocess:
    def test_should_call_subprocess_with_timeout_and_no_user_input(self):
        from lfx.services.local_model.installers.linux import LinuxInstaller

        completed = MagicMock(returncode=0, stdout="", stderr="")
        consent_cb = MagicMock(return_value=True)

        with patch("lfx.services.local_model.installers.linux.subprocess.run", return_value=completed) as mock_run:
            LinuxInstaller().install(consent_cb)

        assert mock_run.called
        kwargs = mock_run.call_args.kwargs
        assert "timeout" in kwargs, "subprocess MUST have a timeout"
        assert kwargs["timeout"] >= 30  # install can take a while
        assert kwargs["timeout"] <= 600  # but bounded

    def test_should_return_failed_on_nonzero_exit(self):
        from lfx.services.local_model.installers.linux import LinuxInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        completed = MagicMock(returncode=1, stdout="", stderr="something broke")
        with patch("lfx.services.local_model.installers.linux.subprocess.run", return_value=completed):
            outcome = LinuxInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.FAILED

    def test_should_return_failed_on_subprocess_timeout(self):
        from lfx.services.local_model.installers.linux import LinuxInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        with patch(
            "lfx.services.local_model.installers.linux.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="install", timeout=300),
        ):
            outcome = LinuxInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.FAILED

    def test_should_return_success_on_zero_exit(self):
        from lfx.services.local_model.installers.linux import LinuxInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        completed = MagicMock(returncode=0, stdout="ok", stderr="")
        with patch("lfx.services.local_model.installers.linux.subprocess.run", return_value=completed):
            outcome = LinuxInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.SUCCESS

    def test_subprocess_must_not_interpolate_user_input(self):
        # Why: the install command is built from a fixed, module-level URL constant.
        # No caller-supplied data ever enters the subprocess args. This test pins
        # that contract by inspecting the call args for any sign of unexpected input.
        from lfx.services.local_model.installers.linux import OLLAMA_LINUX_INSTALL_URL, LinuxInstaller

        completed = MagicMock(returncode=0)
        consent_cb = MagicMock(return_value=True)

        with patch("lfx.services.local_model.installers.linux.subprocess.run", return_value=completed) as mock_run:
            LinuxInstaller().install(consent_cb)

        # Flatten args+kwargs into one stringified blob and check it only mentions
        # the pinned URL — no other URL or shell metacharacter the test didn't expect.
        flat = repr(mock_run.call_args)
        assert OLLAMA_LINUX_INSTALL_URL in flat
        # No other http(s) URL leaked in
        forbidden_substrings = ["http://", "https://evil", "https://github", "$(", "`", "$IFS"]
        for bad in forbidden_substrings:
            assert bad not in flat, f"unexpected token {bad!r} in subprocess args: {flat}"
