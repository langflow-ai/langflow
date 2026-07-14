"""Regression tests for Git clone URL validation."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _enable_ssrf(monkeypatch):
    monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)


@pytest.mark.parametrize(
    "url",
    [
        'ext::sh -c "touch /tmp/pwned"',
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
async def test_git_extractor_blocks_dangerous_url_before_clone(url):
    from lfx.components.git.gitextractor import GitExtractorComponent
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = GitExtractorComponent(repository_url=url)
    with (
        patch("lfx.components.git.gitextractor.git.Repo.clone_from") as mock_clone,
        pytest.raises((SSRFProtectionError, ValueError)),
    ):
        await component.get_repository_info()

    mock_clone.assert_not_called()


async def test_git_loader_blocks_remote_helper_before_loader():
    from lfx.components.git.git import GitLoaderComponent
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = GitLoaderComponent(repo_source="Remote", clone_url='ext::sh -c "id"')
    with patch("lfx.components.git.git.GitLoader") as mock_loader, pytest.raises(SSRFProtectionError):
        await component.build_gitloader()

    mock_loader.assert_not_called()
