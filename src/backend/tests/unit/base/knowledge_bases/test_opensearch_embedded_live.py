"""Live round-trip for writing precomputed vectors to OpenSearch.

Opt-in: set ``LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1`` and ``OPENSEARCH_URL``
to a reachable cluster with security disabled, for example
``docker run -p 9200:9200 -e discovery.type=single-node -e DISABLE_SECURITY_PLUGIN=true
opensearchproject/opensearch:2.11.0``.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.backends import IngestedDocument, create_backend

if TYPE_CHECKING:
    from pathlib import Path


def _require_live_opensearch() -> None:
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1":
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 to run live OpenSearch tests")
    if not os.getenv("OPENSEARCH_URL"):
        pytest.skip("OPENSEARCH_URL not set")
    pytest.importorskip("opensearchpy")


@pytest.mark.api_key_required
async def test_copy_preserves_ids_and_vectors_without_an_embedder(tmp_path: Path) -> None:
    _require_live_opensearch()
    # No embedding function: nothing on this path may call a model.
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_emb_{uuid.uuid4().hex[:8]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL"},
        user_id=uuid.uuid4(),
    )
    docs = [
        IngestedDocument(id=f"chunk-{i}", content=f"doc {i}", metadata={"i": i}, embedding=[i / 10] * 8)
        for i in range(4)
    ]
    try:
        await backend.ensure_ready()
        await backend.add_embedded_documents(docs)
        await backend.add_embedded_documents(docs)  # a re-run must upsert
        backend._os_client.indices.refresh(index=backend._os_index)

        assert await backend.count() == 4
        copied = {}
        async for batch in backend.iter_documents(batch_size=2, include_embeddings=True):
            copied.update({d.id: d for d in batch})
        for doc in docs:
            assert copied[doc.id].content == doc.content
            assert copied[doc.id].metadata == doc.metadata
            assert copied[doc.id].embedding == pytest.approx(doc.embedding)
    finally:
        await backend.delete_collection()
        await backend.teardown()
