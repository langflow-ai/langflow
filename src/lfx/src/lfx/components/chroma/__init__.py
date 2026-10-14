# lfx-bundles-shim
"""Import-only compatibility for retired Chroma components, excluded from discovery."""

from lfx.components.chroma.chroma import ChromaVectorStoreComponent
from lfx.components.chroma.local_db import LocalDBComponent

__all__ = ["ChromaVectorStoreComponent", "LocalDBComponent"]
