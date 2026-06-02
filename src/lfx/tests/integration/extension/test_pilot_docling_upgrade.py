"""Integration tests for migrating in-tree Docling components to lfx-docling."""

from __future__ import annotations

from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"

COMPONENTS = [
    ("ChunkDoclingDocumentComponent", "chunk_docling_document"),
    ("DoclingInlineComponent", "docling_inline"),
    ("DoclingRemoteComponent", "docling_remote"),
    ("ExportDoclingDocumentComponent", "export_docling_document"),
]


@pytest.fixture(scope="module")
def migration_table():
    table, error = load_migration_table(TABLE_PATH)
    assert error is None, f"failed to load migration table: {error}"
    assert table is not None
    return table


def _saved_flow_node(node_id: str, type_value: str) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": type_value,
            "node": {"template": {}},
        },
    }


def _saved_flow(type_value: str) -> dict:
    return {"data": {"nodes": [_saved_flow_node("docling-1", type_value)], "edges": []}}


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "_module_name"), COMPONENTS)
def test_legacy_bare_name_flow_upgrades(migration_table, class_name: str, _module_name: str) -> None:
    from lfx.extension.migration.rewrite import migrate_flow_payload

    target = f"ext:docling:{class_name}@official"
    flow = _saved_flow(class_name)

    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == target
    assert report.records[0].legacy_form_kind == "bare_class_name"


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "module_name"), COMPONENTS)
def test_legacy_import_path_flow_upgrades(migration_table, class_name: str, module_name: str) -> None:
    from lfx.extension.migration.rewrite import migrate_flow_payload

    target = f"ext:docling:{class_name}@official"
    flow = _saved_flow(f"lfx.components.docling.{module_name}.{class_name}")

    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == target
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "_module_name"), COMPONENTS)
def test_short_import_path_flow_upgrades(migration_table, class_name: str, _module_name: str) -> None:
    from lfx.extension.migration.rewrite import migrate_flow_payload

    target = f"ext:docling:{class_name}@official"
    flow = _saved_flow(f"lfx.components.docling.{class_name}")

    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == target


@pytest.mark.integration
def test_unrelated_component_is_not_rewritten(migration_table) -> None:
    """A node whose type is not a Docling component must be left untouched.

    Guards against over-broad rewrites in ``migrate_flow_payload``: only the
    four Docling identifiers should migrate, never an unrelated/unknown name.
    """
    from lfx.extension.migration.rewrite import migrate_flow_payload

    original_type = "TotallyUnrelatedComponent"
    flow = _saved_flow(original_type)

    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 0
    assert flow["data"]["nodes"][0]["data"]["type"] == original_type


@pytest.mark.integration
def test_lfx_docling_distribution_is_importable() -> None:
    try:
        import lfx_docling
    except ImportError:
        pytest.skip("lfx-docling not installed in this test environment")

    for class_name, _module_name in COMPONENTS:
        assert getattr(lfx_docling, class_name).__name__ == class_name


@pytest.mark.integration
def test_bundle_loads_and_resolves_runtime_classes() -> None:
    try:
        import lfx_docling
    except ImportError:
        pytest.skip("lfx-docling not installed in this test environment")

    from lfx.extension import SLOT_OFFICIAL, load_extension

    result = load_extension(Path(lfx_docling.__file__).parent, slot=SLOT_OFFICIAL, distribution="lfx-docling")

    assert result.ok, [e.code for e in result.errors]
    loaded_by_name = {component.class_name: component for component in result.components}

    for class_name, _module_name in COMPONENTS:
        loaded = loaded_by_name[class_name]
        assert loaded.bundle == "docling"
        assert loaded.slot == SLOT_OFFICIAL
        assert loaded.namespaced_id == f"ext:docling:{class_name}@official"
