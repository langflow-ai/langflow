"""Compatibility import for the retired Chroma integration."""

from lfx.components.chroma.local_db import LocalDBComponent as RetiredLocalDBComponent


class LocalDBComponent(RetiredLocalDBComponent):
    """Retain bundle discovery and saved-node identity without the Chroma SDK."""


__all__ = ["LocalDBComponent"]
