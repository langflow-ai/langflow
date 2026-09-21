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

import re
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from lfx.base.knowledge_bases.backends import OpenSearchBackend, PostgresBackend
from lfx.base.knowledge_bases.backends.opensearch import (
    DEFAULT_TEXT_FIELD,
    DEFAULT_VECTOR_FIELD,
    LEGACY_SHARED_INDEX_KEY,
    derive_index_name,
)

pytestmark = pytest.mark.usefixtures("fake_opensearchpy")

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

    def test_relevance_score_remains_higher_is_better(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path)
        assert backend.normalize_score(0.75) == 0.75

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


# OpenSearch index names: lowercase, none of ``\\ / * ? " < > | , # :`` or
# whitespace, no leading ``- _ + .``, at most 255 bytes.
_VALID_INDEX_NAME = re.compile(r"^(?![-_+.])[^A-Z\\/*?\"<>|,#:\s]{1,255}$")


class TestOpenSearchIndexIsolation:
    """Each owner's Knowledge Base / Memory Base must get its own index.

    KB names are unique per user, not globally. Deriving the index from
    ``kb_name`` alone made two users' same-named KBs share one index, so each
    could read, count, and delete the other's chunks. The index is now scoped
    by owner (the same name pgvector gives the KB's table) unless an explicit
    ``index_name`` override is configured.
    """

    def _make(self, kb_path: Path, kb_name: str, backend_config: dict, user_id: UUID | str | None) -> OpenSearchBackend:
        backend = OpenSearchBackend(
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            user_id=user_id,
        )
        backend._resolved_url = "https://example.local:9200"
        backend._resolved_username = "admin"
        backend._resolved_password = "secret"  # noqa: S105 — test fixture  # pragma: allowlist secret
        backend._secrets_resolved = True
        return backend

    def _built_index(self, backend: OpenSearchBackend) -> str:
        fake_wrapper = MagicMock(name="OpenSearchVectorSearch")
        with (
            patch("opensearchpy.OpenSearch", return_value=MagicMock()),
            patch("langchain_community.vectorstores.OpenSearchVectorSearch", fake_wrapper),
        ):
            _ = backend.vector_store
        return fake_wrapper.call_args.kwargs["index_name"]

    def test_same_kb_name_for_different_owners_gets_different_indexes(self, tmp_path: Path) -> None:
        index_a = self._built_index(self._make(tmp_path, "docs", {}, uuid4()))
        index_b = self._built_index(self._make(tmp_path, "docs", {}, uuid4()))
        assert index_a != index_b

    def test_index_is_owner_scoped_when_unset(self, tmp_path: Path) -> None:
        owner = uuid4()
        backend = self._make(tmp_path, "chat_memory_a1b2c3d4", {"url_variable": "OPENSEARCH_URL"}, owner)
        index = self._built_index(backend)
        assert index == derive_index_name("chat_memory_a1b2c3d4", owner)
        assert backend._os_index == index
        assert re.fullmatch(r"lf_[0-9a-f]{24}", index)

    def test_string_and_uuid_owner_ids_resolve_to_the_same_index(self, tmp_path: Path) -> None:
        owner = uuid4()
        from_uuid = self._built_index(self._make(tmp_path, "docs", {}, owner))
        from_string = self._built_index(self._make(tmp_path, "docs", {}, str(owner).upper()))
        assert from_uuid == from_string

    def test_matches_pgvector_collection_name(self, tmp_path: Path) -> None:
        owner = uuid4()
        postgres = PostgresBackend(kb_name="Team Docs", user_id=owner)
        assert self._built_index(self._make(tmp_path, "Team Docs", {}, owner)) == postgres.collection_name

    def test_missing_owner_fails_closed(self, tmp_path: Path) -> None:
        # No owner must never fall back to a name other users could also get.
        with pytest.raises(ValueError, match="valid user_id"):
            self._built_index(self._make(tmp_path, "docs", {}, None))

    def test_explicit_index_name_overrides_derivation(self, tmp_path: Path) -> None:
        # Operators pointing a KB at an externally-managed index keep control,
        # and migrated KBs keep reading the index they already wrote to.
        backend = self._make(tmp_path, "docs", {"index_name": "external_index"}, uuid4())
        assert self._built_index(backend) == "external_index"
        assert backend._os_index == "external_index"

    def test_explicit_index_name_does_not_require_an_owner(self, tmp_path: Path) -> None:
        backend = _make_backend(tmp_path, backend_config={"index_name": "external_index"})
        assert self._built_index(backend) == "external_index"

    def test_override_cannot_target_another_owners_scoped_index(self, tmp_path: Path) -> None:
        victim_index = derive_index_name("docs", uuid4())
        backend = self._make(tmp_path, "docs", {"index_name": victim_index}, uuid4())
        with pytest.raises(ValueError, match="reserved for owner-scoped"):
            self._built_index(backend)

    def test_override_cannot_target_scoped_index_without_an_owner(self, tmp_path: Path) -> None:
        backend = self._make(tmp_path, "docs", {"index_name": derive_index_name("docs", uuid4())}, None)
        with pytest.raises(ValueError, match="reserved for owner-scoped"):
            self._built_index(backend)

    def test_override_naming_its_own_scoped_index_is_allowed(self, tmp_path: Path) -> None:
        # A migration downgrade pins KBs to their own owner-scoped index.
        owner = uuid4()
        own_index = derive_index_name("docs", owner)
        backend = self._make(tmp_path, "docs", {"index_name": own_index}, owner)
        assert self._built_index(backend) == own_index

    def test_shared_legacy_index_marker_warns(self, tmp_path: Path) -> None:
        owner = uuid4()
        backend = self._make(tmp_path, "docs", {LEGACY_SHARED_INDEX_KEY: "docs"}, owner)
        with patch("lfx.base.knowledge_bases.backends.opensearch.logger") as fake_logger:
            index = self._built_index(backend)
        assert index == derive_index_name("docs", owner)
        fake_logger.warning.assert_called_once()
        assert "docs" in fake_logger.warning.call_args.args

    def test_no_warning_without_the_marker(self, tmp_path: Path) -> None:
        backend = self._make(tmp_path, "docs", {}, uuid4())
        with patch("lfx.base.knowledge_bases.backends.opensearch.logger") as fake_logger:
            self._built_index(backend)
        fake_logger.warning.assert_not_called()


