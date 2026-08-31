import json
from importlib.metadata import version
from pathlib import Path

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
