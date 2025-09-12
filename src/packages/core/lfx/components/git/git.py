import re
import tempfile
from contextlib import asynccontextmanager
from fnmatch import fnmatch
from pathlib import Path

import anyio
from langchain_community.document_loaders.git import GitLoader

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data


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
    def is_binary(file_path: str | Path) -> bool:
        """Check if a file is binary by looking for null bytes."""
        try:
            with Path(file_path).open("rb") as file:
                content = file.read(1024)
                return b"\x00" in content
        except Exception:  # noqa: BLE001
            return True

    @staticmethod
    def check_file_patterns(file_path: str | Path, patterns: str) -> bool:
        """Check if a file matches the given patterns.

        Args:
            file_path: Path to the file to check
            patterns: Comma-separated list of glob patterns

        Returns:
            bool: True if file should be included, False if excluded
        """
        # Handle empty or whitespace-only patterns
        if not patterns or patterns.isspace():
            return True

        path_str = str(file_path)
        file_name = Path(path_str).name
        pattern_list: list[str] = [pattern.strip() for pattern in patterns.split(",") if pattern.strip()]

        # If no valid patterns after stripping, treat as include all
        if not pattern_list:
            return True

        # Process exclusion patterns first
        for pattern in pattern_list:
            if pattern.startswith("!"):
                # For exclusions, match against both full path and filename
                exclude_pattern = pattern[1:]
                if fnmatch(path_str, exclude_pattern) or fnmatch(file_name, exclude_pattern):
                    return False

        # Then check inclusion patterns
        include_patterns = [p for p in pattern_list if not p.startswith("!")]
        # If no include patterns, treat as include all
        if not include_patterns:
            return True

        # For inclusions, match against both full path and filename
        return any(fnmatch(path_str, pattern) or fnmatch(file_name, pattern) for pattern in include_patterns)

    @staticmethod
    def check_content_pattern(file_path: str | Path, pattern: str) -> bool:
        """Check if file content matches the given regex pattern.

        Args:
            file_path: Path to the file to check
            pattern: Regex pattern to match against content

        Returns:
            bool: True if content matches, False otherwise
        """
        try:
            # Check if file is binary
            with Path(file_path).open("rb") as file:
                content = file.read(1024)
                if b"\x00" in content:
                    return False

            # Try to compile the regex pattern first
            try:
                # Use the MULTILINE flag to better handle text content
                content_regex = re.compile(pattern, re.MULTILINE)
                # Test the pattern with a simple string to catch syntax errors
                test_str = "test\nstring"
                if not content_regex.search(test_str):
                    # Pattern is valid but doesn't match test string
                    pass
            except (re.error, TypeError, ValueError):
                return False

            # If not binary and regex is valid, check content
            with Path(file_path).open(encoding="utf-8") as file:
                file_content = file.read()
            return bool(content_regex.search(file_content))
        except (OSError, UnicodeDecodeError):
            return False

    def build_combined_filter(self, file_filter_patterns: str | None = None, content_filter_pattern: str | None = None):
        """Build a combined filter function from file and content patterns.

        Args:
            file_filter_patterns: Comma-separated glob patterns
            content_filter_pattern: Regex pattern for content

        Returns:
            callable: Filter function that takes a file path and returns bool
        """

        def combined_filter(file_path: str) -> bool:
            try:
                path = Path(file_path)

                # Check if file exists and is readable
                if not path.exists():
                    return False

                # Check if file is binary
                if self.is_binary(path):
                    return False

                # Apply file pattern filters
                if file_filter_patterns and not self.check_file_patterns(path, file_filter_patterns):
                    return False

                # Apply content filter
                return not (content_filter_pattern and not self.check_content_pattern(path, content_filter_pattern))
            except Exception:  # noqa: BLE001
                return False

        return combined_filter

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

        combined_filter = self.build_combined_filter(file_filter_patterns, content_filter_pattern)

        repo_source = getattr(self, "repo_source", None)
        if repo_source == "Local":
            repo_path = self.repo_path
            clone_url = None
        else:
            # Clone source
            clone_url = self.clone_url
            async with self.temp_clone_dir() as temp_dir:
                repo_path = temp_dir

        # Only pass branch if it's explicitly set
        branch = getattr(self, "branch", None)
        if not branch:
            branch = None

        return GitLoader(
            repo_path=repo_path,
            clone_url=clone_url if repo_source == "Remote" else None,
            branch=branch,
            file_filter=combined_filter,
        )

    async def load_documents(self) -> list[Data]:
        gitloader = await self.build_gitloader()
        data = [Data.from_document(doc) async for doc in gitloader.alazy_load()]
        self.status = data
        return data
