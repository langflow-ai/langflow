import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from nv_ingest_client.client import Ingestor
from nv_ingest_client.util.file_processing.extract import EXTENSION_TO_DOCUMENT_TYPE

from langflow.custom import Component
from langflow.io import BoolInput, FileInput, IntInput, MessageTextInput, Output, StrInput, DropdownInput
from langflow.schema import Data

logger = logging.getLogger(__name__)


class NVIDIAIngestComponent(Component):
    display_name = "NVIDIA Ingest"
    description = """NVIDIA Ingest (nv-ingest) efficiently processes, transforms, and stores large datasets for AI and ML integration."""
    documentation: str = "https://github.com/NVIDIA/nv-ingest/tree/main/docs"
    icon = "NVIDIA"
    name = "NVIDIAIngest"
    beta = True

    file_types = list(EXTENSION_TO_DOCUMENT_TYPE.keys())
    supported_file_types_info = f"Supported file types: {', '.join(file_types)}"

    inputs = [
        StrInput(
            name="base_url",
            display_name="NVIDIA Ingestion URL",
            info="The URL of the NVIDIA Ingestion API.",
        ),
        FileInput(
            name="path",
            display_name="Path",
            file_types=file_types,
            info=supported_file_types_info,
            required=True,
        ),
        BoolInput(
            name="extract_text",
            display_name="Extract text",
            info="Extract text from document",
            value=True,
        ),
        BoolInput(
            name="extract_charts",
            display_name="Extract charts",
            info="Extract text from charts",
            value=False,
        ),
        BoolInput(
            name="extract_tables",
            display_name="Extract tables",
            info="Extract text from tables",
            value=True,
        ),
        DropdownInput(
            name="text_depth",
            display_name="Text depth",
            info="Level at which text is extracted (applies before splitting). Support for 'block', 'line', 'span' varies by document type.",
            options=["document", "page", "block", "line", "span"],
            value="document",  # Default value
            advanced=True,
        ),
        BoolInput(
            name="split_text",
            display_name="Split text",
            info="Split text into smaller chunks",
            value=True,
        ),
        DropdownInput(
            name="split_by",
            display_name="Split by",
            info="How to split into chunks ('size' splits by number of characters)",
            options=["page", "sentence", "word", "size"],
            value="word",  # Default value
            advanced=True,
        ),
        IntInput(
            name="split_length",
            display_name="Split Length",
            info="The size of each chunk based on the 'split_by' method",
            value=200,
            advanced=True,
        ),
        IntInput(
            name="split_overlap",
            display_name="Split Overlap",
            info="Number of segments (as determined by the 'split_by' method) to overlap from previous chunk",
            value=20,
            advanced=True,
        ),
        IntInput(
            name="max_character_length",
            display_name="Max Character Length",
            info="Maximum number of characters in each chunk",
            value=1000,
            advanced=True,
        ),
        IntInput(
            name="sentence_window_size",
            display_name="Sentence Window Size",
            info="Number of sentences to include from previous and following chunk (when split_by='sentence')",
            value=0,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="load_file"),
    ]

    def load_file(self) -> Data:
        if not self.path:
            err_msg = "Upload a file to use this component."
            raise ValueError(err_msg)

        resolved_path = self.resolve_path(self.path)
        extension = Path(resolved_path).suffix[1:].lower()
        if extension not in self.file_types:
            err_msg = f"Unsupported file type: {extension}"
            raise ValueError(err_msg)

        parsed_url = urlparse(self.base_url)

        message = f"creating Ingestor for host: {parsed_url.hostname}, port: {parsed_url.port}"
        self.log(message, name="NVIDIAIngestComponent")

        ingestor = (
            Ingestor(message_client_hostname=parsed_url.hostname, message_client_port=parsed_url.port)
            .files(resolved_path)
            .extract(
                extract_text=self.extract_text,
                extract_tables=self.extract_tables,
                extract_charts=self.extract_charts,
                extract_images=False,
                text_depth=self.text_depth,
            )
        )

        if self.split_text:
            ingestor = ingestor.split(
                split_by=self.split_by,
                split_length=self.split_length,
                split_overlap=self.split_overlap,
                max_character_length=self.max_character_length,
                sentence_window_size=self.sentence_window_size,
            )

        result = ingestor.ingest()
        result_str = str(result)
        msg = f"results: {result_str}"
        self.log(msg, name="NVIDIAIngestComponent")

        data = []

        # Result is a list of segments as determined by the text_depth option (if "document" then only one segment)
        # each segment is a list of elements (text, structured, image)
        for segment in result:
            for element in segment:
                if element["document_type"] == "text":
                    data.append(
                        Data(
                            text=element["metadata"]["content"],
                            file_path=element["metadata"]["source_metadata"]["source_name"],
                            document_type=element["document_type"],
                            description=element["metadata"]["content_metadata"]["description"],
                        )
                    )
                # both charts and tables are returned as "structured" document type, with extracted text in "table_content"
                elif element["document_type"] == "structured":
                    data.append(
                        Data(
                            text=element["metadata"]["table_metadata"]["table_content"],
                            file_path=element["metadata"]["source_metadata"]["source_name"],
                            document_type=element["document_type"],
                            description=element["metadata"]["content_metadata"]["description"],
                        )
                    )

        self.status = data if data else "No data"
        return data or Data()