@pytest.mark.parametrize(
    "kb_name",
    [
        "docs",
        "Docs",
        "My KB!",
        "  Docs 2024  ",
        "_leading",
        "..",
        "",
        "日本語のナレッジ",
        pytest.param("a" * 1000, id="1000-chars"),
        'bad\\/*?"<>|,#: name',
    ],
)
def test_derived_index_name_is_always_a_valid_opensearch_name(kb_name: str) -> None:
    index = derive_index_name(kb_name, uuid4())
    assert _VALID_INDEX_NAME.fullmatch(index), index
    assert len(index.encode()) <= 255


def test_kb_names_that_sanitized_to_one_legacy_index_now_differ() -> None:
    # "Docs" and "docs" (or "a:b" and "a#b") used to share an index even for one owner.
    owner = uuid4()
    assert derive_index_name("Docs", owner) != derive_index_name("docs", owner)
    assert derive_index_name("a:b", owner) != derive_index_name("a#b", owner)


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
    async def test_flat_filter_is_translated_to_bool_dsl(self, tmp_path: Path) -> None:
        # Callers hand the backend the portable flat ``{key: value}`` shape
        # (the same contract Chroma reads as ``$eq``). The backend must
        # translate it into OpenSearch bool DSL — LangChain injects a
        # non-empty ``filter`` into the k-NN query and a flat dict would be
        # rejected / silently match nothing. Regressing this breaks the
        # default session-filtered Memory Base retrieval path.
        backend = _make_backend(tmp_path)
        fake_vs = MagicMock()
        fake_vs.asimilarity_search = AsyncMock(return_value=[])
        backend._vector_store = fake_vs

        await backend.similarity_search(query="hi", k=3, filter={"session_id": "s1"})

        forwarded = fake_vs.asimilarity_search.call_args.kwargs["filter"]
        assert forwarded == {
            "bool": {
                "must": [
                    {
                        "bool": {
                            "should": [
                                {"match": {"session_id": "s1"}},
                                {"match": {"metadata.session_id": "s1"}},
                            ],
                            "minimum_should_match": 1,
                        }
                    }
                ]
            }
        }
        # The retrieval filter and the delete rollback path must produce the
        # exact same translation so they can never drift.
        assert forwarded == backend._translate_where({"session_id": "s1"})

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


