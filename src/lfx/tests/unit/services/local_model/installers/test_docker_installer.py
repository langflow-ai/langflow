"""Tests for DockerInstaller — refuses to install inside a container.

Why this exists at all (vs. just skipping): being explicit about the Docker
strategy means the install path is closed-by-default. If a future change
accidentally routes a Docker container to the LinuxInstaller, the test for
"DockerInstaller is selected when is_docker()" will fail in the factory tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock


class TestDockerInstaller:
    def test_should_return_unsupported_status(self):
        from lfx.services.local_model.installers.docker import DockerInstaller
        from lfx.services.local_model.installers.protocol import InstallStatus

        outcome = DockerInstaller().install(MagicMock(return_value=True))

        assert outcome.status == InstallStatus.UNSUPPORTED

    def test_message_should_guide_user_to_docker_compose(self):
        # Why: when the user is in a container and we refuse, we owe them a clear
        # next step. The message is part of the API contract — UI tests will assert
        # on it. We pin specific keywords here so a sloppy reword doesn't drop the
        # actionable instruction.
        from lfx.services.local_model.installers.docker import DockerInstaller

        outcome = DockerInstaller().install(MagicMock(return_value=True))

        msg = outcome.message.lower()
        assert "docker" in msg
        assert "host" in msg or "compose" in msg

    def test_should_never_call_consent_callback(self):
        # Why: consent is for "we are about to do something on your machine". We
        # are doing nothing — so we must NOT prompt and NOT confuse the UX with a
        # consent dialog that goes nowhere.
        from lfx.services.local_model.installers.docker import DockerInstaller

        consent_cb = MagicMock()
        DockerInstaller().install(consent_cb)

        consent_cb.assert_not_called()
