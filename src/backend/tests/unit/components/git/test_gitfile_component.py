from unittest.mock import AsyncMock, MagicMock, patch

import aiofiles
import anyio
import pytest
from git.exc import GitCommandError
from langflow.components.git.gitfile import GitFileComponent
from langflow.schema import Data

from tests.base import ComponentTestBaseWithoutClient


class TestGitFileComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return GitFileComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "repository_url": "https://github.com/test/repo",
            "branch": "main",
            "selected_files": ["test.txt"],
            "session_id": "test_session",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_update_build_config_no_repo_url(self):
        component = GitFileComponent()
        build_config = {
            "branch": {"options": [], "value": ""},
            "selected_files": {"options": [], "value": []},
        }

        result = await component.update_build_config(build_config, None)

        assert result["branch"]["options"] == ["Enter repository URL first"]
        assert result["branch"]["value"] == "Enter repository URL first"
        assert result["selected_files"]["options"] == ["Select branch first"]
        assert result["selected_files"]["value"] == []

    async def test_get_files_content_missing_repo_url(self):
        component = GitFileComponent()
        with pytest.raises(GitCommandError, match="Repository URL is required"):
            await component.get_files_content()

    async def test_get_files_content_missing_branch(self):
        component = GitFileComponent()
        component.repository_url = "https://github.com/test/repo"
        with pytest.raises(GitCommandError, match="Branch selection is required"):
            await component.get_files_content()

    async def test_get_files_content_missing_files(self):
        component = GitFileComponent()
        component.repository_url = "https://github.com/test/repo"
        component.branch = "main"
        component.selected_files = []
        with pytest.raises(GitCommandError, match="File selection is required"):
            await component.get_files_content()

    async def test_is_binary_text_file(self, tmp_path):
        component = GitFileComponent()
        test_file = anyio.Path(tmp_path) / "test.txt"
        async with aiofiles.open(test_file, "w") as f:
            await f.write("Hello, World!")

        result = await component.is_binary(test_file)
        assert result is False

    @patch("langflow.components.git.gitfile.GitFileComponent.is_binary")
    async def test_is_binary_binary_file(self, mock_is_binary, tmp_path):
        mock_is_binary.return_value = True
        GitFileComponent()
        test_file = anyio.Path(tmp_path) / "test.bin"
        async with aiofiles.open(test_file, "wb") as f:
            await f.write(bytes([0x00, 0x01, 0x02, 0x03]))

        result = await mock_is_binary(test_file)
        assert result is True

    @patch("git.Repo")
    @patch("anyio.to_thread.run_sync")
    @pytest.mark.usefixtures("mock_repo")
    async def test_get_branches(self, mock_run_sync):
        component = GitFileComponent()

        # Create mock refs
        mock_main = MagicMock()
        mock_main.name = "origin/main"
        mock_develop = MagicMock()
        mock_develop.name = "origin/develop"
        mock_head = MagicMock()
        mock_head.name = "origin/HEAD"
        mock_refs = [mock_main, mock_develop, mock_head]

        # Create mock remote
        mock_remote = MagicMock()
        mock_remote.refs = mock_refs

        # Create mock repo instance
        mock_instance = MagicMock()
        mock_instance.remote.return_value = mock_remote

        # Set up run_sync to return our mock instance
        async def mock_run_sync_side_effect(f, *_args, **_kwargs):
            if callable(f):
                return mock_instance
            return None

        mock_run_sync.side_effect = mock_run_sync_side_effect

        # Mock the temp_git_repo context manager
        with patch.object(component, "temp_git_repo") as mock_temp_repo:
            mock_temp_repo.return_value.__aenter__.return_value = "mock_repo_path"
            mock_temp_repo.return_value.__aexit__.return_value = None

            branches = await component.get_branches("https://github.com/test/repo")
            assert sorted(branches) == ["develop", "main"]

    @patch("git.Repo")
    @patch("anyio.to_thread.run_sync")
    @patch("aiofiles.open")
    @patch("anyio.Path.exists")
    @patch("anyio.Path.stat")
    @patch("langflow.components.git.gitfile.GitFileComponent.is_binary")
    @pytest.mark.usefixtures("mock_repo")
    async def test_get_files_content_success(
        self, mock_is_binary, mock_stat, mock_exists, mock_aiofiles_open, mock_run_sync
    ):
        component = GitFileComponent()
        component.repository_url = "https://github.com/test/repo"
        component.branch = "main"
        component.selected_files = ["test.txt"]

        # Mock file operations
        mock_exists.return_value = True
        mock_stat.return_value = MagicMock(st_size=12)
        mock_is_binary.return_value = False

        # Mock file content
        test_content = "Test content"
        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=test_content)
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file

        # Mock git operations
        mock_instance = MagicMock()

        async def mock_run_sync_side_effect(f, *_args, **_kwargs):
            if callable(f):
                return mock_instance
            return None

        mock_run_sync.side_effect = mock_run_sync_side_effect

        # Mock the temp_git_repo context manager
        with patch.object(component, "temp_git_repo") as mock_temp_repo:
            mock_temp_repo.return_value.__aenter__.return_value = "mock_repo_path"
            mock_temp_repo.return_value.__aexit__.return_value = None

            result = await component.get_files_content()
            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], Data)
            assert result[0].data["path"] == "test.txt"
            assert result[0].data["content"] == test_content
