import re
import shutil
import tempfile
from pathlib import Path

from langchain_community.document_loaders.git import GitLoader

from langflow.custom import Component
from langflow.io import (
    DropdownInput,
    MessageTextInput,
    Output,
)
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

    _temp_clone_path: str | None = None

    @staticmethod
    def is_binary(file_path: str) -> bool:
        """Check if a file is binary by looking for null bytes."""
        with Path(file_path).open("rb") as file:
            return b"\x00" in file.read(1024)

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

    def build_gitloader(self) -> GitLoader:
        file_filter_patterns = getattr(self, "file_filter", None)
        content_filter_pattern = getattr(self, "content_filter", None)

        file_filters = []
        if file_filter_patterns:
            patterns = [pattern.strip() for pattern in file_filter_patterns.split(",")]

            def file_filter(file_path: Path) -> bool:
                if len(patterns) == 1 and patterns[0].startswith("!"):
                    return not file_path.match(patterns[0][1:])
                included = any(file_path.match(pattern) for pattern in patterns if not pattern.startswith("!"))
                excluded = any(file_path.match(pattern[1:]) for pattern in patterns if pattern.startswith("!"))
                return included and not excluded

            file_filters.append(file_filter)

        if content_filter_pattern:
            content_regex = re.compile(content_filter_pattern)

            def content_filter(file_path: Path) -> bool:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                return bool(content_regex.search(content))

            file_filters.append(content_filter)

        def combined_filter(file_path: str) -> bool:
            path = Path(file_path)
            if self.is_binary(file_path):
                return False
            return all(f(path) for f in file_filters) if file_filters else True

        repo_source = getattr(self, "repo_source", None)
        if repo_source == "Local":
            repo_path = self.repo_path
            clone_url = None
        else:
            # Clone source
            clone_url = self.clone_url
            # Generate a temporary directory for cloning
            self._temp_clone_path = tempfile.mkdtemp(prefix="langflow_clone_")
            repo_path = self._temp_clone_path

        return GitLoader(
            repo_path=repo_path,
            clone_url=clone_url if repo_source == "Remote" else None,
            branch=self.branch,
            file_filter=combined_filter,
        )

    def load_documents(self) -> list[Data]:
        gitloader = self.build_gitloader()
        documents = list(gitloader.lazy_load())
        data = [Data.from_document(doc) for doc in documents]
        self.status = data

        # Cleanup after loading if cloned
        repo_source = getattr(self, "repo_source", None)
        if repo_source == "Remote" and self._temp_clone_path:
            shutil.rmtree(self._temp_clone_path, ignore_errors=True)
            self._temp_clone_path = None

        return data
