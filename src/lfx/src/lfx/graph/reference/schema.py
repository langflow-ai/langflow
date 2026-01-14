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
            return f"{base}.{self.dot_path}"
        return base
