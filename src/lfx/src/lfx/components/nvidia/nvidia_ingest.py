from urllib.parse import urlparse

from pypdf import PdfReader

from lfx.base.data.base_file import BaseFileComponent
from lfx.inputs.inputs import BoolInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput
from lfx.schema.data import Data


class NvidiaIngestComponent(BaseFileComponent):
    display_name = "NVIDIA Retriever Extraction"
    description = "Multi-modal data extraction from documents using NVIDIA's NeMo API."
    documentation: str = "https://docs.nvidia.com/nemo/retriever/extraction/overview/"
    icon = "NVIDIA"
    beta = True

    try:
        from nv_ingest_client.util.file_processing.extract import EXTENSION_TO_DOCUMENT_TYPE

        # Supported file extensions from https://github.com/NVIDIA/nv-ingest/blob/main/README.md
        VALID_EXTENSIONS = ["pdf", "docx", "pptx", "jpeg", "png", "svg", "tiff", "txt"]
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
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="NVIDIA API Key",
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
            value=False,
        ),
        BoolInput(
            name="extract_images",
            display_name="Extract Images",
            info="Extract images from document",
            value=True,
        ),
        BoolInput(
            name="extract_infographics",
            display_name="Extract Infographics",
            info="Extract infographics from document",
            value=False,
            advanced=True,
        ),
        DropdownInput(
            name="text_depth",
            display_name="Text Depth",
            info=(
                "Level at which text is extracted (applies before splitting). "
                "Support for 'block', 'line', 'span' varies by document type."
            ),
            options=["document", "page", "block", "line", "span"],
            value="page",  # Default value
            advanced=True,
        ),
        BoolInput(
            name="split_text",
            display_name="Split Text",
            info="Split text into smaller chunks",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk size",
            info="The number of tokens per chunk",
            value=500,
            advanced=True,
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk Overlap",
            info="Number of tokens to overlap from previous chunk",
            value=150,
            advanced=True,
        ),
        BoolInput(
            name="filter_images",
            display_name="Filter Images",
            info="Filter images (see advanced options for filtering criteria).",
            advanced=True,
            value=False,
        ),
        IntInput(
            name="min_image_size",
            display_name="Minimum Image Size Filter",
            info="Minimum image width/length in pixels",
            value=128,
            advanced=True,
        ),
        FloatInput(
            name="min_aspect_ratio",
            display_name="Minimum Aspect Ratio Filter",
            info="Minimum allowed aspect ratio (width / height). Images narrower than this will be filtered out.",
            value=0.2,
            advanced=True,
        ),
        FloatInput(
            name="max_aspect_ratio",
            display_name="Maximum Aspect Ratio Filter",
            info="Maximum allowed aspect ratio (width / height). Images taller than this will be filtered out.",
            value=5.0,
            advanced=True,
        ),
        BoolInput(
            name="dedup_images",
            display_name="Deduplicate Images",
            info="Filter duplicated images.",
            advanced=True,
            value=True,
        ),
        BoolInput(
            name="caption_images",
            display_name="Caption Images",
            info="Generate captions for images using the NVIDIA captioning model.",
            advanced=True,
            value=True,
        ),
        BoolInput(
            name="high_resolution",
            display_name="High Resolution (PDF only)",
            info=("Process pdf in high-resolution mode for better quality extraction from scanned pdf."),
            advanced=True,
            value=False,
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

        if not file_list:
            err_msg = "No files to process."
            self.log(err_msg)
            raise ValueError(err_msg)

        # Check if all files are PDFs when high resolution mode is enabled
        if self.high_resolution:
            for file in file_list:
                try:
                    with file.path.open("rb") as f:
                        PdfReader(f)
                except Exception as exc:
                    error_msg = "High-resolution mode only supports valid PDF files."
                    self.log(error_msg)
                    raise ValueError(error_msg) from exc

        file_paths = [str(file.path) for file in file_list]

        self.base_url: str | None = self.base_url.strip() if self.base_url else None
        if self.base_url:
            try:
                urlparse(self.base_url)
            except Exception as e:
                error_msg = f"Invalid Base URL format: {e}"
                self.log(error_msg)
                raise ValueError(error_msg) from e
        else:
            base_url_error = "Base URL is required"
            raise ValueError(base_url_error)

        self.log(
            f"Creating Ingestor for Base URL: {self.base_url!r}",
        )

        try:
            ingestor = (
                Ingestor(
                    message_client_kwargs={
                        "base_url": self.base_url,
                        "headers": {"Authorization": f"Bearer {self.api_key}"},
                        "max_retries": 3,
                        "timeout": 60,
                    }
                )
                .files(file_paths)
                .extract(
                    extract_text=self.extract_text,
                    extract_tables=self.extract_tables,
                    extract_charts=self.extract_charts,
                    extract_images=self.extract_images,
                    extract_infographics=self.extract_infographics,
                    text_depth=self.text_depth,
                    **({"extract_method": "nemoretriever_parse"} if self.high_resolution else {}),
                )
            )

            if self.extract_images:
                if self.dedup_images:
                    ingestor = ingestor.dedup(content_type="image", filter=True)

                if self.filter_images:
                    ingestor = ingestor.filter(
                        content_type="image",
                        min_size=self.min_image_size,
                        min_aspect_ratio=self.min_aspect_ratio,
                        max_aspect_ratio=self.max_aspect_ratio,
                        filter=True,
                    )

                if self.caption_images:
                    ingestor = ingestor.caption()

            if self.extract_text and self.split_text:
                ingestor = ingestor.split(
                    tokenizer="intfloat/e5-large-unsupervised",
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    params={"split_source_types": ["PDF"]},
                )

            result = ingestor.ingest()
        except Exception as e:
            ingest_error = f"Error during ingestion: {e}"
            self.log(ingest_error)
            raise

        self.log(f"Results: {result}")

        data: list[Data | None] = []
        document_type_text = "text"
        document_type_structured = "structured"

        # Result is a list of segments as determined by the text_depth option (if "document" then only one segment)
        # each segment is a list of elements (text, structured, image)
        for segment in result:
            if segment:
                for element in segment:
                    document_type = element.get("document_type")
                    metadata = element.get("metadata", {})
                    source_metadata = metadata.get("source_metadata", {})

                    if document_type == document_type_text:
                        data.append(
                            Data(
                                text=metadata.get("content", ""),
                                file_path=source_metadata.get("source_name", ""),
                                document_type=document_type,
                                metadata=metadata,
                            )
                        )
                    # Both charts and tables are returned as "structured" document type,
                    # with extracted text in "table_content"
                    elif document_type == document_type_structured:
                        table_metadata = metadata.get("table_metadata", {})

                        # reformat chart/table images as binary data
                        if "content" in metadata:
                            metadata["content"] = {"$binary": metadata["content"]}

                        data.append(
                            Data(
                                text=table_metadata.get("table_content", ""),
                                file_path=source_metadata.get("source_name", ""),
                                document_type=document_type,
                                metadata=metadata,
                            )
                        )
                    elif document_type == "image":
                        image_metadata = metadata.get("image_metadata", {})

                        # reformat images as binary data
                        if "content" in metadata:
                            metadata["content"] = {"$binary": metadata["content"]}

                        data.append(
                            Data(
                                text=image_metadata.get("caption", "No caption available"),
                                file_path=source_metadata.get("source_name", ""),
                                document_type=document_type,
                                metadata=metadata,
                            )
                        )
                    else:
                        self.log(f"Unsupported document type {document_type}")
        self.status = data or "No data"

        # merge processed data with BaseFile objects
        return self.rollup_data(file_list, data)
