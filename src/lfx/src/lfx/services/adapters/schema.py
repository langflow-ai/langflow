"""Schema definitions for adapter registries."""

from __future__ import annotations

from enum import Enum


class AdapterType(str, Enum):
    """Categories for adapter registries.

    The enum value drives convention-based derivation of discovery
    coordinates (entry-point group and config section path).
    """

    DEPLOYMENT = "deployment"

    @property
    def entry_point_group(self) -> str:
        """Entry-point group name for this adapter type."""
        return f"lfx.{self.value}.adapters"

    @property
    def config_section_path(self) -> tuple[str, ...]:
        """TOML config section path for this adapter type."""
        return (self.value, "adapters")
