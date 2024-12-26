import os
import shutil
import tempfile
from pathlib import Path

import git

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, MultiselectInput, Output
from langflow.schema import Data


class GitFileComponent(Component):
    display_name = "GitFile"
    description = "Analyzes a Git repository and returns the content of selected files from specified branch"
    icon = "GitLoader"
    inputs = [
        MessageTextInput(
            name="repository_url",
            display_name="Repository URL",
            info="URL of the Git repository (e.g., https://github.com/username/repo)",
            value="",
        ),
        DropdownInput(
            name="branch",
            display_name="Branch",
            info="Select a branch from the repository",
            options=["Enter repository URL first"],
            value="Enter repository URL first",
            refresh_button=True,
        ),
        MultiselectInput(
            name="selected_files",
            display_name="Select Files",
            info="Select one or more files from the repository",
            options=["Select branch first"],
            value=[],
            refresh_button=True,
        ),
    ]
    outputs = [
        Output(display_name="Files Content", name="files_content", method="get_files_content"),
    ]

    def is_binary(self, file_path):
        try:
            with Path(file_path).open() as check_file:
                check_file.read()
                return False
        except UnicodeDecodeError:
            return True

    def get_repository_files(self, repo_path):
        file_list = []
        for root, _, files in os.walk(repo_path):
            for file in files:
                file_path = Path(root) / file
                relative_path = os.path.relpath(file_path, repo_path)
                if not relative_path.startswith(".git"):
                    file_list.append(relative_path)
        return sorted(file_list)

    def get_branches(self, repo_url):
        try:
            temp_dir = tempfile.mkdtemp()
            repo = git.Repo.clone_from(repo_url, temp_dir, no_checkout=True)
            repo.remote().fetch()
            branches = []

            for ref in repo.remote().refs:
                if ref.name == "origin/HEAD":
                    continue
                branch_name = ref.name.split("/")[-1]
                if branch_name not in branches:
                    branches.append(branch_name)

            return sorted(branches) if branches else ["main", "master"]
        except git.GitCommandError as e:
            self.log(f"Error getting branches: {e!s}")
            return ["main", "master"]
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def update_build_config(self, build_config: dict, _field_value: str, field_name: str | None = None) -> dict:
        if not self.repository_url:
            build_config["branch"]["options"] = ["Enter repository URL first"]
            build_config["branch"]["value"] = "Enter repository URL first"
            build_config["selected_files"]["options"] = ["Select branch first"]
            build_config["selected_files"]["value"] = []
            return build_config

        if field_name in {"repository_url", "branch"}:
            branches = self.get_branches(self.repository_url)
            build_config["branch"]["options"] = branches
            if field_name == "repository_url":
                build_config["branch"]["value"] = branches[0] if branches else "main"

        if (
            self.branch
            and self.branch not in ["Enter repository URL first"]
            and field_name in {"repository_url", "branch", "selected_files"}
        ):
            try:
                temp_dir = tempfile.mkdtemp()
                _ = git.Repo.clone_from(self.repository_url, temp_dir, branch=self.branch, depth=1, single_branch=True)

                file_list = self.get_repository_files(temp_dir)
                if not file_list:
                    self.log("No files found in repository")
                    build_config["selected_files"]["options"] = ["No files found in branch"]
                    build_config["selected_files"]["value"] = []
                else:
                    self.log(f"Found {len(file_list)} files")
                    build_config["selected_files"]["options"] = file_list

            except git.exc.GitCommandError as e:
                error_msg = f"Git error: {e!s}"
                self.log(error_msg)
                build_config["selected_files"]["options"] = ["Error accessing branch"]
                build_config["selected_files"]["value"] = []
            except OSError as e:
                error_msg = f"Error listing files: {e!s}"
                self.log(error_msg)
                build_config["selected_files"]["options"] = ["Error listing files"]
                build_config["selected_files"]["value"] = []
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return build_config

    def get_files_content(self) -> list[Data]:
        if not self.repository_url:
            return [Data(data={"error": "Please enter a repository URL"})]
        if not self.branch or self.branch == "Enter repository URL first":
            return [Data(data={"error": "Please select a branch"})]
        if not self.selected_files:
            return [Data(data={"error": "Please select at least one file"})]

        try:
            temp_dir = tempfile.mkdtemp()
            try:
                _ = git.Repo.clone_from(self.repository_url, temp_dir, branch=self.branch, depth=1, single_branch=True)

                content_list = []
                for file_name in self.selected_files:
                    file_path = Path(temp_dir) / file_name
                    file_info = {"path": file_name, "size": file_path.stat().st_size if file_path.exists() else 0}

                    if not file_path.exists():
                        file_info["content"] = None
                        file_info["error"] = "File not found"
                    elif self.is_binary(file_path):
                        file_info["content"] = "[BINARY FILE]"
                        file_info["is_binary"] = True
                    else:
                        with file_path.open(encoding="utf-8", errors="replace") as f:
                            file_info["content"] = f.read()

                    content_list.append(Data(data=file_info))

                self.status = content_list
                return content_list
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except (git.exc.GitCommandError, OSError) as e:
            error_msg = f"Error getting files content: {e!s}"
            self.status = error_msg
            return [Data(data={"error": error_msg})]
