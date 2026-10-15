import json
from importlib.metadata import version
from pathlib import Path

import pytest
from lfx.components.cassandra import (
    CassandraChatMemory as CompatibilityCassandraChatMemory,
)
from lfx.components.cassandra import (
    CassandraGraphVectorStoreComponent as CompatibilityCassandraGraphVectorStoreComponent,
)
from lfx.components.cassandra import (
    CassandraVectorStoreComponent as CompatibilityCassandraVectorStoreComponent,
)
from lfx.components.cassandra.cassandra import CassandraVectorStoreComponent as CompatibilityModuleCassandraVectorStore
from lfx.components.cassandra.cassandra_chat import CassandraChatMemory as CompatibilityModuleCassandraChatMemory
from lfx.components.cassandra.cassandra_graph import (
    CassandraGraphVectorStoreComponent as CompatibilityModuleCassandraGraphVectorStore,
)
from lfx_datastax.components.cassandra import (
    CassandraChatMemory,
    CassandraGraphVectorStoreComponent,
    CassandraVectorStoreComponent,
)


def test_legacy_cassandra_imports_preserve_class_identity() -> None:
    assert CompatibilityCassandraVectorStoreComponent is CassandraVectorStoreComponent
    assert CompatibilityCassandraChatMemory is CassandraChatMemory
    assert CompatibilityCassandraGraphVectorStoreComponent is CassandraGraphVectorStoreComponent
    assert CompatibilityModuleCassandraVectorStore is CassandraVectorStoreComponent
    assert CompatibilityModuleCassandraChatMemory is CassandraChatMemory
    assert CompatibilityModuleCassandraGraphVectorStore is CassandraGraphVectorStoreComponent
    assert CassandraVectorStoreComponent.__name__ == "CassandraVectorStoreComponent"
    assert CassandraChatMemory.__name__ == "CassandraChatMemory"
    assert CassandraGraphVectorStoreComponent.__name__ == "CassandraGraphVectorStoreComponent"


def test_manifest_exposes_cassandra_as_a_separate_bundle() -> None:
    manifest_path = Path(__file__).parents[1] / "src" / "lfx_datastax" / "extension.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Assert the manifest tracks the distribution rather than a literal: the release-plan guard
    # bumps pyproject whenever releasable bundle source changes, and a hardcoded version here
    # turns every one of those bumps into a spurious failure while checking nothing real. The
    # invariant worth pinning is that extension.json and the package stay in lockstep -- bumping
    # one without the other is the actual bug.
    assert manifest["version"] == version("lfx-datastax")
    assert manifest["bundles"] == [
        {"name": "datastax", "path": "components/datastax"},
        {"name": "cassandra", "path": "components/cassandra"},
    ]


def _search_type_options() -> list[str]:
    inputs = [i for i in CassandraGraphVectorStoreComponent.inputs if getattr(i, "name", None) == "search_type"]
    assert len(inputs) == 1
    return list(inputs[0].options)


@pytest.mark.parametrize(
    ("option", "search_type"),
    [
        ("Traversal", "traversal"),
        ("MMR traversal", "mmr_traversal"),
        ("Similarity", "similarity"),
        ("Similarity with score threshold", "similarity_score_threshold"),
        ("MMR (Max Marginal Relevance)", "mmr"),
    ],
)
def test_cassandra_graph_maps_each_search_type_option(option: str, search_type: str) -> None:
    """Every Search Type dropdown option has to reach the graph search it names.

    ``_map_search_type`` compared against ``"MMR Traversal"`` while the dropdown ships
    ``"MMR traversal"`` (lower-case ``t``), so that branch was dead code and the option
    fell through to the plain-``"traversal"`` default -- the component silently ran a
    non-diversified traversal while reporting MMR in the UI and in its own logs.
    """
    assert option in _search_type_options()

    component = CassandraGraphVectorStoreComponent()
    component.search_type = option
    assert component._map_search_type() == search_type


def test_cassandra_graph_exposes_mm_traversal_to_the_retriever_contract() -> None:
    """The retriever kwargs take the same mapping, so the drift leaked there too.

    ``mmr_traversal`` is a real ``CassandraGraphVectorStore`` search type (it has a
    dedicated ``mmr_traversal_search``), so once the option is mapped the retriever
    built from this component asks for MMR as well.
    """
    component = CassandraGraphVectorStoreComponent()
    component.search_type = "MMR traversal"
    assert component.get_retriever_kwargs()["search_type"] == "mmr_traversal"
