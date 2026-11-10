"""Cassandra Graph search results from langchain-community's real search code (LE-3341).

``test_cassandra_graph_search_type.py`` checks the arguments the component sends. These tests
check what comes back: ``traversal_search``, ``ammr_traversal_search`` and ``MmrHelper`` run as
shipped, and only the CQL layer (``CassandraVectorStore``) is an in-memory fake. If a
langchain-community upgrade changes MMR traversal's depth or threshold handling, these fail.
"""

from __future__ import annotations

import math
from unittest.mock import patch

import langchain_community.graph_vectorstores.cassandra as lc_cassandra
import pytest
from langchain_community.graph_vectorstores import CassandraGraphVectorStore
from langchain_community.graph_vectorstores.base import Node
from langchain_community.graph_vectorstores.links import Link
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx_datastax.components.cassandra.cassandra_graph import CassandraGraphVectorStoreComponent

QUERY = "cassandra graph traversal"


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
def real_store_factory():
    with patch.object(lc_cassandra, "CassandraVectorStore", _InMemoryCassandraVectorStore):
        yield lambda table: CassandraGraphVectorStore(
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
    """root -> hop -> hop2, with 100 decoys closer to the query than hop.

    The decoys fill fetch_k=100, so hop and hop2 are reachable only by following edges.
    """
    table = {QUERY: [1, 0, 0], "root": [1, 0.1, 0], "hop": [0.3, -0.95, 0], "hop2": [0.2, -0.9, 0.3]}
    nodes = [
        Node(id="root", text="root", links=[Link.outgoing("kw", "t1")]),
        Node(id="hop", text="hop", links=[Link.incoming("kw", "t1"), Link.outgoing("kw", "t2")]),
        Node(id="hop2", text="hop2", links=[Link.incoming("kw", "t2")]),
    ]
    for i in range(100):
        table[f"decoy{i}"] = [1, 0.1 + i * 1e-4, 1e-3]
        nodes.append(Node(id=f"decoy{i}", text=f"decoy{i}"))
    store = real_store_factory(table)
    store.add_nodes(nodes)
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
