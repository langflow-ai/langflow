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
        ids = [doc.id for doc in docs]
        assert await backend.get_documents_by_ids(ids) == []
        await backend.add_embedded_documents(docs)
        stored = await backend.get_documents_by_ids(ids)
        assert {doc.id: (doc.page_content, doc.metadata) for doc in stored} == {
            doc.id: (doc.content, doc.metadata) for doc in docs
        }
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


# Share every hyphen-separated piece but the first, as UUIDs from one job batch can.
_JOB_A = "aaaaaaaa-1111-4111-8111-111111111111"
_JOB_B = "bbbbbbbb-1111-4111-8111-111111111111"


async def _seed_two_jobs(tmp_path: Path):
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_job_{uuid.uuid4().hex[:8]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL"},
        user_id=uuid.uuid4(),
    )
    await backend.ensure_ready()
    docs = [
        IngestedDocument(id=f"a-{i}", content=f"a {i}", metadata={"job_id": _JOB_A}, embedding=[i / 10] * 8)
        for i in range(5)
    ] + [
        IngestedDocument(id=f"b-{i}", content=f"b {i}", metadata={"job_id": _JOB_B}, embedding=[i / 10] * 8)
        for i in range(3)
    ]
    await backend.add_embedded_documents([*docs, IngestedDocument(id="c", content="old", embedding=[0.5] * 8)])
    backend._os_client.indices.refresh(index=backend._os_index)
    return backend


async def _read_job(backend, job_id, **kwargs):
    return [doc async for batch in backend.iter_job_documents(job_id, **kwargs) for doc in batch]


async def test_jobs_sharing_uuid_pieces_read_back_apart(tmp_path: Path) -> None:
    _require_live_opensearch()
    backend = await _seed_two_jobs(tmp_path)
    try:
        assert await backend.count_job(_JOB_A) == 5
        assert await backend.count_job(_JOB_B) == 3
        job_a = await _read_job(backend, _JOB_A, batch_size=2)
        assert [doc.id for doc in job_a] == [f"a-{i}" for i in range(5)]
        assert job_a[3].content == "a 3"
        assert job_a[3].embedding == pytest.approx([0.3] * 8)
    finally:
        await backend.delete_collection()
        await backend.teardown()


async def test_resuming_a_job_returns_only_what_is_left(tmp_path: Path) -> None:
    _require_live_opensearch()
    backend = await _seed_two_jobs(tmp_path)
    try:
        assert [doc.id for doc in await _read_job(backend, _JOB_A, after_id="a-2")] == ["a-3", "a-4"]
        assert [doc.id for doc in await _read_job(backend, None, after_id="b-2")] == ["c"]
        assert len(await _read_job(backend, None)) == 9
    finally:
        await backend.delete_collection()
        await backend.teardown()


async def test_a_job_is_found_in_a_flat_source_layout(tmp_path: Path) -> None:
    _require_live_opensearch()
    backend = await _seed_two_jobs(tmp_path)
    job = "cccccccc-1111-4111-8111-111111111111"
    try:
        backend._os_client.index(
            index=backend._os_index,
            id="flat",
            body={"text": "flat", "job_id": job, "vector_field": [0.1] * 8},
            refresh=True,
        )
        assert await backend.count_job(job) == 1
        assert [(doc.id, doc.content, doc.metadata) for doc in await _read_job(backend, job)] == [
            ("flat", "flat", {"job_id": job})
        ]
    finally:
        await backend.delete_collection()
        await backend.teardown()


async def test_a_never_created_index_has_no_job_chunks(tmp_path: Path) -> None:
    _require_live_opensearch()
    backend = create_backend(
        "opensearch",
        kb_name=f"kb_job_{uuid.uuid4().hex[:8]}",
        kb_path=tmp_path,
        backend_config={"url_variable": "OPENSEARCH_URL"},
        user_id=uuid.uuid4(),
    )
    try:
        assert await _read_job(backend, _JOB_A) == []
        assert await backend.count_job(_JOB_A) == 0
    finally:
        await backend.teardown()
