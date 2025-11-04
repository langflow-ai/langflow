"""Azure Document Intelligence Service implementation."""

from __future__ import annotations

from typing import Any
import uuid

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

from .settings import DocumentIntelligenceSettings


class DocumentIntelligenceService(Service):
    """Service for managing Azure Document Intelligence operations."""

    name = "document_intelligence_service"

    def __init__(self):
        super().__init__()
        # Initialize settings from environment variables
        self.settings = DocumentIntelligenceSettings()
        self._client: DocumentAnalysisClient | None = None
        self._ready = False

        # Check if Azure SDK is available
        if not AZURE_SDK_AVAILABLE:
            logger.warning("Azure SDK not available. Document Intelligence service will be limited.")

    def set_ready(self) -> None:
        """Set the service as ready."""
        if not AZURE_SDK_AVAILABLE:
            raise ValueError(
                "Azure SDK is not available. Install azure-ai-formrecognizer to use Document Intelligence service."
            )
        if not self.settings.is_configured():
            raise ValueError("Document Intelligence settings are not properly configured")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready and AZURE_SDK_AVAILABLE

    def get_client(self) -> DocumentAnalysisClient:
        """Get or create an Azure Document Analysis Client."""
        if not AZURE_SDK_AVAILABLE:
            raise ValueError(
                "Azure SDK is not available. Install azure-ai-formrecognizer to use Document Intelligence service."
            )

        if self.settings.API_KEY is None:
            try:
                credential = DefaultAzureCredential()
                return DocumentAnalysisClient(
                    endpoint=self.settings.ENDPOINT, credential=credential
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to get token from Managed Identity: {e!s}"
                ) from e
        else:
            return DocumentAnalysisClient(
                endpoint=self.settings.ENDPOINT,
                credential=AzureKeyCredential(self.settings.API_KEY),
            )

    async def process_document(
        self,
        file_content: bytes,
        model_type: str = "prebuilt-document",
        include_confidence: bool = False,
        extract_tables: bool = True,
        extract_key_value_pairs: bool = True,
    ) -> tuple[list[dict[str, Any]], str]:
        """Process a document using Azure Document Intelligence.

        Args:
            file_content: The document content as bytes
            model_type: The Document Intelligence model to use
            include_confidence: Whether to include confidence scores
            extract_tables: Whether to extract table data
            extract_key_value_pairs: Whether to extract form fields

        Returns:
            Tuple of (structured_pages, plain_text)
        """
        if not AZURE_SDK_AVAILABLE:
            raise ValueError(
                "Azure SDK is not available. Install azure-ai-formrecognizer to use Document Intelligence service."
            )

        try:
            client = self.get_client()

            # Start document analysis
            poller = client.begin_analyze_document(model_type, file_content)
            result = poller.result()

            # Initialize pages
            pages_data = {}
            document_uuid = str(uuid.uuid4())
            for page in result.pages:
                chunks_metadata=[]
                for _, line in enumerate(page.lines):
                    chunk_uuid = str(uuid.uuid4())
                    
                    # Extract all metadata from OCR
                    chunk_metadata = {
                        "chunk_uuid": chunk_uuid,
                        "content": line.content,
                        "text": line.content,  # Alias
                        
                        # Character offsets in the original document
                        "begin_offset": line.spans[0].offset if line.spans else 0,
                        "end_offset": line.spans[0].offset + line.spans[0].length if line.spans else len(line.content),
                        
                        # Bounding box coordinates (from OCR)
                        "bounding_region": {
                            "page_number": page.page_number,
                            "polygon": [
                                {"x": point.x, "y": point.y} 
                                for point in line.polygon  # ← Use line.polygon, not line.bounding_regions
                            ] if hasattr(line, 'polygon') and line.polygon else []
                        }
                    }
                    chunks_metadata.append(chunk_metadata)
                pages_data[page.page_number] = {
                    "page_number": page.page_number,
                    "text": [],
                    "tables": [],
                    "form": [],
                    "width": page.width if hasattr(page, 'width') else None,
                    "height": page.height if hasattr(page, 'height') else None,
                    "unit": page.unit if hasattr(page, 'unit') else None,
                    "chunks_metadata":chunks_metadata,
                    "document_uuid":document_uuid
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
            if extract_key_value_pairs and result.key_value_pairs:
                for kv_pair in result.key_value_pairs:
                    if kv_pair.key and kv_pair.value:
                        # Get page number from key's bounding region
                        page_num = (
                            kv_pair.key.bounding_regions[0].page_number
                            if kv_pair.key.bounding_regions
                            else 1
                        )
                        if page_num in pages_data:
                            form_item = {
                                "key": kv_pair.key.content,
                                "value": kv_pair.value.content,
                            }
                            if include_confidence:
                                form_item["key_confidence"] = kv_pair.key.confidence if hasattr(kv_pair.key, 'confidence') else None
                                form_item["value_confidence"] = kv_pair.value.confidence if hasattr(kv_pair.value, 'confidence') else None

                            pages_data[page_num]["form"].append(form_item)

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
                            cell_confidence = None
                            for cell in table.cells:
                                if (
                                    cell.row_index == row_index
                                    and cell.column_index == col_index
                                ):
                                    cell_content = cell.content
                                    if include_confidence and hasattr(cell, 'confidence'):
                                        cell_confidence = cell.confidence
                                    break

                            cell_data = {"content": cell_content}
                            if include_confidence and cell_confidence is not None:
                                cell_data["confidence"] = cell_confidence
                            row_data.append(cell_data)
                        table_data.append(row_data)

                    if page_num in pages_data:
                        table_info = {
                            "data": table_data,
                            "row_count": table.row_count,
                            "column_count": table.column_count,
                        }
                        if include_confidence and hasattr(table, 'confidence'):
                            table_info["confidence"] = table.confidence

                        pages_data[page_num]["tables"].append(table_info)

            # Convert pages_data to list and sort by page number
            structured_pages = [
                {
                    "page_number": page_num,
                    "text": page_data["text"],
                    "tables": page_data["tables"],
                    "form": page_data["form"],
                    "width": page_data.get("width"),
                    "height": page_data.get("height"),
                    "unit": page_data.get("unit"),
                    "chunks_metadata": page_data.get("chunks_metadata"),
                    "document_uuid": page_data.get("document_uuid")

                }
                for page_num, page_data in sorted(pages_data.items())
            ]

            # Create plain text version
            plain_text_pages = [page["text"] for page in structured_pages]
            plain_text = "\n=== END OF PAGE ===\n".join(plain_text_pages)

            return structured_pages, plain_text,document_uuid

        except Exception as e:
            logger.error(f"Error processing document: {e!s}")
            raise