"""SSRF / RCE regression tests for the Git components' clone URL handling.

A tenant-controlled repository URL handed to ``git clone`` enables RCE via the ``ext::``
remote helper, arbitrary local-file disclosure via ``file://`` / bare paths, and SSRF to
internal hosts. These tests confirm the dangerous URL never reaches ``git.Repo.clone_from``.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def ssrf_on():
    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get:
        s = MagicMock()
        s.settings.ssrf_protection_enabled = True
        s.settings.ssrf_allowed_hosts = []
        s.settings.restrict_local_file_access = False
        mock_get.return_value = s
        yield


@pytest.mark.usefixtures("ssrf_on")
@pytest.mark.parametrize(
    "url",
    [
        'ext::sh -c "touch /tmp/pwned"',  # remote-helper RCE
        "file:///etc/passwd",  # local file read
        "/etc/passwd",  # bare local path
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata SSRF
        "-upload-pack=evil",  # git option injection
    ],
)
async def test_gitextractor_blocks_dangerous_url(url):
    from lfx.components.git.gitextractor import GitExtractorComponent
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = GitExtractorComponent(repository_url=url)
    with patch("lfx.components.git.gitextractor.git.Repo.clone_from") as mock_clone:
        with pytest.raises((SSRFProtectionError, ValueError)):
            await component.get_repository_info()
        assert mock_clone.call_count == 0


@pytest.mark.usefixtures("ssrf_on")
async def test_gitloader_blocks_dangerous_clone_url():
    from lfx.components.git.git import GitLoaderComponent
    from lfx.utils.ssrf_protection import SSRFProtectionError

    component = GitLoaderComponent(repo_source="Remote", clone_url='ext::sh -c "id"')
    with patch("lfx.components.git.git.GitLoader") as mock_loader:
        with pytest.raises((SSRFProtectionError, ValueError)):
            await component.build_gitloader()
        assert mock_loader.call_count == 0
