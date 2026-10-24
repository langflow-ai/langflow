"""Security regression tests for the Git components.

A tenant-controlled repository URL handed to ``git clone`` enables RCE via the ``ext::``
remote helper, arbitrary local-file disclosure via ``file://`` / bare paths, and SSRF to
internal hosts. These tests confirm the dangerous URL never reaches ``git.Repo.clone_from``.
"""

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("lfx_bundles")


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


class TestGitExtractorComponent:
    @pytest.fixture
    def component_class(self):
        from lfx.components.git.gitextractor import GitExtractorComponent

        return GitExtractorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"repository_url": "https://example.com/repository.git"}

    @pytest.fixture
    def gitextractor_repo_with_symlink(self, component_class, default_kwargs, tmp_path, monkeypatch):
        """Provide a checked-out tree whose symlinks point outside the repository."""
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / "README.md").write_bytes(b"repository content\n")

        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("SAFE_CANARY\n" * 3, encoding="utf-8")
        (repository / "linked.txt").symlink_to(outside_file)

        outside_directory = tmp_path / "outside-directory"
        outside_directory.mkdir()
        (repository / "linked-directory").symlink_to(outside_directory, target_is_directory=True)

        @asynccontextmanager
        async def fake_temp_git_repo(_self):
            yield str(repository)

        monkeypatch.setattr(component_class, "temp_git_repo", fake_temp_git_repo)
        return component_class(**default_kwargs)

    async def test_files_content_skips_symlinks(self, gitextractor_repo_with_symlink):
        result = await gitextractor_repo_with_symlink.get_files_content()

        assert [item.data["path"] for item in result] == ["README.md"]
        assert "SAFE_CANARY" not in result[0].data["content"]

    async def test_text_content_skips_symlinks(self, gitextractor_repo_with_symlink):
        result = await gitextractor_repo_with_symlink.get_text_based_file_contents()

        assert "README.md" in result.text
        assert "linked.txt" not in result.text
        assert "SAFE_CANARY" not in result.text

    async def test_statistics_skips_symlinks(self, gitextractor_repo_with_symlink):
        result = await gitextractor_repo_with_symlink.get_statistics()

        assert result[0].data["total_files"] == 1
        assert result[0].data["total_lines"] == 1
        assert result[0].data["total_size_bytes"] == len(b"repository content\n")
        assert result[0].data["directories"] == 0


@pytest.mark.usefixtures("ssrf_on")
class TestGitLoaderComponent:
    @pytest.fixture
    def gitloader_repo_with_symlinks(self, tmp_path, monkeypatch):
        from git import Repo
        from lfx.components.git.git import GitLoaderComponent

        settings = MagicMock()
        settings.settings.restrict_local_file_access = False
        monkeypatch.setattr("lfx.utils.file_path_security.get_settings_service", lambda: settings)

        repository = tmp_path / "loader-repository"
        repository.mkdir()
        (repository / "README.md").write_text("repository readme\n", encoding="utf-8")
        (repository / "docs").mkdir()
        (repository / "docs" / "guide.txt").write_text("repository guide\n", encoding="utf-8")

        outside_directory = tmp_path / "loader-outside"
        outside_directory.mkdir()
        outside_file = outside_directory / "outside.txt"
        outside_file.write_text("OUTSIDE_REPOSITORY_CONTENT\n", encoding="utf-8")
        (outside_directory / "nested.txt").write_text("OUTSIDE_REPOSITORY_CONTENT\n", encoding="utf-8")

        (repository / "linked.txt").symlink_to(outside_file)
        (repository / "linked-directory").symlink_to(outside_directory, target_is_directory=True)

        git_repo = Repo.init(repository, initial_branch="main")
        git_repo.index.add(["README.md", "docs/guide.txt", "linked.txt", "linked-directory"])
        with git_repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")
        git_repo.index.commit("Add repository fixtures")

        component = GitLoaderComponent(repo_source="Local", repo_path=str(repository), branch="main")
        return component, repository

    async def test_load_documents_skips_symlinks(self, gitloader_repo_with_symlinks):
        component, _ = gitloader_repo_with_symlinks

        result = await component.load_documents()

        assert sorted(item.data["source"] for item in result) == ["README.md", "docs/guide.txt"]
        assert all("OUTSIDE_REPOSITORY_CONTENT" not in item.data["text"] for item in result)

    def test_combined_filter_rejects_symlinks(self, gitloader_repo_with_symlinks):
        component, repository = gitloader_repo_with_symlinks
        filter_func = component.build_combined_filter(repo_path=repository)

        assert filter_func(str(repository / "README.md"))
        assert not filter_func(str(repository / "linked.txt"))
        assert not filter_func(str(repository / "linked-directory" / "nested.txt"))
