"""Every Search Type label a dropdown offers must reach its own LangChain search type.

The dropdown labels and ``_map_search_type`` used to be typed separately, and a label
that drifted from its branch silently fell through to the default (Cassandra Graph's
"MMR traversal" ran as plain similarity that way). The expected tables below are typed
out on purpose, not imported from the components: saved flows store these labels, so
a renamed label or a changed target must fail here.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from lfx_datastax.components.cassandra.cassandra import CassandraVectorStoreComponent
from lfx_datastax.components.datastax.astradb_graph import AstraDBGraphVectorStoreComponent
from lfx_datastax.components.datastax.astradb_vectorstore import AstraDBVectorStoreComponent
from lfx_datastax.components.datastax.hcd import HCDVectorStoreComponent

BASIC_SEARCH_TYPES = {
    "Similarity": "similarity",
    "Similarity with score threshold": "similarity_score_threshold",
    "MMR (Max Marginal Relevance)": "mmr",
}
GRAPH_SEARCH_TYPES = {
    **BASIC_SEARCH_TYPES,
    "Graph Traversal": "traversal",
    "MMR (Max Marginal Relevance) Graph Traversal": "mmr_traversal",
}
EXPECTED = {
    CassandraVectorStoreComponent: (BASIC_SEARCH_TYPES, "Similarity"),
    HCDVectorStoreComponent: (BASIC_SEARCH_TYPES, "Similarity"),
    AstraDBVectorStoreComponent: (BASIC_SEARCH_TYPES, "Similarity"),
    AstraDBGraphVectorStoreComponent: (GRAPH_SEARCH_TYPES, "MMR (Max Marginal Relevance) Graph Traversal"),
}


def _dropdown(component_class):
    return next(field for field in component_class.inputs if field.name == "search_type")


def _map(component_class, label):
    """Return the mapped search type and the warnings the component logged on the way."""
    component = component_class()
    component.search_type = label
    with patch(f"{component_class.__module__}.logger", create=True) as logger:
        search_type = component._map_search_type()
    warnings = [call.args[0] % call.args[1:] for call in logger.warning.call_args_list]
    return search_type, warnings


@pytest.mark.parametrize(
    ("component_class", "label"),
    [(cls, label) for cls in EXPECTED for label in _dropdown(cls).options],
    ids=lambda value: value.__name__ if isinstance(value, type) else value,
)
def test_should_map_every_dropdown_option_to_its_own_search_type(component_class, label):
    expected_table, _ = EXPECTED[component_class]

    search_type, warnings = _map(component_class, label)

    assert search_type == expected_table[label]
    assert warnings == [], "a label the dropdown offers must not be treated as unknown"


@pytest.mark.parametrize("component_class", list(EXPECTED), ids=lambda cls: cls.__name__)
def test_should_offer_exactly_the_saved_labels_in_order_with_the_same_default(component_class):
    expected_table, expected_default = EXPECTED[component_class]
    dropdown = _dropdown(component_class)

    assert dropdown.options == list(expected_table)
    assert dropdown.value == expected_default


@pytest.mark.parametrize("component_class", list(EXPECTED), ids=lambda cls: cls.__name__)
@pytest.mark.parametrize("label", ["Unknown mode", "", "similarity", "Graph traversal"])
def test_should_fall_back_to_similarity_and_warn_when_the_label_is_unknown(component_class, label):
    """Lower-case and near-miss labels are unknown too: the lookup is exact, as saved flows are."""
    search_type, warnings = _map(component_class, label)

    assert search_type == "similarity"
    assert len(warnings) == 1
    assert repr(label) in warnings[0]
