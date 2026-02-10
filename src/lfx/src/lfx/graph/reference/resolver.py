# src/lfx/src/lfx/graph/reference/resolver.py
import json
import logging
from typing import TYPE_CHECKING, Any

from lfx.graph.reference.parser import parse_references
from lfx.graph.reference.schema import Reference
from lfx.graph.reference.utils import traverse_dot_path
from lfx.schema.data import Data
from lfx.schema.message import Message

logger = logging.getLogger(__name__)

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
        text = value.text
        if text is None:
            return ""
        if isinstance(text, str):
            return text
        # If text is an iterator (async or sync), it hasn't been consumed yet
        logger.warning(
            "Message text is a %s and cannot be resolved synchronously in @reference; "
            "returning empty string. Consider awaiting the message before referencing it.",
            type(text).__name__,
        )
        return ""

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


VARS_SLUG = "Vars"


def resolve_references(
    text: str,
    graph: "Graph",
    global_variables: dict[str, Any] | None = None,
) -> str:
    """Resolve all @references in text to actual values.

    Supports two kinds of references:
    - @NodeSlug.output — resolved from graph vertices
    - @Vars.variable_name — resolved from global_variables dict

    Args:
        text: Text containing @references
        graph: The graph containing the vertices
        global_variables: Optional dict of global variable name → value

    Returns:
        Text with references replaced by actual values

    Raises:
        ReferenceResolutionError: If a reference cannot be resolved
    """
    references = parse_references(text)

    if not references:
        return text

    # Sort by full_path length descending so longer (more specific) references
    # are replaced first, preventing shorter prefixes from corrupting longer ones
    # e.g. @API.data.user.name must be replaced before @API.data
    references.sort(key=lambda r: len(r.full_path), reverse=True)

    result = text

    for ref in references:
        if ref.node_slug == VARS_SLUG:
            value = _resolve_global_variable(ref, global_variables)
        else:
            value = _resolve_vertex_reference(ref, graph)

        # Traverse dot path if present
        if ref.dot_path:
            try:
                value = traverse_dot_path(value, ref.dot_path)
            except ValueError as e:
                msg = f"Failed to resolve path '{ref.full_path}': {e}"
                raise ReferenceResolutionError(msg) from e

        # Extract text content from the value
        text_value = _extract_text_value(value)

        # Replace in text
        result = result.replace(ref.full_path, text_value)

    return result


def _resolve_global_variable(ref: Reference, global_variables: dict[str, Any] | None) -> Any:
    """Resolve a @Vars.variable_name reference."""
    if global_variables is None:
        msg = f"Global variables are not available; cannot resolve '@Vars.{ref.output_name}'"
        raise ReferenceResolutionError(msg)
    if ref.output_name not in global_variables:
        msg = f"Global variable '{ref.output_name}' not found"
        raise ReferenceResolutionError(msg)
    return global_variables[ref.output_name]


def _resolve_vertex_reference(ref: Reference, graph: "Graph") -> Any:
    """Resolve a @NodeSlug.output reference from the graph."""
    vertex = graph.get_vertex_by_slug(ref.node_slug)
    if vertex is None:
        msg = f"Node '{ref.node_slug}' not found"
        raise ReferenceResolutionError(msg)

    if ref.output_name not in vertex.outputs_map:
        msg = f"Output '{ref.output_name}' not found on node '{ref.node_slug}' (vertex_id={vertex.id})"
        raise ReferenceResolutionError(msg)

    output = vertex.outputs_map[ref.output_name]
    return output.value if hasattr(output, "value") else output
