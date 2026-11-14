"""Cassandra Graph search results from langchain-community's real search code (LE-3341).

``test_cassandra_graph_search_type.py`` checks the arguments the component sends. These tests
check what comes back: ``traversal_search``, ``ammr_traversal_search`` and ``MmrHelper`` run as
shipped, and only the CQL layer (``CassandraVectorStore``) is an in-memory fake. If a
langchain-community upgrade changes MMR traversal's depth or threshold handling, these fail.
The ``test_component_*`` tests build the component from flow inputs, so the store construction runs too.
"""

from __future__ import annotations

import math
from unittest.mock import patch

import langchain_community.graph_vectorstores.cassandra as lc_cassandra
import numpy as np
import pytest
from langchain_community.graph_vectorstores import CassandraGraphVectorStore
from langchain_community.graph_vectorstores.base import Node
from langchain_community.graph_vectorstores.links import Link
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.schema.data import Data
from lfx_datastax.components.cassandra.cassandra_graph import CassandraGraphVectorStoreComponent

QUERY = "cassandra graph traversal"

# root -> hop -> hop2, with 100 decoys closer to the query than hop. The decoys fill fetch_k=100,
# so hop and hop2 are reachable only by following edges.
CHAIN_TABLE = {
    QUERY: [1, 0, 0],
    "root": [1, 0.1, 0],
    "hop": [0.3, -0.95, 0],
    "hop2": [0.2, -0.9, 0.3],
    **{f"decoy{i}": [1, 0.1 + i * 1e-4, 1e-3] for i in range(100)},
}
CHAIN_LINKS = {
    "root": [Link.outgoing("kw", "t1")],
    "hop": [Link.incoming("kw", "t1"), Link.outgoing("kw", "t2")],
    "hop2": [Link.incoming("kw", "t2")],
}
CHAIN_TEXTS = [text for text in CHAIN_TABLE if text != QUERY]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True)) / (math.hypot(*a) * math.hypot(*b))


class _FakeSession:
    def prepare(self, query: str) -> str:
        return query


class _InMemoryCassandraVectorStore:
    """Just enough of ``langchain_community.vectorstores.cassandra.Cassandra``: cosine ANN, filter, get-by-id."""

    def __init__(self, *, embedding: Embeddings, **_kwargs):
        self.embedding = embedding
        self.session = _FakeSession()
        self.rows: dict[str, tuple[Document, list[float]]] = {}

    @staticmethod
    def _matches(doc: Document, metadata_filter: dict | None) -> bool:
        return all(doc.metadata.get(k) == v for k, v in (metadata_filter or {}).items())

    @staticmethod
    def _copy(doc: Document) -> Document:
        return Document(page_content=doc.page_content, metadata=dict(doc.metadata), id=doc.id)

    def add_documents(self, docs: list[Document], ids: list[str]) -> list[str]:
        vectors = self.embedding.embed_documents([d.page_content for d in docs])
        for doc, doc_id, vector in zip(docs, ids, vectors, strict=True):
            self.rows[doc_id] = (
                Document(page_content=doc.page_content, metadata=dict(doc.metadata), id=doc_id),
                vector,
            )
        return ids

    def _nearest(self, embedding: list[float], k: int, metadata_filter: dict | None):
        hits = [(d, v, i) for i, (d, v) in self.rows.items() if self._matches(d, metadata_filter)]
        hits.sort(key=lambda hit: _cosine(embedding, hit[1]), reverse=True)
        return [(self._copy(d), v, i) for d, v, i in hits[:k]]

    def similarity_search(self, query: str, k: int = 4, filter=None, **_):  # noqa: A002
        return [d for d, _, _ in self._nearest(self.embedding.embed_query(query), k, filter)]

    async def asimilarity_search_with_embedding_id_by_vector(self, embedding, k=4, filter=None, **_):  # noqa: A002
        return self._nearest(embedding, k, filter)

    async def ametadata_search(self, filter=None, n=5):  # noqa: A002
        return [self._copy(d) for d, _ in self.rows.values() if self._matches(d, filter)][:n]

    async def aget_by_document_id(self, document_id: str) -> Document | None:
        row = self.rows.get(document_id)
        return self._copy(row[0]) if row else None


class _TableEmbeddings(Embeddings):
    def __init__(self, table: dict[str, list[float]]):
        self.table = table

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.table[t] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.table[text]


@pytest.fixture
def offline_cassandra():
    """Swap the CQL layer for the in-memory fake and skip cassio's cluster connection."""
    with (
        patch.object(lc_cassandra, "CassandraVectorStore", _InMemoryCassandraVectorStore),
        patch("cassio.init") as cassio_init,
    ):
        yield cassio_init


@pytest.fixture
def real_store_factory(offline_cassandra):  # noqa: ARG001
    return lambda table: CassandraGraphVectorStore(
        embedding=_TableEmbeddings(table), keyspace="ks", table_name="graph_table"
    )


def _search(store: CassandraGraphVectorStore, option: str, depth: int = 1) -> list[str]:
    component = CassandraGraphVectorStoreComponent()
    component.search_type = option
    component.search_query = QUERY
    component.number_of_results = 4
    component.search_score_threshold = 0
    component.depth = depth
    component.search_filter = {}
    component._cached_vector_store = store  # check_cached_vector_store returns it as is
    return [data.text for data in component.search_documents()]


