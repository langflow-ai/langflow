"""Unit tests for ``OpenSearchBackend`` defaults.

Pins the default vector-field name to ``vector_field`` — the field
LangChain's ``OpenSearchVectorSearch`` actually writes embeddings to.
That wrapper resolves ``vector_field`` from per-call kwargs (default
``"vector_field"``) and ignores the value passed to its constructor;
the KB backend never passes a per-call override, so ingestion writes
and similarity searches both land on ``vector_field``. ``iter_documents``
reads ``DEFAULT_VECTOR_FIELD`` to pull stored embeddings back, so a
regression here (e.g. back to ``chunk_embedding``) silently returns
``_embeddings: None`` for every retrieved chunk even though retrieval
itself still works — the exact ``include_embeddings`` bug these tests
guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.knowledge_bases.backends import OpenSearchBackend
from lfx.base.knowledge_bases.backends.opensearch import (
    DEFAULT_TEXT_FIELD,
    DEFAULT_VECTOR_FIELD,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_backend(
    kb_path: Path,
    backend_config: dict | None = None,
) -> OpenSearchBackend:
    backend = OpenSearchBackend(
        kb_name="kb_os_defaults",
        kb_path=kb_path,
        backend_config=backend_config or {"index_name": "test_index"},
    )
    # Pre-populate resolved secrets so ``ensure_ready`` is a no-op and
    # ``_build_vector_store`` can run without touching variable_service.
    backend._resolved_url = "https://example.local:9200"
    backend._resolved_username = "admin"
    backend._resolved_password = "secret"  # noqa: S105 — test fixture  # pragma: allowlist secret
    backend._secrets_resolved = True
    return backend


class TestOpenSearchBackendVectorFieldDefault:
    """Default field names must match LangChain's write field (``vector_field``)."""

    def test_default_vector_field_is_vector_field(self) -> None:
        # LangChain's OpenSearchVectorSearch writes embeddings under
        # ``vector_field`` (its per-call default, which the constructor arg
        # cannot change). ``iter_documents`` reads this constant to fetch them
        # back, so it must match the write field or include_embeddings
        # retrieval returns None for every chunk.
        assert DEFAULT_VECTOR_FIELD == "vector_field"

    def test_build_vector_store_uses_vector_field_by_default(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path)
        fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch(
                "langchain_community.vectorstores.OpenSearchVectorSearch",
                fake_wrapper,
            ),
        ):
            _ = backend.vector_store

        fake_wrapper.assert_called_once()
        kwargs = fake_wrapper.call_args.kwargs
        assert kwargs["vector_field"] == "vector_field"
        assert kwargs["text_field"] == DEFAULT_TEXT_FIELD
        # Sanity-check the field the backend stashes for iter/count helpers
        # so the in-memory state agrees with the field LangChain reads/writes.
        assert backend._os_vector_field == "vector_field"

    def test_build_vector_store_honours_backend_config_override(self, tmp_path: Path) -> None:
        # Operators with a legacy ``vector_field`` index (or any custom
        # name) must still be able to override via backend_config.
        backend = _make_backend(
            tmp_path,
            backend_config={"index_name": "test_index", "vector_field": "embedding"},
        )
        fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch(
                "langchain_community.vectorstores.OpenSearchVectorSearch",
                fake_wrapper,
            ),
        ):
            _ = backend.vector_store

        kwargs = fake_wrapper.call_args.kwargs
        assert kwargs["vector_field"] == "embedding"
        assert backend._os_vector_field == "embedding"


@pytest.mark.parametrize(
    ("config_value", "expected"),
    [
        (None, "vector_field"),
        ("", "vector_field"),
        ("custom_vec", "custom_vec"),
    ],
)
def test_vector_field_resolution_table(tmp_path: Path, config_value: str | None, expected: str) -> None:
    """Empty / missing config falls back to the default; truthy wins."""
    cfg: dict = {"index_name": "test_index"}
    if config_value is not None:
        cfg["vector_field"] = config_value
    backend = _make_backend(tmp_path, backend_config=cfg)
    fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
    with (
        patch("opensearchpy.OpenSearch", return_value=MagicMock()),
        patch(
            "langchain_community.vectorstores.OpenSearchVectorSearch",
            fake_wrapper,
        ),
    ):
        _ = backend.vector_store

    assert fake_wrapper.call_args.kwargs["vector_field"] == expected