class TestOpenSearchSSRFProtection:
    """The cluster URL is tenant-controlled, so the backend must not dial it blindly.

    Regression guard for the KB OpenSearch SSRF (CWE-918): the URL comes from a
    per-user Langflow variable whose value is stored verbatim, and
    ``OpenSearch(hosts=[url]).info()`` otherwise fetches whatever host:port/path
    the tenant chose — including loopback, RFC1918, and the cloud-metadata
    address — even with ``LANGFLOW_SSRF_PROTECTION_ENABLED=true``. The backend
    now applies the same connector SSRF policy the vector-store components use,
    inside ``_resolve_secrets`` so every path (test-connection, ingestion,
    retrieval) is covered.
    """

    @pytest.fixture
    def ssrf_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pin the SSRF knobs so the tests don't depend on ambient settings."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", raising=False)

    def _backend(self, tmp_path: Path, url: str) -> OpenSearchBackend:
        backend = OpenSearchBackend(
            kb_name="kb_ssrf",
            kb_path=tmp_path,
            backend_config={"index_name": "test_index"},
        )
        # resolve_secret is called for url, then username, then password.
        backend.resolve_secret = AsyncMock(side_effect=[url, None, None])
        return backend

    @pytest.mark.usefixtures("ssrf_env")
    async def test_resolve_secrets_blocks_cloud_metadata_url(self, tmp_path: Path) -> None:
        from lfx.utils.ssrf_protection import SSRFProtectionError

        backend = self._backend(tmp_path, "http://169.254.169.254/latest/meta-data/")
        with pytest.raises(SSRFProtectionError, match="blocked"):
            await backend._resolve_secrets()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_resolve_secrets_blocks_rfc1918_url(self, tmp_path: Path) -> None:
        from lfx.utils.ssrf_protection import SSRFProtectionError

        backend = self._backend(tmp_path, "http://10.0.0.5:9200")
        with pytest.raises(SSRFProtectionError, match="blocked"):
            await backend._resolve_secrets()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_resolve_secrets_blocks_hostname_resolving_to_private_ip(self, tmp_path: Path) -> None:
        from lfx.utils.ssrf_protection import SSRFProtectionError

        backend = self._backend(tmp_path, "http://opensearch.internal:9200")
        with (
            patch("lfx.utils.ssrf_protection.resolve_hostname", return_value=["10.1.2.3"]),
            pytest.raises(SSRFProtectionError, match="blocked"),
        ):
            await backend._resolve_secrets()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_resolve_secrets_blocks_non_http_scheme(self, tmp_path: Path) -> None:
        from lfx.utils.ssrf_protection import SSRFProtectionError

        backend = self._backend(tmp_path, "file:///etc/passwd")
        with pytest.raises(SSRFProtectionError):
            await backend._resolve_secrets()

    @pytest.mark.usefixtures("ssrf_env")
    async def test_allowlisted_internal_host_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Operators whose cluster genuinely lives on an internal network keep a
        # supported escape hatch: LANGFLOW_SSRF_ALLOWED_HOSTS.
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "10.0.0.5")
        backend = self._backend(tmp_path, "http://10.0.0.5:9200")
        await backend._resolve_secrets()
        assert backend._resolved_url == "http://10.0.0.5:9200"

    @pytest.mark.usefixtures("ssrf_env")
    async def test_test_connection_reports_ssrf_block(self, tmp_path: Path) -> None:
        # The blocked URL must surface as a failed test-connection result with
        # an accurate type — never as a dialed connection.
        backend = self._backend(tmp_path, "http://169.254.169.254:80")
        result = await backend.test_connection()
        assert result.ok is False
        assert result.details["type"] == "SSRFProtectionError"
        assert "blocked" in result.message

    @pytest.mark.usefixtures("ssrf_env")
    async def test_blocked_url_is_never_stashed_for_later_paths(self, tmp_path: Path) -> None:
        from lfx.utils.ssrf_protection import SSRFProtectionError

        backend = self._backend(tmp_path, "http://169.254.169.254:80")
        with pytest.raises(SSRFProtectionError):
            await backend._resolve_secrets()
        # A KB created against a hostile variable must not keep the SSRF alive
        # on the ingestion/retrieval paths after test-connection.
        assert getattr(backend, "_resolved_url", None) is None
