"""Template Text Extractor Component - Extracts text from JSON documents."""

from lfx.custom.custom_component.component import Component
from langflow.inputs import DataInput
from lfx.io import BoolInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

# Inline utility function
def extract_text_from_document(document_data):
    """Extract structured text from a document JSON structure."""
    try:
        # Handle string input (fallback)
        if isinstance(document_data, str):
            return {
                "cleaned_lines": {
                    "Paragraph 1": {
                        "element_id": "text_0",
                        "text": document_data,
                        "type": "paragraph"
                    }
                },
                "metadata": {
                    "total_elements": 1,
                    "extraction_method": "raw_text"
                }
            }

        # Handle dict input (expected from DOCX processor)
        if not isinstance(document_data, dict):
            document_data = {"error": "Invalid document data format"}

        # Check for errors in input
        if "error" in document_data:
            return {
                "cleaned_lines": {},
                "metadata": {
                    "error": document_data["error"],
                    "total_elements": 0
                }
            }

        cleaned_lines = {}
        element_counter = 0

        # Extract paragraphs
        paragraphs = document_data.get("paragraphs", [])
        for para_idx, paragraph in enumerate(paragraphs):
            if isinstance(paragraph, dict) and paragraph.get("text", "").strip():
                key = f"Paragraph {para_idx + 1}"
                cleaned_lines[key] = {
                    "element_id": paragraph.get("element_id", f"para_{element_counter}"),
                    "text": paragraph["text"].strip(),
                    "type": "paragraph",
                    "style": paragraph.get("style", "Normal"),
                    "index": paragraph.get("index", para_idx)
                }
                element_counter += 1

        # Extract tables
        tables = document_data.get("tables", [])
        for table_idx, table in enumerate(tables):
            if isinstance(table, dict):
                key = f"Table {table_idx + 1}"

                # Convert table rows to a more usable format
                table_data = []
                rows = table.get("rows", [])

                for row in rows:
                    if isinstance(row, dict):
                        cells = row.get("cells", [])
                        row_text = []
                        for cell in cells:
                            if isinstance(cell, dict):
                                cell_text = cell.get("text", "").strip()
                                row_text.append(cell_text)

                        if row_text:  # Only add non-empty rows
                            table_data.append({
                                "row": row_text
                            })

                if table_data:  # Only add table if it has content
                    cleaned_lines[key] = {
                        "element_id": table.get("element_id", f"table_{element_counter}"),
                        "table": table_data,
                        "type": "table",
                        "index": table.get("index", table_idx)
                    }
                    element_counter += 1

        # Extract images (if any)
        images = document_data.get("images", [])
        for img_idx, image in enumerate(images):
            if isinstance(image, dict):
                key = f"Image {img_idx + 1}"
                cleaned_lines[key] = {
                    "element_id": image.get("element_id", f"image_{element_counter}"),
                    "type": "image",
                    "filename": image.get("filename", f"image_{img_idx + 1}"),
                    "content_type": image.get("content_type", "unknown")
                }
                element_counter += 1

        # Prepare metadata
        metadata = {
            "total_elements": len(cleaned_lines),
            "total_paragraphs": len(paragraphs),
            "total_tables": len(tables),
            "total_images": len(images),
            "extraction_method": "structured_document",
            "original_metadata": document_data.get("metadata", {})
        }

        # Add section information if available
        sections = document_data.get("sections", {})
        if sections:
            metadata["sections"] = sections
            metadata["total_sections"] = len(sections)

        return {
            "cleaned_lines": cleaned_lines,
            "metadata": metadata
        }

    except Exception as e:
        return {
            "cleaned_lines": {},
            "metadata": {
                "error": f"Error extracting text: {str(e)}",
                "total_elements": 0
            }
        }


class TemplateTextExtractorComponent(Component):
    """Extract structured text from JSON documents for LLM processing."""

    display_name = "Template Text Extractor"
    category: str = "processing"
    description = "Extract structured text from JSON documents"
    documentation = ""
    icon = "text"
    name = "TemplateTextExtractor"

    inputs = [
        DataInput(
            name="document_json",
            display_name="Document JSON",
            info="JSON document from DOCX processor",
            required=True,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            value=True,
            info="Include extraction metadata in output",
        ),
    ]

    outputs = [
        Output(
            display_name="Extracted Text", name="extracted_text", method="extract_text"
        ),
        Output(
            display_name="Formatted Text",
            name="formatted_text",
            method="get_formatted_text",
        ),
    ]

    def extract_text(self) -> Data:
        """Extract text data from the document JSON."""
        try:
            if not self.document_json:
                return Data(value={"error": "No document JSON provided"})

            # Handle Data object input
            document_data = self.document_json
            if hasattr(document_data, "value"):
                document_data = document_data.value
            elif hasattr(document_data, "data"):
                document_data = document_data.data

            # Extract text using utility function
            result = extract_text_from_document(document_data)

            # Remove metadata if not requested
            if not self.include_metadata:
                result.pop("metadata", None)

            # Set status
            text_count = len(result.get("cleaned_lines", {}))
            self.status = f"Extracted {text_count} text elements"

            return Data(value=result)

        except Exception as e:
            self.status = f"Error: {str(e)}"
            return Data(value={"error": str(e), "status": "failed"})

    def get_formatted_text(self) -> Message:
        """Get formatted text with element IDs for prompt input."""
        try:
            if not self.document_json:
                return Message(text="Error: No document JSON provided")

            # Handle Data object input
            document_data = self.document_json
            if hasattr(document_data, "value"):
                document_data = document_data.value
            elif hasattr(document_data, "data"):
                document_data = document_data.data

            # Extract text using utility function
            result = extract_text_from_document(document_data)

            # Format text with element IDs for prompt
            formatted_lines = []
            cleaned_lines = result.get("cleaned_lines", {})

            # Sort by paragraph/table number
            for key in sorted(
                cleaned_lines.keys(),
                key=lambda x: (
                    x.split()[0],  # Type (Paragraph/Table)
                    int(x.split()[-1]) if x.split()[-1].isdigit() else 0,  # Number
                ),
            ):
                item = cleaned_lines[key]
                element_id = item.get("element_id", "")

                if "text" in item:
                    # Format: [element_id] text content
                    formatted_lines.append(f"[{element_id}] {item['text']}")
                elif "table" in item:
                    # Format table data
                    formatted_lines.append(f"[{element_id}] Table:")
                    for row_data in item.get("table", []):
                        row = row_data.get("row", [])
                        formatted_lines.append("  | " + " | ".join(row) + " |")

            # Join all lines into a single text string
            formatted_text = "\n".join(formatted_lines)

            self.status = f"Formatted {len(formatted_lines)} lines for prompt"

            # Return as Message that can be used directly in prompt
            return Message(text=formatted_text)

        except Exception as e:
            self.status = f"Error: {str(e)}"
            return Message(text=f"Error: {str(e)}")