@pytest.fixture
def chain_store(real_store_factory):
    store = real_store_factory(CHAIN_TABLE)
    store.add_nodes(Node(id=text, text=text, links=CHAIN_LINKS.get(text, [])) for text in CHAIN_TEXTS)
    return store


@pytest.mark.parametrize(
    ("depth", "expected"),
    [(0, ["root"]), (1, ["hop", "root"]), (2, ["hop", "hop2", "root"])],
)
@pytest.mark.parametrize("option", ["Traversal", "MMR traversal"])
def test_should_reach_the_same_graph_nodes_for_traversal_and_mmr_traversal(chain_store, option, depth, expected):
    reached = [text for text in _search(chain_store, option, depth) if not text.startswith("decoy")]

    assert sorted(reached) == expected


def test_should_return_all_k_documents_for_mmr_traversal_with_default_threshold(real_store_factory):
    """Near-duplicates get negative MMR scores; a threshold of 0 used to stop after the first."""
    table = {
        QUERY: [1, 1, 1],
        "a1": [1, 1, 0],
        "a2": [1, 1, 0.05],
        "a3": [1, 0.97, 0],
        "a4": [0.97, 1, 0.02],
    }
    store = real_store_factory(table)
    store.add_documents([Document(page_content=text) for text in table if text != QUERY])

    assert sorted(_search(store, "MMR traversal")) == ["a1", "a2", "a3", "a4"]


def _built_component(option: str, depth: int = 1) -> CassandraGraphVectorStoreComponent:
    """The component as a flow configures it: Data with link metadata in, a search query set."""
    return CassandraGraphVectorStoreComponent(
        database_ref="127.0.0.1",
        username="cassandra",
        token="secret",  # noqa: S106
        keyspace="ks",
        table_name="graph_table",
        setup_mode="Sync",
        cluster_kwargs={},
        embedding=_TableEmbeddings(CHAIN_TABLE),
        ingest_data=[Data(data={"text": text, "links": CHAIN_LINKS.get(text, [])}) for text in CHAIN_TEXTS],
        search_query=QUERY,
        search_type=option,
        number_of_results=4,
        depth=depth,
        search_score_threshold=0,
        search_filter={},
    )


def _component_search(option: str, depth: int = 1) -> list[Data]:
    component = _built_component(option, depth)
    assert isinstance(component.build_vector_store(), CassandraGraphVectorStore)
    return component.search_documents()


def _as_text(data: Data) -> str:
    """What a downstream Parser/Chat Output does with each result."""
    # Imported late: with langflow installed, importing lfx.helpers before lfx_datastax hits a circular import.
    from lfx.helpers.data import safe_convert

    return safe_convert(data)


def _graph_texts(results: list[Data]) -> list[str]:
    return sorted(data.text for data in results if not data.text.startswith("decoy"))


@pytest.mark.parametrize(("depth", "expected"), [(0, ["root"]), (1, ["hop", "root"])])
@pytest.mark.parametrize("option", ["Traversal", "MMR traversal"])
def test_component_should_follow_ingested_links_for_traversal_options(offline_cassandra, option, depth, expected):
    results = _component_search(option, depth)

    assert _graph_texts(results) == expected
    offline_cassandra.assert_called_once()


@pytest.mark.usefixtures("offline_cassandra")
def test_component_should_return_all_k_results_for_mmr_traversal_with_numpy_scores_that_serialize():
    results = _component_search("MMR traversal")

    assert len(results) == 4
    assert all(isinstance(data.data["similarity_score"], np.floating) for data in results)
    for data in results:
        assert '"similarity_score"' in _as_text(data)


@pytest.mark.usefixtures("offline_cassandra")
def test_component_should_not_follow_links_for_similarity():
    results = _component_search("Similarity")

    assert len(results) == 4
    assert results[0].text == "root"
    assert "hop" not in _graph_texts(results)
    assert all(_as_text(data) for data in results)


@pytest.mark.usefixtures("offline_cassandra")
def test_component_should_raise_clear_error_for_similarity_with_score_threshold():
    with pytest.raises(ValueError, match="Cassandra Graph doesn't support 'Similarity with score threshold'"):
        _component_search("Similarity with score threshold")


def _raise_key_error(missing: str):
    def similarity_search(*_args, **_kwargs):
        raise KeyError(missing)

    return similarity_search


@pytest.mark.usefixtures("offline_cassandra")
def test_component_should_ask_to_ingest_through_langflow_when_rows_lack_content(monkeypatch):
    """A table written outside Langflow/LangChain has no 'content' field to read back."""
    monkeypatch.setattr(_InMemoryCassandraVectorStore, "similarity_search", _raise_key_error("content"))

    with pytest.raises(ValueError, match="You should ingest data through Langflow") as exc:
        _component_search("Similarity")

    assert "does not contain a field name 'content'" in str(exc.value)


@pytest.mark.usefixtures("offline_cassandra")
def test_component_should_keep_other_key_errors_unchanged(monkeypatch):
    monkeypatch.setattr(_InMemoryCassandraVectorStore, "similarity_search", _raise_key_error("body_blob"))

    with pytest.raises(KeyError, match="body_blob"):
        _component_search("Similarity")
