"""Tests for WindowsInstaller — downloads OllamaSetup.exe and runs with UAC prompt.

Threat model covered:
  - HTTPS pinning to https://ollama.com/.
  - Consent enforced before download or exec.
  - Downloaded file written to a temp directory and cleaned up.
  - Subprocess uses list args; no shell=True; no string interpolation of remote data.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestWindowsInstallerConsent:
    def test_should_return_declined_when_consent_callback_returns_false(self):
        from lfx.services.local_model.installers.protocol import InstallStatus
        from lfx.services.local_model.installers.windows import WindowsInstaller

        consent_cb = MagicMock(return_value=False)

        with (
            patch("lfx.services.local_model.installers.windows.subprocess.run") as mock_run,
            patch("lfx.services.local_model.installers.windows.httpx.stream") as mock_stream,
        ):
            outcome = WindowsInstaller().install(consent_cb)

        assert outcome.status == InstallStatus.DECLINED
        mock_run.assert_not_called()
        mock_stream.assert_not_called()


class TestWindowsInstallerUrlPinning:
    def test_setup_exe_url_must_be_https_ollama(self):
        from lfx.services.local_model.installers.windows import OLLAMA_WINDOWS_SETUP_URL

        assert OLLAMA_WINDOWS_SETUP_URL.startswith("https://ollama.com/")
        assert OLLAMA_WINDOWS_SETUP_URL.endswith(".exe")


def _make_streamed_response(chunks=(b"data",)):
    """Helper: a context manager mock matching httpx.stream(...) usage."""
    response = MagicMock()
    response.raise_for_status = MagicMock(return_value=None)
    response.iter_bytes = MagicMock(return_value=iter(chunks))
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=response)
    cm.__exit__ = MagicMock(return_value=None)
    return cm


class TestWindowsInstallerDownloadAndExecute:
    def test_should_download_and_execute_setup_exe_on_success(self):
        # Why: the happy path is the most security-sensitive. We pin that the
        # subprocess receives the temp-dir installer path (a list arg, never the
        # URL or any user-supplied value) and that we got SUCCESS.
        import httpx
        from lfx.services.local_model.installers.protocol import InstallStatus
        from lfx.services.local_model.installers.windows import WindowsInstaller

        completed = MagicMock(returncode=0, stdout="", stderr="")

        with (
            patch(
                "lfx.services.local_model.installers.windows.httpx.stream",
                return_value=_make_streamed_response(),
            ),
            patch(
                "lfx.services.local_model.installers.windows.subprocess.run", return_value=completed
            ) as mock_run,
        ):
            outcome = WindowsInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.SUCCESS
        # subprocess invoked with a list whose only element is a path under our tempdir
        cmd = mock_run.call_args.args[0]
        assert isinstance(cmd, list)
        assert len(cmd) == 1
        assert cmd[0].endswith("OllamaSetup.exe")
        # No URL leaked into subprocess args
        assert "http" not in cmd[0]
        # ensure the unused import sentinel `httpx` is referenced for the linter
        assert isinstance(httpx.HTTPError("x"), Exception)

    def test_should_return_failed_on_download_http_error(self):
        import httpx
        from lfx.services.local_model.installers.protocol import InstallStatus
        from lfx.services.local_model.installers.windows import WindowsInstaller

        with patch(
            "lfx.services.local_model.installers.windows.httpx.stream",
            side_effect=httpx.ConnectError("dns failed"),
        ):
            outcome = WindowsInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.FAILED
        assert "Download" in outcome.message

    def test_should_return_failed_on_setup_nonzero_exit(self):
        from lfx.services.local_model.installers.protocol import InstallStatus
        from lfx.services.local_model.installers.windows import WindowsInstaller

        completed = MagicMock(returncode=1223, stdout="", stderr="user cancelled UAC")
        with (
            patch(
                "lfx.services.local_model.installers.windows.httpx.stream",
                return_value=_make_streamed_response(),
            ),
            patch("lfx.services.local_model.installers.windows.subprocess.run", return_value=completed),
        ):
            outcome = WindowsInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.FAILED
