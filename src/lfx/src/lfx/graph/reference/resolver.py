# src/lfx/src/lfx/graph/reference/resolver.py
import json
from typing import TYPE_CHECKING, Any

from lfx.graph.reference.parser import parse_references
from lfx.graph.reference.utils import traverse_dot_path
from lfx.schema.data import Data
from lfx.schema.message import Message

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph


class ReferenceResolutionError(Exception):
    """Raised when a reference cannot be resolved."""


def _extract_text_value(value: Any) -> str:
    """Extract text content from a value.

    Handles Message objects by extracting their text property.
    Handles Data objects by JSON stringifying their data property.
    For other types, converts to string.

    Args:
        value: The value to extract text from

    Returns:
        String representation of the value
    """
    if value is None:
        return ""

    # Handle Message objects - extract the text content
    if isinstance(value, Message):
        return value.text or ""

    # Handle Data objects - JSON stringify the data property
    if isinstance(value, Data):
        try:
            return json.dumps(value.data, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value.data)

    # Handle objects with a text attribute
    if hasattr(value, "text") and isinstance(value.text, str):
        return value.text

    return str(value)


def resolve_references(text: str, graph: "Graph") -> str:
    """Resolve all @references in text to actual values.

    Args:
        text: Text containing @NodeSlug.output references
        graph: The graph containing the vertices

    Returns:
        Text with references replaced by actual values

    Raises:
        ReferenceResolutionError: If a reference cannot be resolved
    """
    references = parse_references(text)

    if not references:
        return text

    result = text

    for ref in references:
        # Find the vertex by slug
        vertex = graph.get_vertex_by_slug(ref.node_slug)
        if vertex is None:
            msg = f"Node '{ref.node_slug}' not found"
            raise ReferenceResolutionError(msg)

        # Get the output value
        if ref.output_name not in vertex.outputs_map:
            msg = f"Output '{ref.output_name}' not found on node '{ref.node_slug}' (vertex_id={vertex.id})"
            raise ReferenceResolutionError(msg)

        output = vertex.outputs_map[ref.output_name]
        # Get the actual value from the Output object
        value = output.value if hasattr(output, "value") else output

        # Traverse dot path if present
        if ref.dot_path:
            value = traverse_dot_path(value, ref.dot_path)

        # Extract text content from the value
        text_value = _extract_text_value(value)

        # Replace in text
        result = result.replace(ref.full_path, text_value)

    return result
