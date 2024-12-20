import asyncio
import re
import tempfile
from contextlib import asynccontextmanager
from fnmatch import fnmatch
from pathlib import Path

import anyio
from langchain_community.document_loaders.git import GitLoader

from langflow.custom import Component
from langflow.io import DropdownInput, MessageTextInput, Output
from langflow.schema import Data


class GitLoaderComponent(Component):
    display_name = "Git"
    description = (
        "Load and filter documents from a local or remote Git repository. "
        "Use a local repo path or clone from a remote URL."
    )
    trace_type = "tool"
    icon = "GitLoader"

    inputs = [
        DropdownInput(
            name="repo_source",
            display_name="Repository Source",
            options=["Local", "Remote"],
            required=True,
            info="Select whether to use a local repo path or clone from a remote URL.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="repo_path",
            display_name="Local Repository Path",
            required=False,
            info="The local path to the existing Git repository (used if 'Local' is selected).",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="clone_url",
            display_name="Clone URL",
            required=False,
            info="The URL of the Git repository to clone (used if 'Clone' is selected).",
            dynamic=True,
            show=False,
        ),
        MessageTextInput(
            name="branch",
            display_name="Branch",
            required=False,
            value="main",
            info="The branch to load files from. Defaults to 'main'.",
        ),
        MessageTextInput(
            name="file_filter",
            display_name="File Filter",
            required=False,
            advanced=True,
            info=(
                "Patterns to filter files. For example:\n"
                "Include only .py files: '*.py'\n"
                "Exclude .py files: '!*.py'\n"
                "Multiple patterns can be separated by commas."
            ),
        ),
        MessageTextInput(
            name="content_filter",
            display_name="Content Filter",
            required=False,
            advanced=True,
            info="A regex pattern to filter files based on their content.",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="load_documents"),
    ]

    @staticmethod
    async def is_binary(file_path: str | Path) -> bool:
        """Check if a file is binary by looking for null bytes."""
        path = anyio.Path(file_path)
        content = await path.read_bytes()
        return b"\x00" in content[:1024]

    @asynccontextmanager
    async def temp_clone_dir(self):
        """Context manager for handling temporary clone directory."""
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="langflow_clone_")
            yield temp_dir
        finally:
            if temp_dir:
                await anyio.Path(temp_dir).rmdir()

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        # Hide fields by default
        build_config["repo_path"]["show"] = False
        build_config["clone_url"]["show"] = False

        if field_name == "repo_source":
            if field_value == "Local":
                build_config["repo_path"]["show"] = True
                build_config["repo_path"]["required"] = True
                build_config["clone_url"]["required"] = False
            elif field_value == "Remote":
                build_config["clone_url"]["show"] = True
                build_config["clone_url"]["required"] = True
                build_config["repo_path"]["required"] = False

        return build_config

    async def build_gitloader(self) -> GitLoader:
        file_filter_patterns = getattr(self, "file_filter", None)
        content_filter_pattern = getattr(self, "content_filter", None)

        def is_binary(file_path: str | Path) -> bool:
            """Check if a file is binary by looking for null bytes."""
            try:
                with Path(file_path).open("rb") as file:
                    content = file.read(1024)
                    return b"\x00" in content
            except Exception:  # noqa: BLE001
                return True

        def combined_filter(file_path: str) -> bool:
            try:
                path = Path(file_path)
                if is_binary(file_path):
                    return False

                # Apply file pattern filters
                if file_filter_patterns:
                    patterns = [pattern.strip() for pattern in file_filter_patterns.split(",")]
                    path_str = str(path)

                    # Handle single exclusion pattern
                    if len(patterns) == 1 and patterns[0].startswith("!"):
                        return not fnmatch(path_str, patterns[0][1:])

                    # Handle multiple patterns
                    included = any(fnmatch(path_str, pattern) for pattern in patterns if not pattern.startswith("!"))
                    excluded = any(fnmatch(path_str, pattern[1:]) for pattern in patterns if pattern.startswith("!"))

                    # If no include patterns, treat as include all
                    if not any(not pattern.startswith("!") for pattern in patterns):
                        included = True

                    if not included or excluded:
                        return False

                # Apply content filter
                if content_filter_pattern:
                    try:
                        content_regex = re.compile(content_filter_pattern)
                        with Path(file_path).open() as file:
                            content = file.read()
                        if not content_regex.search(content):
                            return False
                    except (OSError, UnicodeDecodeError):
                        return False

            except Exception:  # noqa: BLE001
                return False
            return True

        repo_source = getattr(self, "repo_source", None)
        if repo_source == "Local":
            repo_path = self.repo_path
            clone_url = None
        else:
            # Clone source
            clone_url = self.clone_url
            async with self.temp_clone_dir() as temp_dir:
                repo_path = temp_dir

        return GitLoader(
            repo_path=repo_path,
            clone_url=clone_url if repo_source == "Remote" else None,
            branch=self.branch,
            file_filter=combined_filter,
        )

    async def load_documents(self) -> list[Data]:
        gitloader = await self.build_gitloader()
        data = [Data.from_document(doc) for doc in await asyncio.to_thread(gitloader.lazy_load)]
        self.status = data
        return data
