from urllib.parse import urlparse

from langflow.base.data import BaseFileComponent
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput
from langflow.schema import Data


class NvidiaIngestComponent(BaseFileComponent):
    display_name = "NVIDIA Retriever Extraction"
    description = "Multi-modal data extraction from documents using NVIDIA's NeMo API."
    documentation: str = "https://docs.nvidia.com/nemo/retriever/extraction/overview/"
    icon = "NVIDIA"
    beta = True

    try:
        from nv_ingest_client.util.file_processing.extract import EXTENSION_TO_DOCUMENT_TYPE

        VALID_EXTENSIONS = list(EXTENSION_TO_DOCUMENT_TYPE.keys())
    except ImportError:
        msg = (
            "NVIDIA Retriever Extraction (nv-ingest) dependencies missing. "
            "Please install them using your package manager. (e.g. uv pip install langflow[nv-ingest])"
        )
        VALID_EXTENSIONS = [msg]

    inputs = [
        *BaseFileComponent._base_inputs,
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="The URL of the NVIDIA NeMo Retriever Extraction API.",
        ),
        BoolInput(
            name="extract_text",
            display_name="Extract Text",
            info="Extract text from documents",
            value=True,
        ),
        BoolInput(
            name="extract_charts",
            display_name="Extract Charts",
            info="Extract text from charts",
            value=False,
        ),
        BoolInput(
            name="extract_tables",
            display_name="Extract Tables",
            info="Extract text from tables",
            value=True,
        ),
        DropdownInput(
            name="text_depth",
            display_name="Text Depth",
            info=(
                "Level at which text is extracted (applies before splitting). "
                "Support for 'block', 'line', 'span' varies by document type."
            ),
            options=["document", "page", "block", "line", "span"],
            value="document",  # Default value
            advanced=True,
        ),
        BoolInput(
            name="split_text",
            display_name="Split Text",
            info="Split text into smaller chunks",
            value=True,
        ),
        DropdownInput(
            name="split_by",
            display_name="Split By",
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
        *BaseFileComponent._base_outputs,
    ]

    def process_files(self, file_list: list[BaseFileComponent.BaseFile]) -> list[BaseFileComponent.BaseFile]:
        try:
            from nv_ingest_client.client import Ingestor
        except ImportError as e:
            msg = (
                "NVIDIA Retriever Extraction (nv-ingest) dependencies missing. "
                "Please install them using your package manager. (e.g. uv pip install langflow[nv-ingest])"
            )
            raise ImportError(msg) from e

        self.base_url: str | None = self.base_url.strip() if self.base_url else None

        if not file_list:
            err_msg = "No files to process."
            self.log(err_msg)
            raise ValueError(err_msg)

        file_paths = [str(file.path) for file in file_list]

        try:
            parsed_url = urlparse(self.base_url)
            if not parsed_url.hostname or not parsed_url.port:
                err_msg = "Invalid URL: Missing hostname or port."
                self.log(err_msg)
                raise ValueError(err_msg)
        except Exception as e:
            self.log(f"Error parsing URL: {e}")
            raise

        self.log(
            f"Creating Ingestor for host: {parsed_url.hostname!r}, port: {parsed_url.port!r}",
        )
        try:
            from nv_ingest_client.client import Ingestor

            ingestor = (
                Ingestor(message_client_hostname=parsed_url.hostname, message_client_port=parsed_url.port)
                .files(file_paths)
                .extract(
                    extract_text=self.extract_text,
                    extract_tables=self.extract_tables,
                    extract_charts=self.extract_charts,
                    extract_images=False,  # Currently not supported
                    text_depth=self.text_depth,
                )
            )
        except Exception as e:
            self.log(f"Error creating Ingestor: {e}")
            raise

        if self.split_text:
            ingestor = ingestor.split(
                split_by=self.split_by,
                split_length=self.split_length,
                split_overlap=self.split_overlap,
                max_character_length=self.max_character_length,
                sentence_window_size=self.sentence_window_size,
            )

        try:
            result = ingestor.ingest()
        except Exception as e:
            self.log(f"Error during ingestion: {e}")
            raise

        self.log(f"Results: {result}")

        data: list[Data | None] = []
        document_type_text = "text"
        document_type_structured = "structured"

        # Result is a list of segments as determined by the text_depth option (if "document" then only one segment)
        # each segment is a list of elements (text, structured, image)
        for segment in result:
            for element in segment:
                document_type = element.get("document_type")
                metadata = element.get("metadata", {})
                source_metadata = metadata.get("source_metadata", {})
                content_metadata = metadata.get("content_metadata", {})

                if document_type == document_type_text:
                    data.append(
                        Data(
                            text=metadata.get("content", ""),
                            file_path=source_metadata.get("source_name", ""),
                            document_type=document_type,
                            description=content_metadata.get("description", ""),
                        )
                    )
                # Both charts and tables are returned as "structured" document type,
                # with extracted text in "table_content"
                elif document_type == document_type_structured:
                    table_metadata = metadata.get("table_metadata", {})
                    data.append(
                        Data(
                            text=table_metadata.get("table_content", ""),
                            file_path=source_metadata.get("source_name", ""),
                            document_type=document_type,
                            description=content_metadata.get("description", ""),
                        )
                    )
                else:
                    # image is not yet supported; skip if encountered
                    self.log(f"Unsupported document type: {document_type}")

        self.status = data or "No data"

        # merge processed data with BaseFile objects
        return self.rollup_data(file_list, data)
