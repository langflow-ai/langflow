"""Deterministic embedding stub for Natural ``external_apis=stubbed`` runs.

Kept suite-local (not a vendor FakeEmbeddings) so retrieval ranking stays
stable across processes. Integration tests patch ``get_embeddings`` with this
class; stubbed Natural fixtures embed the same algorithm inline where the
Langflow server cannot import the Locust package.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

PERF_MOCK_EMBEDDING_MARKER = "PERF_MOCK_EMBEDDING"
# Match the provisioner's default all-MiniLM-L6-v2 collection dimension so
# stubbed query vectors remain compatible with the seeded local Chroma index.
DEFAULT_EMBEDDING_DIM = 384


class DeterministicEmbeddings:
    """Stable hash-derived vectors for stubbed ingest/query embedding."""

    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIM) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        values: list[float] = []
        block = 0
        while len(values) < self.dimension:
            digest = hashlib.sha256(f"{block}:{text}".encode()).digest()
            values.extend(byte / 255.0 for byte in digest)
            block += 1
        return values[: self.dimension]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
