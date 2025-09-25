"""Text Extraction Utility Functions."""

from typing import Any, Dict, List, Optional, Union


def extract_text_from_document(document_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """
    Extract structured text from a document JSON structure.

    Args:
        document_data: Document data from DOCX processor (dict) or raw string

    Returns:
        Dict containing cleaned_lines, metadata, and other extracted information
    """
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


def format_text_with_element_ids(cleaned_lines: Dict[str, Any]) -> List[str]:
    """
    Format cleaned lines into text with element IDs for prompt use.

    Args:
        cleaned_lines: Dictionary of cleaned text elements

    Returns:
        List of formatted text lines
    """
    formatted_lines = []

    # Sort by element type and number
    for key in sorted(
        cleaned_lines.keys(),
        key=lambda x: (
            x.split()[0],  # Type (Paragraph/Table/Image)
            int(x.split()[-1]) if x.split()[-1].isdigit() else 0,  # Number
        ),
    ):
        item = cleaned_lines[key]
        element_id = item.get("element_id", "")

        if item.get("type") == "paragraph" and "text" in item:
            # Format: [element_id] text content
            formatted_lines.append(f"[{element_id}] {item['text']}")

        elif item.get("type") == "table" and "table" in item:
            # Format table data
            formatted_lines.append(f"[{element_id}] Table:")
            for row_data in item.get("table", []):
                row = row_data.get("row", [])
                if row:
                    formatted_lines.append("  | " + " | ".join(row) + " |")

        elif item.get("type") == "image":
            # Format image reference
            filename = item.get("filename", "unknown")
            formatted_lines.append(f"[{element_id}] Image: {filename}")

    return formatted_lines


def get_text_summary(document_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """
    Get a summary of text content from document data.

    Args:
        document_data: Document data to summarize

    Returns:
        Dict containing summary information
    """
    result = extract_text_from_document(document_data)
    cleaned_lines = result.get("cleaned_lines", {})
    metadata = result.get("metadata", {})

    # Count different element types
    element_counts = {
        "paragraphs": 0,
        "tables": 0,
        "images": 0
    }

    total_text_length = 0
    text_snippets = []

    for key, item in cleaned_lines.items():
        item_type = item.get("type", "unknown")

        if item_type == "paragraph":
            element_counts["paragraphs"] += 1
            text = item.get("text", "")
            total_text_length += len(text)
            if len(text) > 50:
                text_snippets.append(text[:50] + "...")
            else:
                text_snippets.append(text)

        elif item_type == "table":
            element_counts["tables"] += 1
            table_data = item.get("table", [])
            if table_data:
                # Get first row as snippet
                first_row = table_data[0].get("row", [])
                if first_row:
                    text_snippets.append(f"Table: {' | '.join(first_row[:3])}...")

        elif item_type == "image":
            element_counts["images"] += 1
            filename = item.get("filename", "unknown")
            text_snippets.append(f"Image: {filename}")

    return {
        "element_counts": element_counts,
        "total_text_length": total_text_length,
        "text_snippets": text_snippets[:5],  # First 5 snippets
        "metadata": metadata
    }