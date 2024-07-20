from typing import List

from langchain_community.document_loaders.git import GitLoader
from langflow.custom import Component
from langflow.io import StrInput, Output
from langflow.schema import Data


class GitLoaderComponent(Component):
    display_name = "GitLoader"
    description = "Load files from a Git repository"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/document_loaders/git/"
    trace_type = "tool"
    icon = "GitLoader"
    name = "GitLoader"

    inputs = [
        StrInput(
            name="repo_path",
            display_name="Repository Path",
            required=True,
            info="The local path to the Git repository.",
        ),
        StrInput(
            name="clone_url",
            display_name="Clone URL",
            required=False,
            info="The URL to clone the Git repository from.",
        ),
        StrInput(
            name="branch",
            display_name="Branch",
            required=False,
            value="main",
            info="The branch to load files from. Defaults to 'main'.",
        ),
        StrInput(
            name="file_filter",
            display_name="File Filter",
            required=False,
            advanced=True,
            info="A function that takes a file path and returns a boolean indicating whether to load the file. "
            "Example to include only .py files: lambda file_path: file_path.endswith('.py'). "
            "Example to exclude .py files: lambda file_path: not file_path.endswith('.py').",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="load_documents"),
    ]

    def build_gitloader(self) -> GitLoader:
        file_filter = None
        if self.file_filter:
            file_filter = eval(self.file_filter)

        loader = GitLoader(
            repo_path=self.repo_path,
            clone_url=self.clone_url,
            branch=self.branch,
            file_filter=file_filter,
        )
        return loader

    def load_documents(self) -> List[Data]:
        gitloader = self.build_gitloader()
        documents = gitloader.lazy_load()
        data = [Data.from_document(doc) for doc in documents]
        self.status = data
        return data
