# src/lfx/src/lfx/graph/reference/parser.py
import re

from lfx.graph.reference.schema import Reference

# Pattern breakdown:
# (?<!\w)          - negative lookbehind: @ must not be preceded by word char (prevents email matches)
# @(\w+)           - @ followed by node slug (word chars)
# \.(\w+)          - dot followed by output name (word chars)
# ((?:\.\w+|\[\d+\])*)  - optional: dot paths and array indices
REFERENCE_PATTERN = re.compile(r"(?<!\w)@(\w+)\.(\w+)((?:\.\w+|\[\d+\])*)")


def parse_references(text: str) -> list[Reference]:
    """Extract all @references from text.

    Parses references in the format: @NodeSlug.output_name.optional.dot.path[0]

    Args:
        text: The text to parse for references

    Returns:
        List of Reference objects found in the text
    """
    references = []
    for match in REFERENCE_PATTERN.finditer(text):
        node_slug = match.group(1)
        output_name = match.group(2)
        dot_path_raw = match.group(3)

        # Clean up dot path - remove leading dot if present
        dot_path = dot_path_raw.lstrip(".") if dot_path_raw else None

        references.append(
            Reference(
                node_slug=node_slug,
                output_name=output_name,
                dot_path=dot_path if dot_path else None,
            )
        )

    return references
