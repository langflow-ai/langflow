"""Tests for bootstrap.ensure_local_model_ready — the end-to-end pipeline.

Each test mocks the four dependent capabilities (is_docker, is_ollama_installed,
get_installer, ollama_health, model_puller) and exercises one branch of the
pipeline. Together they pin every observable outcome of the orchestrator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _patch_pipeline(
    *,
    is_docker: bool = False,
    is_installed: bool = True,
    install_status=None,
    is_running: bool = True,
    is_pulled: bool = True,
    pull_status=None,
):
    """Helper: returns a list of patch context managers covering all 5 boundary calls."""
    from lfx.services.local_model.installers.protocol import InstallOutcome, InstallStatus
    from lfx.services.local_model.model_puller import PullOutcome, PullStatus

    install_status = install_status if install_status is not None else InstallStatus.SUCCESS
    pull_status = pull_status if pull_status is not None else PullStatus.SUCCESS

    installer = MagicMock()
    installer.install = MagicMock(return_value=InstallOutcome(status=install_status))

    return [
        patch("lfx.services.local_model.bootstrap.is_docker", return_value=is_docker),
        patch("lfx.services.local_model.bootstrap.is_ollama_installed", return_value=is_installed),
        patch("lfx.services.local_model.bootstrap.get_installer", return_value=installer),
        patch("lfx.services.local_model.bootstrap.is_ollama_running", AsyncMock(return_value=is_running)),
        patch("lfx.services.local_model.bootstrap.is_model_pulled", AsyncMock(return_value=is_pulled)),
        patch(
            "lfx.services.local_model.bootstrap.pull_model",
            AsyncMock(return_value=PullOutcome(status=pull_status)),
        ),
        patch("lfx.services.local_model.bootstrap.asyncio.sleep", AsyncMock(return_value=None)),
    ]


# ---------------------------------------------------------------------------
# BootstrapStatus + BootstrapOutcome
# ---------------------------------------------------------------------------


class TestBootstrapStatus:
    @pytest.mark.parametrize(
        "name",
        [
            "READY",
            "DOCKER_GUIDANCE",
            "INSTALL_DECLINED",
            "INSTALL_FAILED",
            "OLLAMA_NOT_RUNNING",
            "PULL_FAILED",
            "UNSUPPORTED_OS",
        ],
    )
    def test_should_expose_canonical_status(self, name):
        from lfx.services.local_model.bootstrap import BootstrapStatus

        assert hasattr(BootstrapStatus, name)


class TestBootstrapOutcome:
    def test_should_be_frozen(self):
        from lfx.services.local_model.bootstrap import BootstrapOutcome, BootstrapStatus

        outcome = BootstrapOutcome(status=BootstrapStatus.READY)

        with pytest.raises((AttributeError, TypeError)):
            outcome.status = BootstrapStatus.PULL_FAILED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline branches
# ---------------------------------------------------------------------------


class TestBootstrapPipeline:
    @pytest.mark.asyncio
    async def test_should_short_circuit_with_docker_guidance_when_in_container(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready

        consent_cb = MagicMock()
        progress_cb = MagicMock()

        with self._stack(_patch_pipeline(is_docker=True)):
            outcome = await ensure_local_model_ready(consent_cb, progress_cb)

        assert outcome.status == BootstrapStatus.DOCKER_GUIDANCE
        # Critical: when in Docker we must NOT prompt the user for consent.
        consent_cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_return_install_declined_when_user_says_no(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready
        from lfx.services.local_model.installers.protocol import InstallStatus

        with self._stack(_patch_pipeline(is_installed=False, install_status=InstallStatus.DECLINED)):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.INSTALL_DECLINED

    @pytest.mark.asyncio
    async def test_should_return_install_failed_when_install_breaks(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready
        from lfx.services.local_model.installers.protocol import InstallStatus

        with self._stack(_patch_pipeline(is_installed=False, install_status=InstallStatus.FAILED)):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.INSTALL_FAILED

    @pytest.mark.asyncio
    async def test_should_return_unsupported_os_when_installer_unsupported(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready
        from lfx.services.local_model.installers.protocol import InstallStatus

        with self._stack(_patch_pipeline(is_installed=False, install_status=InstallStatus.UNSUPPORTED)):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.UNSUPPORTED_OS

    @pytest.mark.asyncio
    async def test_should_return_ollama_not_running_when_health_keeps_failing(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready

        # Even after install succeeded, Ollama may not start (sandbox, missing
        # systemd, user closed app, etc.). We retry briefly then surface a clear
        # error so the user knows the next step is manual.
        with self._stack(_patch_pipeline(is_running=False)):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.OLLAMA_NOT_RUNNING

    @pytest.mark.asyncio
    async def test_should_pull_model_when_not_present_and_succeed(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready
        from lfx.services.local_model.model_puller import PullStatus

        with self._stack(_patch_pipeline(is_pulled=False, pull_status=PullStatus.SUCCESS)):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.READY

    @pytest.mark.asyncio
    async def test_should_return_pull_failed_when_pull_breaks(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready
        from lfx.services.local_model.model_puller import PullStatus

        with self._stack(_patch_pipeline(is_pulled=False, pull_status=PullStatus.FAILED)):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.PULL_FAILED

    @pytest.mark.asyncio
    async def test_should_return_ready_when_everything_already_set_up(self):
        from lfx.services.local_model.bootstrap import BootstrapStatus, ensure_local_model_ready

        with self._stack(_patch_pipeline()):
            outcome = await ensure_local_model_ready(MagicMock(), MagicMock())

        assert outcome.status == BootstrapStatus.READY

    @pytest.mark.asyncio
    async def test_install_path_does_not_run_when_already_installed(self):
        from lfx.services.local_model.bootstrap import ensure_local_model_ready
        from lfx.services.local_model.installers.protocol import InstallOutcome, InstallStatus

        installer = MagicMock()
        installer.install = MagicMock(return_value=InstallOutcome(status=InstallStatus.SUCCESS))

        with patch.multiple(
            "lfx.services.local_model.bootstrap",
            is_docker=MagicMock(return_value=False),
            is_ollama_installed=MagicMock(return_value=True),
            get_installer=MagicMock(return_value=installer),
            is_ollama_running=AsyncMock(return_value=True),
            is_model_pulled=AsyncMock(return_value=True),
        ):
            await ensure_local_model_ready(MagicMock(), MagicMock())

        # Critical: re-install would be wasteful and could surprise users with
        # a UAC/sudo prompt for no reason.
        installer.install.assert_not_called()

    @staticmethod
    def _stack(patches):
        """Helper to enter a list of patch context managers as a single block."""
        from contextlib import ExitStack

        stack = ExitStack()
        for p in patches:
            stack.enter_context(p)
        return stack