class TestOpenSearchIterDocumentsEmbeddings:
    """``iter_documents`` must return stored embeddings from the write field.

    The ``include_embeddings`` retrieval path gathers these vectors via
    ``iter_documents`` and joins them back onto the search results. LangChain
    stores them under ``vector_field`` (see module docstring); reading any
    other field yields ``embedding=None`` and the Knowledge component surfaces
    ``_embeddings: None`` for every chunk — the bug this guards. The
    ``_source`` shapes below mirror real upload-ingested OpenSearch documents:
    ``{text, metadata, vector_field}``, with a doc-level ``_id`` (a UUID)
    intentionally distinct from any metadata ``_id`` (a content hash).
    """

    @pytest.mark.asyncio
    async def test_iter_documents_reads_embeddings_from_vector_field(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path)
        upload_vec = [0.1, 0.2, 0.3]
        identifier_vec = [0.4, 0.5, 0.6]
        # Two real-world shapes: an upload-ingested chunk (no ``_id`` in
        # metadata, joined downstream on content) and an identifier-column
        # chunk (``_id`` present, joined on id).
        fake_hits = [
            {
                "_id": "0d73456e-4a65-4edd-9d6e-0dbf0f7d1063",
                "_source": {
                    "text": "upload chunk",
                    "metadata": {"file_name": "a.txt", "chunk_index": 0},
                    "vector_field": upload_vec,
                },
            },
            {
                "_id": "1f84567a-1111-2222-3333-444455556666",
                "_source": {
                    "text": "identifier chunk",
                    "metadata": {"id": "1", "category": "geo", "_id": "6b86b273ff34"},
                    "vector_field": identifier_vec,
                },
            },
        ]

        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch", MagicMock()),
            patch("opensearchpy.helpers.scan", return_value=(hit for hit in fake_hits)),
        ):
            _ = backend.vector_store  # resolves _os_* fields from defaults
            batches = [batch async for batch in backend.iter_documents(include_embeddings=True)]

        docs = [doc for batch in batches for doc in batch]
        assert len(docs) == 2
        by_content = {doc.content: doc for doc in docs}
        # Upload-style chunk: embedding populated, no _id (content-keyed join).
        assert by_content["upload chunk"].embedding == upload_vec
        assert "_id" not in by_content["upload chunk"].metadata
        # Identifier-style chunk: embedding populated, _id preserved for the join.
        assert by_content["identifier chunk"].embedding == identifier_vec
        assert by_content["identifier chunk"].metadata.get("_id") == "6b86b273ff34"

    @pytest.mark.asyncio
    async def test_iter_documents_falls_back_when_config_names_unwritten_field(self, tmp_path: Path) -> None:
        # The real-world failure: the DB-providers UI persists
        # ``backend_config.vector_field = "chunk_embedding"``, but LangChain
        # ignores that and writes embeddings under ``vector_field``. Reading the
        # configured name alone returns None for every chunk (the reported bug);
        # the fallback to LangChain's field must still surface the vector.
        backend = _make_backend(
            tmp_path,
            backend_config={"index_name": "test_index", "vector_field": "chunk_embedding"},
        )
        embedding = [0.7, 0.8, 0.9]
        fake_hits = [
            {
                "_id": "doc-uuid",
                "_source": {
                    "text": "legacy-config chunk",
                    "metadata": {"file_name": "a.txt"},
                    "vector_field": embedding,  # where LangChain actually wrote it
                },
            },
        ]

        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch", MagicMock()),
            patch("opensearchpy.helpers.scan", return_value=(hit for hit in fake_hits)),
        ):
            _ = backend.vector_store
            # The configured (never-written) field is what the backend stashes…
            assert backend._os_vector_field == "chunk_embedding"
            batches = [batch async for batch in backend.iter_documents(include_embeddings=True)]

        docs = [doc for batch in batches for doc in batch]
        # …yet the embedding still comes back via the LangChain-default fallback.
        assert docs[0].embedding == embedding

    @pytest.mark.asyncio
    async def test_iter_documents_prefers_configured_field_when_present(self, tmp_path: Path) -> None:
        # An externally-populated index that genuinely stores vectors under the
        # configured field must be read from that field, not the fallback.
        backend = _make_backend(
            tmp_path,
            backend_config={"index_name": "test_index", "vector_field": "embedding"},
        )
        configured_vec = [1.0, 1.1, 1.2]
        fake_hits = [
            {"_id": "x", "_source": {"text": "c", "metadata": {"k": "v"}, "embedding": configured_vec}},
        ]
        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch", MagicMock()),
            patch("opensearchpy.helpers.scan", return_value=(hit for hit in fake_hits)),
        ):
            _ = backend.vector_store
            batches = [batch async for batch in backend.iter_documents(include_embeddings=True)]

        docs = [doc for batch in batches for doc in batch]
        assert docs[0].embedding == configured_vec

    @pytest.mark.asyncio
    async def test_iter_documents_excludes_real_vector_field_when_not_requested(self, tmp_path: Path) -> None:
        # When embeddings aren't requested, the scan excludes the vector field
        # to keep scroll payloads small (count()/iter() never need it). The
        # exclusion must target the real write field, else large vectors keep
        # streaming on every call.
        backend = _make_backend(tmp_path)
        fake_hits = [{"_id": "x", "_source": {"text": "c", "metadata": {"k": "v"}}}]
        captured: dict = {}

        def _fake_scan(_client, **kwargs):
            captured.update(kwargs)
            return (hit for hit in fake_hits)

        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch", MagicMock()),
            patch("opensearchpy.helpers.scan", side_effect=_fake_scan),
        ):
            _ = backend.vector_store
            batches = [batch async for batch in backend.iter_documents(include_embeddings=False)]

        docs = [doc for batch in batches for doc in batch]
        assert docs[0].embedding is None
        assert captured.get("_source_excludes") == ["vector_field"]

    @pytest.mark.asyncio
    async def test_iter_documents_excludes_both_fields_for_legacy_config(self, tmp_path: Path) -> None:
        # With a legacy ``chunk_embedding`` config the scan must exclude both
        # the configured name and LangChain's real field, else the (large)
        # ``vector_field`` vector keeps streaming on every count()/iter().
        backend = _make_backend(
            tmp_path,
            backend_config={"index_name": "test_index", "vector_field": "chunk_embedding"},
        )
        fake_hits = [{"_id": "x", "_source": {"text": "c", "metadata": {"k": "v"}}}]
        captured: dict = {}

        def _fake_scan(_client, **kwargs):
            captured.update(kwargs)
            return (hit for hit in fake_hits)

        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch", MagicMock()),
            patch("opensearchpy.helpers.scan", side_effect=_fake_scan),
        ):
            _ = backend.vector_store
            _ = [batch async for batch in backend.iter_documents(include_embeddings=False)]

        assert captured.get("_source_excludes") == ["chunk_embedding", "vector_field"]


