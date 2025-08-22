"""Enhanced file component v2 with mypy and ruff compliance."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import TYPE_CHECKING, Any

from langflow.base.data.base_file import BaseFileComponent
from langflow.base.data.utils import TEXT_FILE_TYPES, parallel_load_data, parse_text_file_to_data
from langflow.io import (
    BoolInput,
    DropdownInput,
    FileInput,
    IntInput,
    MessageTextInput,
    Output,
    StrInput,
)
from langflow.schema.data import Data
from langflow.schema.message import Message

if TYPE_CHECKING:
    from langflow.schema import DataFrame


class MockConversionStatus(Enum):
    """Mock ConversionStatus for fallback compatibility."""

    SUCCESS = "success"
    FAILURE = "failure"


class MockInputFormat(Enum):
    """Mock InputFormat for fallback compatibility."""

    PDF = "pdf"
    IMAGE = "image"


class MockImageRefMode(Enum):
    """Mock ImageRefMode for fallback compatibility."""

    PLACEHOLDER = "placeholder"
    EMBEDDED = "embedded"


class DoclingImports:
    """Container for docling imports with type information."""

    def __init__(
        self,
        conversion_status: type[Enum],
        input_format: type[Enum],
        document_converter: type,
        image_ref_mode: type[Enum],
        strategy: str,
    ) -> None:
        self.conversion_status = conversion_status
        self.input_format = input_format
        self.document_converter = document_converter
        self.image_ref_mode = image_ref_mode
        self.strategy = strategy


class FileComponent(BaseFileComponent):
    """Enhanced file component v2 that combines standard file loading with optional Docling processing and export.

    This component supports all features of the standard File component, plus an advanced mode
    that enables Docling document processing and export to various formats (Markdown, HTML, etc.).
    """

    display_name = "File"
    description = "Loads content from files with optional advanced document processing and export using Docling."
    documentation: str = "https://docs.langflow.org/components-data#file"
    icon = "file-text"
    name = "File"

    # Docling supported formats from original component
    VALID_EXTENSIONS = [
        "adoc",
        "asciidoc",
        "asc",
        "bmp",
        "csv",
        "dotx",
        "dotm",
        "docm",
        "docx",
        "htm",
        "html",
        "jpeg",
        "json",
        "md",
        "pdf",
        "png",
        "potx",
        "ppsx",
        "pptm",
        "potm",
        "ppsm",
        "pptx",
        "tiff",
        "txt",
        "xls",
        "xlsx",
        "xhtml",
        "xml",
        "webp",
        *TEXT_FILE_TYPES,
    ]

    # Fixed export settings
    EXPORT_FORMAT = "Markdown"
    IMAGE_MODE = "placeholder"

    _base_inputs = deepcopy(BaseFileComponent._base_inputs)

    for input_item in _base_inputs:
        if isinstance(input_item, FileInput) and input_item.name == "path":
            input_item.real_time_refresh = True
            break

    inputs = [
        *_base_inputs,
        BoolInput(
            name="advanced_mode",
            display_name="Advanced Parser",
            value=False,
            real_time_refresh=True,
            info=(
                "Enable advanced document processing and export with Docling for PDFs, images, and office documents. "
                "Available only for single file processing."
            ),
            show=False,
        ),
        DropdownInput(
            name="pipeline",
            display_name="Pipeline",
            info="Docling pipeline to use",
            options=["standard", "vlm"],
            value="standard",
            advanced=True,
        ),
        DropdownInput(
            name="ocr_engine",
            display_name="OCR Engine",
            info="OCR engine to use. Only available when pipeline is set to 'standard'.",
            options=["", "easyocr"],
            value="",
            show=False,
            advanced=True,
        ),
        StrInput(
            name="md_image_placeholder",
            display_name="Image placeholder",
            info="Specify the image placeholder for markdown exports.",
            value="<!-- image -->",
            advanced=True,
            show=False,
        ),
        StrInput(
            name="md_page_break_placeholder",
            display_name="Page break placeholder",
            info="Add this placeholder between pages in the markdown output.",
            value="",
            advanced=True,
            show=False,
        ),
        MessageTextInput(
            name="doc_key",
            display_name="Doc Key",
            info="The key to use for the DoclingDocument column.",
            value="doc",
            advanced=True,
            show=False,
        ),
        BoolInput(
            name="use_multithreading",
            display_name="[Deprecated] Use Multithreading",
            advanced=True,
            value=True,
            info="Set 'Processing Concurrency' greater than 1 to enable multithreading.",
        ),
        IntInput(
            name="concurrency_multithreading",
            display_name="Processing Concurrency",
            advanced=True,
            info="When multiple files are being processed, the number of files to process concurrently.",
            value=1,
        ),
        BoolInput(
            name="markdown",
            display_name="Markdown Export",
            info="Export processed documents to Markdown format. Only available when advanced mode is enabled.",
            value=False,
            show=False,
        ),
    ]

    outputs = [
        Output(display_name="Raw Content", name="message", method="load_files_message"),
    ]

    def _path_value(self, template) -> list[str]:
        # Get current path value
        return template.get("path", {}).get("file_path", [])

    def update_build_config(
        self,
        build_config: dict[str, Any],
        field_value: Any,
        field_name: str | None = None,
    ) -> dict[str, Any]:
        """Update build configuration to show/hide fields based on file count and advanced_mode."""
        if field_name == "path":
            # Get current path value
            path_value = self._path_value(build_config)
            file_path = path_value[0] if len(path_value) > 0 else ""

            # Show/hide Advanced Parser based on file count (only for single files)
            file_count = len(field_value) if field_value else 0
            if file_count == 1 and not file_path.endswith((".csv", ".xlsx", ".parquet")):
                build_config["advanced_mode"]["show"] = True
            else:
                build_config["advanced_mode"]["show"] = False
                build_config["advanced_mode"]["value"] = False  # Reset to False when hidden

                # Hide all advanced fields when Advanced Parser is not available
                advanced_fields = [
                    "pipeline",
                    "ocr_engine",
                    "doc_key",
                    "md_image_placeholder",
                    "md_page_break_placeholder",
                ]
                for field in advanced_fields:
                    if field in build_config:
                        build_config[field]["show"] = False

        elif field_name == "advanced_mode":
            # Show/hide advanced fields based on advanced_mode (only if single file)
            advanced_fields = [
                "pipeline",
                "ocr_engine",
                "doc_key",
                "md_image_placeholder",
                "md_page_break_placeholder",
            ]

            for field in advanced_fields:
                if field in build_config:
                    build_config[field]["show"] = field_value

        return build_config

    def update_outputs(self, frontend_node: dict[str, Any], field_name: str, field_value: Any) -> dict[str, Any]:  # noqa: ARG002
        """Dynamically show outputs based on the number of files and their types."""
        if field_name not in ["path", "advanced_mode"]:
            return frontend_node

        # Add outputs based on the number of files in the path
        template = frontend_node.get("template", {})
        path_value = self._path_value(template)
        if len(path_value) == 0:
            return frontend_node

        # Clear existing outputs
        frontend_node["outputs"] = []

        if len(path_value) == 1:
            # We need to check if the file is structured content
            file_path = path_value[0] if field_name == "path" else frontend_node["template"]["path"]["file_path"][0]
            if file_path.endswith((".csv", ".xlsx", ".parquet")):
                frontend_node["outputs"].append(
                    Output(display_name="Structured Content", name="dataframe", method="load_files_structured"),
                )
            elif file_path.endswith(".json"):
                frontend_node["outputs"].append(
                    Output(display_name="Structured Content", name="json", method="load_files_json"),
                )

            # Add outputs based on advanced mode
            advanced_mode = frontend_node.get("template", {}).get("advanced_mode", {}).get("value", False)

            if advanced_mode:
                # Advanced mode: Structured Output, Markdown, and File Path
                frontend_node["outputs"].append(
                    Output(display_name="Structured Output", name="advanced", method="load_files_advanced"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="Markdown", name="markdown", method="load_files_markdown"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path"),
                )
            else:
                # Normal mode: Raw Content and File Path
                frontend_node["outputs"].append(
                    Output(display_name="Raw Content", name="message", method="load_files_message"),
                )
                frontend_node["outputs"].append(
                    Output(display_name="File Path", name="path", method="load_files_path"),
                )
        else:
            # For multiple files, we show the files output (DataFrame format)
            # Advanced Parser is not available for multiple files
            frontend_node["outputs"].append(
                Output(display_name="Files", name="dataframe", method="load_files"),
            )

        return frontend_node

    def _try_import_docling(self) -> DoclingImports | None:
        """Try different import strategies for docling components."""
        # Try strategy 1: Latest docling structure
        try:
            from docling.datamodel.base_models import ConversionStatus, InputFormat  # type: ignore[import-untyped]
            from docling.document_converter import DocumentConverter  # type: ignore[import-untyped]
            from docling_core.types.doc import ImageRefMode  # type: ignore[import-untyped]

            self.log("Using latest docling import structure")
            return DoclingImports(
                conversion_status=ConversionStatus,
                input_format=InputFormat,
                document_converter=DocumentConverter,
                image_ref_mode=ImageRefMode,
                strategy="latest",
            )
        except ImportError as e:
            self.log(f"Latest docling structure failed: {e}")

        # Try strategy 2: Alternative import paths
        try:
            from docling.document_converter import DocumentConverter  # type: ignore[import-untyped]
            from docling_core.types.doc import ImageRefMode  # type: ignore[import-untyped]

            # Try to get ConversionStatus from different locations
            conversion_status: type[Enum] = MockConversionStatus
            input_format: type[Enum] = MockInputFormat

            try:
                from docling_core.types import ConversionStatus, InputFormat  # type: ignore[import-untyped]

                conversion_status = ConversionStatus
                input_format = InputFormat
            except ImportError:
                try:
                    from docling.datamodel import ConversionStatus, InputFormat  # type: ignore[import-untyped]

                    conversion_status = ConversionStatus
                    input_format = InputFormat
                except ImportError:
                    # Use mock enums if we can't find them
                    pass

            self.log("Using alternative docling import structure")
            return DoclingImports(
                conversion_status=conversion_status,
                input_format=input_format,
                document_converter=DocumentConverter,
                image_ref_mode=ImageRefMode,
                strategy="alternative",
            )
        except ImportError as e:
            self.log(f"Alternative docling structure failed: {e}")

        # Try strategy 3: Basic converter only
        try:
            from docling.document_converter import DocumentConverter  # type: ignore[import-untyped]

            self.log("Using basic docling import structure with mocks")
            return DoclingImports(
                conversion_status=MockConversionStatus,
                input_format=MockInputFormat,
                document_converter=DocumentConverter,
                image_ref_mode=MockImageRefMode,
                strategy="basic",
            )
        except ImportError as e:
            self.log(f"Basic docling structure failed: {e}")

        # Strategy 4: Complete fallback - return None to indicate failure
        return None

    def _create_advanced_converter(self, docling_imports: DoclingImports) -> Any:
        """Create advanced converter with pipeline options if available."""
        try:
            from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore[import-untyped]
            from docling.document_converter import PdfFormatOption  # type: ignore[import-untyped]

            document_converter = docling_imports.document_converter
            input_format = docling_imports.input_format

            # Create basic pipeline options
            pipeline_options = PdfPipelineOptions()

            # Configure OCR if specified and available
            if self.ocr_engine:
                try:
                    from docling.models.factories import get_ocr_factory  # type: ignore[import-untyped]

                    pipeline_options.do_ocr = True
                    ocr_factory = get_ocr_factory(allow_external_plugins=False)
                    ocr_options = ocr_factory.create_options(kind=self.ocr_engine)
                    pipeline_options.ocr_options = ocr_options
                    self.log(f"Configured OCR with engine: {self.ocr_engine}")
                except Exception as e:  # noqa: BLE001
                    self.log(f"Could not configure OCR: {e}, proceeding without OCR")
                    pipeline_options.do_ocr = False

            # Create format options
            pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)
            format_options = {}
            if hasattr(input_format, "PDF"):
                format_options[input_format.PDF] = pdf_format_option
            if hasattr(input_format, "IMAGE"):
                format_options[input_format.IMAGE] = pdf_format_option

            return document_converter(format_options=format_options)

        except Exception as e:  # noqa: BLE001
            self.log(f"Could not create advanced converter: {e}, using basic converter")
            return docling_imports.document_converter()

    def _is_docling_compatible(self, file_path: str) -> bool:
        """Check if file is compatible with Docling processing."""
        # All VALID_EXTENSIONS are Docling compatible (except for TEXT_FILE_TYPES which may overlap)
        docling_extensions = [
            ".adoc",
            ".asciidoc",
            ".asc",
            ".bmp",
            ".csv",
            ".dotx",
            ".dotm",
            ".docm",
            ".docx",
            ".htm",
            ".html",
            ".jpeg",
            ".json",
            ".md",
            ".pdf",
            ".png",
            ".potx",
            ".ppsx",
            ".pptm",
            ".potm",
            ".ppsm",
            ".pptx",
            ".tiff",
            ".txt",
            ".xls",
            ".xlsx",
            ".xhtml",
            ".xml",
            ".webp",
        ]
        return any(file_path.lower().endswith(ext) for ext in docling_extensions)

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Process files using standard parsing or Docling based on advanced_mode and file type."""

        def process_file_standard(file_path: str, *, silent_errors: bool = False) -> Data | None:
            """Process a single file using standard text parsing."""
            try:
                return parse_text_file_to_data(file_path, silent_errors=silent_errors)
            except FileNotFoundError as e:
                msg = f"File not found: {file_path}. Error: {e}"
                self.log(msg)
                if not silent_errors:
                    raise
                return None
            except Exception as e:
                msg = f"Unexpected error processing {file_path}: {e}"
                self.log(msg)
                if not silent_errors:
                    raise
                return None

        def process_file_docling(file_path: str, *, silent_errors: bool = False) -> Data | None:
            """Process a single file using Docling if compatible, otherwise standard processing."""
            # Try Docling first if file is compatible and advanced mode is enabled
            try:
                return self._process_with_docling_and_export(file_path)
            except Exception as e:  # noqa: BLE001
                self.log(f"Docling processing failed for {file_path}: {e}, falling back to standard processing")
                if not silent_errors:
                    # Return error data instead of raising
                    return Data(data={"error": f"Docling processing failed: {e}", "file_path": file_path})

            return None

        if not file_list:
            msg = "No files to process."
            raise ValueError(msg)

        file_path = str(file_list[0].path)
        if self.advanced_mode and self._is_docling_compatible(file_path):
            processed_data = process_file_docling(file_path)
            if not processed_data:
                msg = f"Failed to process file with Docling: {file_path}"
                raise ValueError(msg)

            # Serialize processed data to match Data structure
            serialized_data = processed_data.serialize_model()

            # Now, if doc is nested, we need to unravel it
            clean_data: list[Data | None] = [processed_data]

            # This is where we've manually processed the data
            try:
                if "exported_content" not in serialized_data:
                    clean_data = [
                        Data(
                            data={
                                "file_path": file_path,
                                **(
                                    item["element"]
                                    if "element" in item
                                    else {k: v for k, v in item.items() if k != "file_path"}
                                ),
                            }
                        )
                        for item in serialized_data["doc"]
                    ]
            except Exception as _:  # noqa: BLE001
                raise ValueError(serialized_data) from None

            # Repeat file_list to match the number of processed data elements
            final_data: list[Data | None] = clean_data
            return self.rollup_data(file_list, final_data)

        concurrency = 1 if not self.use_multithreading else max(1, self.concurrency_multithreading)
        file_count = len(file_list)

        self.log(f"Starting parallel processing of {file_count} files with concurrency: {concurrency}.")
        file_paths = [str(file.path) for file in file_list]
        my_data = parallel_load_data(
            file_paths,
            silent_errors=self.silent_errors,
            load_function=process_file_standard,
            max_concurrency=concurrency,
        )

        return self.rollup_data(file_list, my_data)

    def load_files_advanced(self) -> DataFrame:
        """Load files using advanced Docling processing and export to an advanced format."""
        # TODO: Update
        self.markdown = False
        return self.load_files()

    def load_files_markdown(self) -> Message:
        """Load files using advanced Docling processing and export to Markdown format."""
        self.markdown = True
        result = self.load_files()
        return Message(text=str(result.text[0]))

    def _process_with_docling_and_export(self, file_path: str) -> Data:
        """Process a single file with Docling and export to the specified format."""
        # Import docling components only when needed
        docling_imports = self._try_import_docling()

        if docling_imports is None:
            msg = "Docling not available for advanced processing"
            raise ImportError(msg)

        conversion_status = docling_imports.conversion_status
        document_converter = docling_imports.document_converter
        image_ref_mode = docling_imports.image_ref_mode

        try:
            # Create converter based on strategy and pipeline setting
            if docling_imports.strategy == "latest" and self.pipeline == "standard":
                converter = self._create_advanced_converter(docling_imports)
            else:
                # Use basic converter for compatibility
                converter = document_converter()
                self.log("Using basic DocumentConverter for Docling processing")

            # Process single file
            result = converter.convert(file_path)

            # Check if conversion was successful
            success = False
            if hasattr(result, "status"):
                if hasattr(conversion_status, "SUCCESS"):
                    success = result.status == conversion_status.SUCCESS
                else:
                    success = str(result.status).lower() == "success"
            elif hasattr(result, "document"):
                # If no status but has document, assume success
                success = result.document is not None

            if not success:
                return Data(data={"error": "Docling conversion failed", "file_path": file_path})

            if self.markdown:
                self.log("Exporting document to Markdown format")
                # Export the document to the specified format
                exported_content = self._export_document(result.document, image_ref_mode)

                return Data(
                    text=exported_content,
                    data={
                        "exported_content": exported_content,
                        "export_format": self.EXPORT_FORMAT,
                        "file_path": file_path,
                    },
                )

            return Data(
                data={
                    "doc": self.docling_to_dataframe_simple(result.document.export_to_dict()),
                    "export_format": self.EXPORT_FORMAT,
                    "file_path": file_path,
                }
            )

        except Exception as e:  # noqa: BLE001
            return Data(data={"error": f"Docling processing error: {e!s}", "file_path": file_path})

    def docling_to_dataframe_simple(self, doc):
        """Extract all text elements into a simple DataFrame."""
        return [
            {
                "page_no": text["prov"][0]["page_no"] if text["prov"] else None,
                "label": text["label"],
                "text": text["text"],
                "level": text.get("level", None),  # for headers
            }
            for text in doc["texts"]
        ]

    def _export_document(self, document: Any, image_ref_mode: type[Enum]) -> str:
        """Export document to Markdown format with placeholder images."""
        try:
            image_mode = (
                image_ref_mode(self.IMAGE_MODE) if hasattr(image_ref_mode, self.IMAGE_MODE) else self.IMAGE_MODE
            )

            # Always export to Markdown since it's fixed
            return document.export_to_markdown(
                image_mode=image_mode,
                image_placeholder=self.md_image_placeholder,
                page_break_placeholder=self.md_page_break_placeholder,
            )

        except Exception as e:  # noqa: BLE001
            self.log(f"Markdown export failed: {e}, using basic text export")
            # Fallback to basic text export
            try:
                return document.export_to_text()
            except Exception:  # noqa: BLE001
                return str(document)
