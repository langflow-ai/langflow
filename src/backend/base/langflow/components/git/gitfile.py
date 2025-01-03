import asyncio
import os
import shutil
import tempfile
from contextlib import asynccontextmanager

import anyio
import git

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, MultiselectInput, Output
from langflow.schema import Data


class GitFileError(Exception):
    """Base exception for GitFile component errors."""
    pass


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

    @asynccontextmanager
    async def temp_git_repo(self):
        """Async context manager for temporary git repository cloning."""
        temp_dir = tempfile.mkdtemp()
        try:
            yield temp_dir
        finally:
            await asyncio.get_event_loop().run_in_executor(None, lambda: shutil.rmtree(temp_dir, ignore_errors=True))

    async def is_binary(self, file_path: anyio.Path) -> bool:
        try:
            async with await file_path.open() as check_file:
                await check_file.read()
                return False
        except UnicodeDecodeError:
            return True

    async def get_repository_files(self, repo_path: str) -> list[str]:
        file_list = []
        path = anyio.Path(repo_path)  # Convert str to anyio.Path explicitly
        async for entry in path.rglob("*"):
            if await entry.is_file():
                relative_path = os.path.relpath(str(entry), str(path))
                if not relative_path.startswith(".git"):
                    file_list.append(relative_path)
        return sorted(file_list)

    async def get_branches(self, repo_url: str) -> list[str]:
        try:
            async with self.temp_git_repo() as temp_dir:
                repo = await asyncio.to_thread(
                    git.Repo.clone_from,
                    repo_url,
                    temp_dir,
                    no_checkout=True
                )
                await asyncio.to_thread(repo.remote().fetch)
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

    async def update_build_config(self, build_config: dict, field_value: str, field_name: Optional[str] = None) -> dict:
        """Update component build configuration."""
        if not self.repository_url:
            build_config["branch"]["options"] = ["Enter repository URL first"]
            build_config["branch"]["value"] = "Enter repository URL first"
            build_config["selected_files"]["options"] = ["Select branch first"]
            build_config["selected_files"]["value"] = []
            return build_config

        if field_name in {"repository_url", "branch"}:
            branches = await self.get_branches(self.repository_url)
            build_config["branch"]["options"] = branches
            if field_name == "repository_url":
                build_config["branch"]["value"] = branches[0] if branches else "main"

        if (
            self.branch
            and self.branch not in ["Enter repository URL first"]
            and field_name in {"repository_url", "branch", "selected_files"}
        ):
            try:
                async with self.temp_git_repo() as temp_dir:
                    await asyncio.to_thread(
                        git.Repo.clone_from,
                        self.repository_url,
                        temp_dir,
                        branch=self.branch,
                        depth=1,
                        single_branch=True
                    )

                    file_list = await self.get_repository_files(temp_dir)
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

        return build_config

    async def get_files_content(self) -> list[Data]:
        if not self.repository_url:
            return [Data(data={"error": "Please enter a repository URL"})]
        if not self.branch or self.branch == "Enter repository URL first":
            return [Data(data={"error": "Please select a branch"})]
        if not self.selected_files:
            return [Data(data={"error": "Please select at least one file"})]

        try:
            async with self.temp_git_repo() as temp_dir:
                await asyncio.to_thread(
                    git.Repo.clone_from,
                    self.repository_url,
                    temp_dir,
                    branch=self.branch,
                    depth=1,
                    single_branch=True
                )

                content_list = []
                for file_name in self.selected_files:
                    file_path = anyio.Path(temp_dir) / file_name
                    stats = await file_path.stat()
                    file_info = {"path": file_name, "size": stats.st_size if await file_path.exists() else 0}

                    if not await file_path.exists():
                        file_info["content"] = None
                        file_info["error"] = "File not found"
                    elif await self.is_binary(file_path):
                        file_info["content"] = "[BINARY FILE]"
                        file_info["is_binary"] = True
                    else:
                        async with await file_path.open(encoding="utf-8", errors="replace") as f:
                            file_info["content"] = await f.read()

                    content_list.append(Data(data=file_info))

                self.status = content_list
                return content_list

        except (git.exc.GitCommandError, OSError) as e:
            error_msg = f"Error getting files content: {e!s}"
            self.status = error_msg
            raise GitFileError(error_msg) from e