class TestOpenSearchSimilaritySearchFilterHandling:
    """Pin the ``filter`` kwarg behaviour of ``similarity_search``.

    LangChain's ``OpenSearchVectorSearch`` forwards ``filter`` straight into
    the k-NN query body. Sending ``"filter": null`` makes OpenSearch reject
    the request with ``x_content_parse_exception: [knn] filter doesn't
    support values of type: VALUE_NULL``. If the override regresses and
    forwards ``filter=None`` (or an empty dict), every KB retrieval against
    OpenSearch would fail — silently looking like 'no results' to any
    component that swallows the error downstream. These tests guard the
    canonical case Langflow itself relies on at
    ``components/files_and_knowledge/retrieval.py``, which never passes a
    filter at all.
    """

    @pytest.mark.asyncio
    async def test_filter_none_is_dropped_from_call(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path)
        fake_vs = MagicMock()
        fake_vs.asimilarity_search = AsyncMock(return_value=[])
        backend._vector_store = fake_vs

        await backend.similarity_search(query="hi", k=3)

        kwargs = fake_vs.asimilarity_search.call_args.kwargs
        assert kwargs == {"query": "hi", "k": 3}
        assert "filter" not in kwargs

    @pytest.mark.asyncio
    async def test_filter_empty_dict_is_dropped_from_call(self, tmp_path: Path) -> None:
        # An empty dict is "no filter requested" — must not reach OpenSearch
        # either, since the k-NN parser also rejects empty objects.
        backend = _make_backend(tmp_path)
        fake_vs = MagicMock()
        fake_vs.asimilarity_search = AsyncMock(return_value=[])
        backend._vector_store = fake_vs

        await backend.similarity_search(query="hi", k=3, filter={})

        assert "filter" not in fake_vs.asimilarity_search.call_args.kwargs

    @pytest.mark.asyncio
    async def test_filter_truthy_is_forwarded(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path)
        fake_vs = MagicMock()
        fake_vs.asimilarity_search = AsyncMock(return_value=[])
        backend._vector_store = fake_vs

        clause = {"bool": {"must": [{"term": {"metadata.session_id": "s1"}}]}}
        await backend.similarity_search(query="hi", k=3, filter=clause)

        kwargs = fake_vs.asimilarity_search.call_args.kwargs
        assert kwargs["filter"] == clause

    @pytest.mark.asyncio
    async def test_with_scores_routes_to_score_method_and_drops_none_filter(self, tmp_path: Path) -> None:
        # When the caller asks for scores we use ``asimilarity_search_with_score``;
        # the filter handling must apply identically on that branch.
        backend = _make_backend(tmp_path)
        fake_vs = MagicMock()
        fake_vs.asimilarity_search_with_score = AsyncMock(return_value=[])
        backend._vector_store = fake_vs

        await backend.similarity_search(query="hi", k=2, with_scores=True)

        kwargs = fake_vs.asimilarity_search_with_score.call_args.kwargs
        assert kwargs == {"query": "hi", "k": 2}
        assert "filter" not in kwargs
