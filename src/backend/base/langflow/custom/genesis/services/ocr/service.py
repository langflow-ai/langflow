# services/ocr/service.py
from __future__ import annotations

from typing import Any

try:
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential

    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False
    DocumentAnalysisClient = None
    AzureKeyCredential = None
    DefaultAzureCredential = None

from langflow.services.base import Service
from loguru import logger

from .settings import OCRSettings


class OCRService(Service):
    """Service for managing Azure OCR operations."""

    name = "ocr_service"

    def __init__(self):
        super().__init__()
        # Initialize settings from environment variables
        self.settings = OCRSettings()
        self._client: DocumentAnalysisClient | None = None
        self._ready = False

        # Check if Azure SDK is available
        if not AZURE_SDK_AVAILABLE:
            logger.warning("Azure SDK not available. OCR service will be limited.")

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not AZURE_SDK_AVAILABLE:
            raise ValueError(
                "Azure SDK is not available. Install azure-ai-formrecognizer to use OCR service."
            )
        if not self.settings.is_configured():
            raise ValueError("OCR settings are not properly configured")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready and AZURE_SDK_AVAILABLE

    def get_client(self) -> DocumentAnalysisClient:
        """Get or create an Azure Document Analysis Client."""
        if not AZURE_SDK_AVAILABLE:
            raise ValueError(
                "Azure SDK is not available. Install azure-ai-formrecognizer to use OCR service."
            )

        if self.settings.DEFAULT_API_KEY is None:
            try:
                credential = DefaultAzureCredential()
                return DocumentAnalysisClient(
                    endpoint=self.settings.DEFAULT_ENDPOINT, credential=credential
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to get token from Managed Identity: {e!s}"
                ) from e
        else:
            return DocumentAnalysisClient(
                endpoint=self.settings.DEFAULT_ENDPOINT,
                credential=AzureKeyCredential(self.settings.DEFAULT_API_KEY),
            )

    async def process_document(
        self,
        file_content: bytes,
        # endpoint: str,
        # api_key: Optional[str] = None,
        # auth_type: str = "api_key",
        model_type: str = "prebuilt-document",
        include_confidence: bool = False,
        extract_tables: bool = True,
    ) -> tuple[list[dict[str, Any]], str]:
        """Process a document using Azure Form Recognizer."""
        if not AZURE_SDK_AVAILABLE:
            raise ValueError(
                "Azure SDK is not available. Install azure-ai-formrecognizer to use OCR service."
            )

        try:
            client = self.get_client()

            # Start document analysis
            poller = client.begin_analyze_document(model_type, file_content)
            result = poller.result()

            # Initialize pages
            pages_data = {}
            for page in result.pages:
                pages_data[page.page_number] = {
                    "page_number": page.page_number,
                    "text": [],
                    "tables": [],
                    "form": [],
                }

            # Extract text content for each page
            for page in result.pages:
                page_text = []
                for line in page.lines:
                    text = line.content
                    if include_confidence:
                        text += f" (confidence: {line.confidence:.2f})"
                    page_text.append(text)

                # Add text to page
                pages_data[page.page_number]["text"] = "\n".join(page_text)

            # Extract and assign key-value pairs to respective pages
            if result.key_value_pairs:
                for kv_pair in result.key_value_pairs:
                    if kv_pair.key and kv_pair.value:
                        # Get page number from key's bounding region
                        page_num = (
                            kv_pair.key.bounding_regions[0].page_number
                            if kv_pair.key.bounding_regions
                            else 1
                        )
                        if page_num in pages_data:
                            pages_data[page_num]["form"].append(
                                {
                                    "key": kv_pair.key.content,
                                    "value": kv_pair.value.content,
                                }
                            )

            # Extract and assign tables to respective pages
            if extract_tables and hasattr(result, "tables"):
                for table in result.tables:
                    page_num = table.bounding_regions[0].page_number

                    # Process table data
                    table_data = []
                    for row_index in range(table.row_count):
                        row_data = []
                        for col_index in range(table.column_count):
                            cell_content = ""
                            for cell in table.cells:
                                if (
                                    cell.row_index == row_index
                                    and cell.column_index == col_index
                                ):
                                    cell_content = cell.content
                                    break
                            row_data.append(cell_content)
                        table_data.append(row_data)

                    if page_num in pages_data:
                        pages_data[page_num]["tables"].append(table_data)

            # Convert pages_data to list and sort by page number
            structured_pages = [
                {
                    "page_number": page_num,
                    "text": page_data["text"],
                    "tables": page_data["tables"],
                    "form": page_data["form"],
                }
                for page_num, page_data in sorted(pages_data.items())
            ]

            # Create plain text version
            plain_text_pages = [page["text"] for page in structured_pages]
            plain_text = "\n END OF PAGE \n".join(plain_text_pages)

            return structured_pages, plain_text

        except Exception as e:
            logger.error(f"Error processing document: {e!s}")
            raise
