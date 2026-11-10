"""Cassandra Graph must build its store and search the way each dropdown option promises.

The dropdown offers ``"MMR traversal"`` but ``_map_search_type`` compared against
``"MMR Traversal"``, so picking it silently ran plain ``traversal``. The options are read
from the component's own dropdown so a label change cannot drift past this test.

LE-3341: the store was built with ``node_table=`` (not a langchain-community 0.4 parameter),
``score_threshold=0`` cut MMR traversal results short, MMR traversal's depth was one hop short
of traversal's, and "Similarity with score threshold" failed with a bare NotImplementedError.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest
from langchain_community.graph_vectorstores import CassandraGraphVectorStore as RealCassandraGraphVectorStore
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.schema.data import Data
from lfx_datastax.components.cassandra import cassandra_graph
from lfx_datastax.components.cassandra.cassandra_graph import CassandraGraphVectorStoreComponent

EXPECTED_SEARCH_TYPES = {
    "Traversal": "traversal",
    "MMR traversal": "mmr_traversal",
    "Similarity": "similarity",
    "Similarity with score threshold": "similarity_score_threshold",
    "MMR (Max Marginal Relevance)": "mmr",
}

SEARCH_TYPE_OPTIONS = next(i for i in CassandraGraphVectorStoreComponent.inputs if i.name == "search_type").options


def _component(search_type: str) -> CassandraGraphVectorStoreComponent:
    component = CassandraGraphVectorStoreComponent()
    component.search_type = search_type
    component.number_of_results = 4
    component.search_score_threshold = 0
    component.depth = 1
    component.search_filter = {}
    return component


def test_should_cover_every_dropdown_option():
    assert sorted(SEARCH_TYPE_OPTIONS) == sorted(EXPECTED_SEARCH_TYPES)


@pytest.mark.parametrize("option", SEARCH_TYPE_OPTIONS)
def test_should_map_each_option_to_its_own_search_type(option: str):
    component = _component(option)

    assert component._map_search_type() == EXPECTED_SEARCH_TYPES[option]
    assert component.get_retriever_kwargs()["search_type"] == EXPECTED_SEARCH_TYPES[option]


@pytest.mark.parametrize("unknown", ["MMR Traversal", "", None])
def test_should_fall_back_to_traversal_and_warn_when_search_type_is_unknown(unknown, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(cassandra_graph.logger, "warning", warnings.append)

    assert _component(unknown)._map_search_type() == "traversal"
    assert len(warnings) == 1
    assert repr(unknown) in warnings[0]


def test_should_not_warn_when_search_type_is_known(monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(cassandra_graph.logger, "warning", warnings.append)

    _component("Traversal")._map_search_type()

    assert warnings == []


MODULE_STORE = "lfx_datastax.components.cassandra.cassandra_graph.CassandraGraphVectorStore"
ALL_LABELS = list(EXPECTED_SEARCH_TYPES)
THRESHOLD_LABEL = "Similarity with score threshold"


def _named_params(func) -> set[str]:
    return {
        name
        for name, param in inspect.signature(func).parameters.items()
        if param.kind not in (param.VAR_KEYWORD, param.VAR_POSITIONAL)
    }


def _connectable_component(*, with_documents: bool) -> CassandraGraphVectorStoreComponent:
    component = _component("Traversal")
    component.database_ref = "127.0.0.1"
    component.username = "user"
    component.token = "token"  # noqa: S105
    component.keyspace = "test_keyspace"
    component.table_name = "graph_table"
    component.setup_mode = "Sync"
    component.cluster_kwargs = {}
    component.embedding = MagicMock(spec=Embeddings)
    component.ingest_data = [Data(text="hello world")] if with_documents else []
    return component


@pytest.mark.parametrize("with_documents", [True, False])
def test_should_build_store_with_kwargs_the_real_langchain_signature_accepts(with_documents: bool):
    """``node_table=`` is not a parameter of CassandraGraphVectorStore, so every search failed."""
    component = _connectable_component(with_documents=with_documents)
    # from_documents forwards **kwargs into __init__, so a kwarg is only valid if one of them names it.
    accepted = _named_params(RealCassandraGraphVectorStore.__init__)
    if with_documents:
        accepted |= _named_params(RealCassandraGraphVectorStore.from_documents)

    with patch("cassio.init"), patch(MODULE_STORE) as store_cls:
        component.build_vector_store()

    call = store_cls.from_documents if with_documents else store_cls
    call.assert_called_once()
    kwargs = call.call_args.kwargs
    assert set(kwargs) <= accepted, f"unknown kwargs: {set(kwargs) - accepted}"
    assert kwargs["table_name"] == "graph_table"
    assert kwargs["keyspace"] == "test_keyspace"


def _searchable(option: str) -> tuple[CassandraGraphVectorStoreComponent, MagicMock]:
    component = _component(option)
    component.search_query = "what about cats?"
    store = MagicMock()
    store.search.return_value = [Document(page_content="cats")]
    # build_vector_store is wrapped by check_cached_vector_store, which returns a cached store as is.
    component._cached_vector_store = store
    return component, store


def _sent_search_args(option: str, depth: int = 1) -> list[dict]:
    """Search kwargs from the retriever and, where the search can run, from search_documents."""
    component, store = _searchable(option)
    component.depth = depth
    component.search_score_threshold = 0.5
    sent = [component.get_retriever_kwargs()["search_kwargs"]]
    if option != THRESHOLD_LABEL:
        component.search_documents()
        sent.append({k: v for k, v in store.search.call_args.kwargs.items() if k not in ("query", "search_type")})
    return sent


@pytest.mark.parametrize("option", ALL_LABELS)
def test_should_send_score_threshold_only_for_similarity_with_score_threshold(option: str):
    """A default threshold of 0 made MMR traversal stop at negative MMR scores (1 of 4 docs)."""
    for args in _sent_search_args(option):
        if option == THRESHOLD_LABEL:
            assert args["score_threshold"] == 0.5
        else:
            assert "score_threshold" not in args


@pytest.mark.parametrize("option", ALL_LABELS)
@pytest.mark.parametrize("depth", [0, 1, 3])
def test_should_add_one_to_depth_only_for_mmr_traversal(option: str, depth: int):
    """mmr_traversal never follows an edge at depth=1, while traversal does one hop."""
    expected = depth + 1 if option == "MMR traversal" else depth

    for args in _sent_search_args(option, depth):
        assert args["depth"] == expected


def test_should_keep_filter_alongside_adjusted_depth_and_drop_empty_filter_entries():
    component = _component("MMR traversal")
    component.search_filter = {"topic": "cats", "": "x", "empty": ""}

    args = component.get_retriever_kwargs()["search_kwargs"]

    assert args == {"k": 4, "depth": 2, "filter": {"topic": "cats"}}


@pytest.mark.parametrize("option", [label for label in ALL_LABELS if label != THRESHOLD_LABEL])
def test_should_search_with_mapped_type_and_return_data(option: str):
    component, store = _searchable(option)

    result = component.search_documents()

    store.search.assert_called_once()
    kwargs = store.search.call_args.kwargs
    assert kwargs["search_type"] == EXPECTED_SEARCH_TYPES[option]
    assert [d.text for d in result] == ["cats"]


def test_should_raise_clear_error_for_similarity_with_score_threshold():
    component, store = _searchable(THRESHOLD_LABEL)

    with pytest.raises(ValueError, match="doesn't support 'Similarity with score threshold'") as exc:
        component.search_documents()

    assert "'Similarity'" in str(exc.value)
    assert "'MMR traversal'" in str(exc.value)
    store.search.assert_not_called()


def test_should_search_with_traversal_when_label_is_unknown(monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(cassandra_graph.logger, "warning", warnings.append)
    component, store = _searchable("MMR Traversal")

    component.search_documents()

    assert store.search.call_args.kwargs["search_type"] == "traversal"
    assert store.search.call_args.kwargs["depth"] == 1
    assert len(warnings) == 1


@pytest.mark.parametrize("query", ["", "   ", "\n\t", None])
def test_should_return_nothing_without_searching_when_query_is_blank(query):
    component, store = _searchable("MMR traversal")
    component.search_query = query

    assert component.search_documents() == []
    store.search.assert_not_called()
