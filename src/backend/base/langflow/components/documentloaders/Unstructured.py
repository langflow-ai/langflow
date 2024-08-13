from typing import List

from langflow.custom import Component
from langflow.io import StrInput, SecretStrInput, Output
from langflow.schema import Data
from langchain_unstructured import UnstructuredLoader


class UnstructuredComponent(Component):
    display_name = "Unstructured"
    description = "Unstructured data loader"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/providers/unstructured/"
    trace_type = "tool"
    icon = "Unstructured"
    name = "Unstructured"

    inputs = [
        StrInput(
            name="file_path",
            display_name="File Path",
            required=True,
            info="The path to the file with which you want to use Unstructured to parse",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=False,
            info="Unstructured API Key. Create at: https://unstructured.io/ - If not provided, open source library will be used",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="load_documents"),
    ]

    def build_unstructured(self) -> UnstructuredLoader:
        file_paths = [
            self.file_path
        ]

        loader = UnstructuredLoader(file_paths)

        return loader

    def load_documents(self) -> List[Data]:
        unstructured = self.build_unstructured()

        documents = unstructured.load()
        data = [Data.from_document(doc) for doc in documents]  # Using the from_document method of Data

        self.status = data

        return data
