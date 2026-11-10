"""Compatibility import for the retired Chroma integration."""

from lfx.components.chroma.chroma import ChromaVectorStoreComponent as RetiredChromaVectorStoreComponent


class ChromaVectorStoreComponent(RetiredChromaVectorStoreComponent):
    """Retain bundle discovery and saved-node identity without the Chroma SDK."""


__all__ = ["ChromaVectorStoreComponent"]
