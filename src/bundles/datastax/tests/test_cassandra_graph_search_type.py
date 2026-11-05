"""Every Cassandra Graph search-type option must reach the store as its own search type.

The dropdown offers ``"MMR traversal"`` but ``_map_search_type`` compared against
``"MMR Traversal"``, so picking it silently ran plain ``traversal``. The options are read
from the component's own dropdown so a label change cannot drift past this test.
"""

from __future__ import annotations

import pytest
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


def test_should_map_mmr_traversal_to_mmr_traversal_not_traversal():
    assert _component("MMR traversal")._map_search_type() == "mmr_traversal"
