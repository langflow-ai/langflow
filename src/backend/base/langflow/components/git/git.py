import re
from pathlib import Path

from langchain_community.document_loaders.git import GitLoader

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data


class GitLoaderComponent(Component):
    display_name = "GitLoader"
    description = "Load files from a Git repository"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/document_loaders/git/"
    trace_type = "tool"
    icon = "GitLoader"
    name = "GitLoader"

    inputs = [
        MessageTextInput(
            name="repo_path",
            display_name="Repository Path",
            required=False,
            info="The local path to the Git repository.",
        ),
        MessageTextInput(
            name="clone_url",
            display_name="Clone URL",
            required=False,
            info="The URL to clone the Git repository from.",
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
            info="A list of patterns to filter files. Example to include only .py files: '*.py'. "
            "Example to exclude .py files: '!*.py'. Multiple patterns can be separated by commas.",
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
    def is_binary(file_path: str) -> bool:
        """Check if a file is binary by looking for null bytes.

        This is necessary because when searches are performed using
        the content_filter, binary files need to be ignored.
        """
        with Path(file_path).open("rb") as file:
            return b"\x00" in file.read(1024)

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
            return all(f(path) for f in file_filters)

        return GitLoader(
            repo_path=self.repo_path,
            clone_url=self.clone_url,
            branch=self.branch,
            file_filter=combined_filter,
        )

    def load_documents(self) -> list[Data]:
        gitloader = self.build_gitloader()
        documents = list(gitloader.lazy_load())
        data = [Data.from_document(doc) for doc in documents]
        self.status = data
        return data
