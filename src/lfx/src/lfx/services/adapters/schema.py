"""Schema definitions for adapter registries."""

from __future__ import annotations

from enum import Enum


class AdapterType(str, Enum):
    """Categories for adapter registries."""

    DEPLOYMENT = "deployment"
