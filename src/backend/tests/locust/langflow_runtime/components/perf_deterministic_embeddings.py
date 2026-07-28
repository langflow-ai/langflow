"""Deterministic embedding stub for Natural ``external_apis=stubbed`` runs.

Kept suite-local (not a vendor FakeEmbeddings) so retrieval ranking stays
stable across processes. Integration tests patch ``get_embeddings`` with this
class; stubbed Natural fixtures embed the same algorithm inline where the
Langflow server cannot import the Locust package.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

PERF_MOCK_EMBEDDING_MARKER = "PERF_MOCK_EMBEDDING"
# Match the provisioner's default all-MiniLM-L6-v2 collection dimension so
# stubbed query vectors remain compatible with the seeded local Chroma index.
DEFAULT_EMBEDDING_DIM = 384


class DeterministicEmbeddings:
    """Stable token-hashed vectors for stubbed ingest/query embedding."""

    def __init__(self, dimension: int = DEFAULT_EMBEDDING_DIM) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        # Binary term presence keeps repeated filler from overwhelming a rare
        # query marker while retaining deterministic token-overlap ranking.
        for token in set(re.findall(r"[A-Za-z0-9]+", text.lower())):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            values[index] += sign
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values] if norm else values

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
