# src/lfx/src/lfx/graph/reference/schema.py
from dataclasses import dataclass


@dataclass
class Reference:
    """Represents an inline variable reference like @NodeSlug.output.path."""

    node_slug: str
    output_name: str
    dot_path: str | None = None

    @property
    def full_path(self) -> str:
        """Return the full reference string."""
        base = f"@{self.node_slug}.{self.output_name}"
        if self.dot_path:
            # If dot_path starts with '[', join directly (e.g. @Node.output[0])
            # Otherwise join with a dot (e.g. @Node.output.items)
            separator = "" if self.dot_path.startswith("[") else "."
            return f"{base}{separator}{self.dot_path}"
        return base
