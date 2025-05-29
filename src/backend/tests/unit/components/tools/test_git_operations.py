import os
import shutil
import tempfile

import pytest
from langflow.components.tools.git_operations import GitOperations

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestGitOperations(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return GitOperations

    @pytest.fixture
    def temp_workspace(self):
        temp_dir = tempfile.mkdtemp(prefix="gitopstest_")
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def default_kwargs(self, temp_workspace):
        return {
            "workspace_folder": temp_workspace,
            "create_if_missing": True,
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        return []

    def test_init_and_status(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        git_init = [t for t in tools if getattr(t, "name", None) == "git_init"][0]
        git_status = [t for t in tools if getattr(t, "name", None) == "git_status"][0]
        # Should not be a repo yet
        assert "Not a Git repository" in git_status({})
        # Init repo
        assert "Initialized empty Git repository" in git_init({})
        # Now status should work
        status = git_status({})
        assert "On branch" in status or "No commits yet" in status

    def test_add_commit_log(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        git_init = [t for t in tools if getattr(t, "name", None) == "git_init"][0]
        git_add = [t for t in tools if getattr(t, "name", None) == "git_add"][0]
        git_commit = [t for t in tools if getattr(t, "name", None) == "git_commit"][0]
        git_log = [t for t in tools if getattr(t, "name", None) == "git_log"][0]
        # Init repo
        git_init({})
        # Create a file
        file_path = os.path.join(component.workspace_folder, "test.txt")
        with open(file_path, "w") as f:
            f.write("hello world")
        # Add file
        assert "Command executed successfully" in git_add({"paths": ["test.txt"]})
        # Commit
        assert "files changed" in git_commit({"message": "Initial commit"}) or "nothing to commit" not in git_commit(
            {"message": "Initial commit"}
        )
        # Log
        log = git_log({"max_count": 1})
        assert "Initial commit" in log or "commit" in log

    def test_branch_checkout_merge(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        git_init = [t for t in tools if getattr(t, "name", None) == "git_init"][0]
        git_branch = [t for t in tools if getattr(t, "name", None) == "git_branch"][0]
        git_checkout = [t for t in tools if getattr(t, "name", None) == "git_checkout"][0]
        git_merge = [t for t in tools if getattr(t, "name", None) == "git_merge"][0]
        git_commit = [t for t in tools if getattr(t, "name", None) == "git_commit"][0]
        git_add = [t for t in tools if getattr(t, "name", None) == "git_add"][0]
        # Init repo
        git_init({})
        # Create and commit on main
        file_path = os.path.join(component.workspace_folder, "main.txt")
        with open(file_path, "w") as f:
            f.write("main branch")
        git_add({"paths": ["main.txt"]})
        git_commit({"message": "main commit"})
        # Create new branch
        assert "Command executed successfully" in git_branch({"new_branch": "feature"})
        # Checkout new branch
        assert "Command executed successfully" in git_checkout({"branch_name": "feature"})
        # Add file on feature branch
        file_path2 = os.path.join(component.workspace_folder, "feature.txt")
        with open(file_path2, "w") as f:
            f.write("feature branch")
        git_add({"paths": ["feature.txt"]})
        git_commit({"message": "feature commit"})
        # Checkout main and merge
        git_checkout({"branch_name": "main"})
        merge_result = git_merge({"source_branch": "feature"})
        assert "Merge conflict" not in merge_result
        assert "Command executed successfully" in merge_result or "Already up to date" in merge_result

    def test_command_history(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tools = component.build_toolkit()
        git_init = [t for t in tools if getattr(t, "name", None) == "git_init"][0]
        git_command_history = [t for t in tools if getattr(t, "name", None) == "git_command_history"][0]
        git_init({})
        history = git_command_history({})
        assert "git init" in history
