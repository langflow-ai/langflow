from langchain_unstructured import UnstructuredLoader

from langflow.custom import Component
from langflow.inputs import FileInput, SecretStrInput
from langflow.schema import Data
from langflow.template import Output


class UnstructuredComponent(Component):
    display_name = "Unstructured"
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
            display_name="Unstructured.io Serverless API Key",
            required=True,
            info="Unstructured API Key. Create at: https://app.unstructured.io/",
        ),
    ]

    outputs = [
        Output(name="data", display_name="Data", method="load_documents"),
    ]

    def build_unstructured(self) -> UnstructuredLoader:
        file_paths = [self.file]

        return UnstructuredLoader(
            file_paths,
            api_key=self.api_key,
            partition_via_api=True,
        )

    def load_documents(self) -> list[Data]:
        unstructured = self.build_unstructured()

        documents = unstructured.load()
        data = [Data.from_document(doc) for doc in documents]  # Using the from_document method of Data

        self.status = data

        return data
