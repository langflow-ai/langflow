"""Live round-trip for writing precomputed vectors to OpenSearch.

Opt-in: set ``LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1`` and ``OPENSEARCH_URL``
to a reachable cluster with security disabled, for example
``docker run -p 9200:9200 -e discovery.type=single-node -e DISABLE_SECURITY_PLUGIN=true
opensearchproject/opensearch:2.11.0``.
"""

from __future__ import annotations

import os
import traceback
import uuid
from typing import TYPE_CHECKING

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
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


@pytest.mark.api_key_required
async def test_reads_chunk_text_back_when_config_names_another_text_field(tmp_path: Path) -> None:
    _require_live_opensearch()
    # The DB Providers UI persists a "Text field" setting, but LangChain writes and
    # searches chunk text under "text" whatever the config says.
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_emb_{uuid.uuid4().hex[:8]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL", "text_field": "content"},
        user_id=uuid.uuid4(),
    )
    docs = [IngestedDocument(id=f"chunk-{i}", content=f"doc {i}", embedding=[0.5] * 4) for i in range(2)]
    try:
        await backend.ensure_ready()
        await backend.add_embedded_documents(docs)
        backend._os_client.indices.refresh(index=backend._os_index)

        copied = {}
        async for batch in backend.iter_documents(include_embeddings=True):
            copied.update({d.id: d.content for d in batch})
        assert copied == {doc.id: doc.content for doc in docs}
    finally:
        await backend.delete_collection()
        await backend.teardown()


@pytest.mark.api_key_required
async def test_writes_a_batch_larger_than_one_bulk_request(tmp_path: Path) -> None:
    _require_live_opensearch()
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_emb_{uuid.uuid4().hex[:8]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL"},
        user_id=uuid.uuid4(),
    )
    docs = [IngestedDocument(id=f"chunk-{i}", content=f"doc {i}", embedding=[0.5] * 4) for i in range(501)]
    try:
        await backend.ensure_ready()
        await backend.add_embedded_documents(docs)
        backend._os_client.indices.refresh(index=backend._os_index)
        assert await backend.count() == 501
    finally:
        await backend.delete_collection()
        await backend.teardown()


@pytest.mark.api_key_required
@pytest.mark.parametrize("write", ["ingest", "copy"])
async def test_rejected_write_is_reported_without_the_documents(tmp_path: Path, write) -> None:
    _require_live_opensearch()
    # An index that holds 4-dimensional vectors refuses an 8-dimensional one, and
    # opensearch-py's error quotes each refused document back: text, metadata and vector.
    embedder = DeterministicFakeEmbedding(size=8)
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_emb_{uuid.uuid4().hex[:8]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL"},
        embedding_function=embedder,
        user_id=uuid.uuid4(),
    )
    text, metadata = "private chunk text", {"note": "private note"}
    vector = embedder.embed_documents([text])[0]
    ingested = [Document(page_content=text, metadata=metadata)]
    copied = [IngestedDocument(id="chunk-b", content=text, metadata=metadata, embedding=vector)]
    try:
        await backend.add_embedded_documents([IngestedDocument(id="chunk-a", content="doc", embedding=[0.5] * 4)])

        writing = backend.add_documents(ingested) if write == "ingest" else backend.add_embedded_documents(copied)
        with pytest.raises(RuntimeError) as rejected:
            await writing

        message = str(rejected.value)
        assert message == "1 document(s) failed to index. Error type(s): mapper_parsing_exception."
        # Nor through the traceback a logger would print.
        for printed in (message, "".join(traceback.format_exception(rejected.value))):
            assert text not in printed
            assert metadata["note"] not in printed
            assert str(float(vector[0])) not in printed
    finally:
        await backend.delete_collection()
        await backend.teardown()
