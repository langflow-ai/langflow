import os

from typing import List

from langflow.custom import Component
from langflow.inputs import FileInput, SecretStrInput
from langflow.template import Output
from langflow.schema import Data

from langchain_community.document_loaders.unstructured import UnstructuredFileLoader


class UnstructuredComponent(Component):
    display_name = "Unstructured Loader"
    description = "Uses Unstructured.io to extract clean text from raw source documents. Supports: PDF, DOCX, TXT"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/providers/unstructured/"
    trace_type = "tool"
    icon = "Unstructured"
    name = "Unstructured"

    inputs = [
        FileInput(
            name="file",
            display_name="File",
            required=True,
            info="The path to the file with which you want to use Unstructured to parse. Supports: PDF, DOCX, TXT",
            file_types=["pdf", "docx", "txt"],  # TODO: Support all unstructured file types
        ),
        SecretStrInput(
            name="api_key",
            display_name="Unstructured.io API Key",
            required=False,
            info="Unstructured API Key. Create at: https://unstructured.io/ - If not provided, open source library will be used",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="load_documents"),
    ]

    def build_unstructured(self) -> UnstructuredFileLoader:
        os.environ["UNSTRUCTURED_API_KEY"] = self.api_key

        file_paths = [self.file]

        loader = UnstructuredFileLoader(file_paths)

        return loader

    def load_documents(self) -> List[Data]:
        unstructured = self.build_unstructured()

        documents = unstructured.load()
        data = [Data.from_document(doc) for doc in documents]  # Using the from_document method of Data

        self.status = data

        return data
