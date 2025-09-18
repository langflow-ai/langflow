from langchain_polaris_ai_datainsight import PolarisAIDataInsightLoader

from lfx.custom import Component
from lfx.io import FileInput, Output, SecretStrInput, StrInput
from lfx.log import logger
from lfx.schema.data import Data


class PolarisAIDataInsightComponent(Component):
    name = "polaris_ai_data_insight"
    display_name: str = "Polaris AI Data Insight"
    description: str = (
        "Polaris AI DataInsight is a document parser that extracts document"
        " elements (text, images, complex tables, charts, etc.) from various file formats"
        " into structured JSON, making them easy to integrate into RAG systems."
    )
    documentation: str = "https://datainsight.polarisoffice.com/documentation"
    trace_type: str = "documentloaders"
    icon: str = "PolarisOffice"

    inputs = [
        FileInput(
            name="file_path",
            display_name="File",
            info="Path to the file to process.",
            fileTypes=["docx", "pptx", "xlsx", "hwp", "hwpx"],
            required=True,
            temp_file=True,
        ),
        SecretStrInput(name="api_key", display_name="API key", required=True),
        StrInput(
            name="resources_dir",
            display_name="Directory For Resources",
            value="tmp/",
            info=(
                "Any images contained in the document as non-text objects will be "
                "stored in this directory as separate image files. If the directory does not exist, it will be created."
                ' Defaults to "tmp/".'
            ),
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="extract_document"),
    ]

    def extract_document(self) -> Data:
        if not self.file_path:
            logger.error("File path is required.")
            self.status = "File path is required."
        if not self.api_key:
            logger.error("API key is required.")
            self.status = "API key is required."
        if not self.resources_dir:
            logger.error("Resources directory is required.")
            self.status = "Resources directory is required."

        loader = PolarisAIDataInsightLoader(
            file_path=self.file_path, api_key=self.api_key, resources_dir=self.resources_dir, mode="single"
        )
        doc = loader.load()[0]

        self.status = doc
        return Data.from_document(doc)
