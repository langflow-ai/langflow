from pathlib import Path

import lfx_arcmira
from lfx.extension import SLOT_OFFICIAL, load_extension
from lfx.extension.loader._plugins import installed_extension_roots
from lfx.extension.migration.loader import load_migration_table
from lfx.extension.migration.rewrite import migrate_flow_payload


def test_installed_bundle_loads_both_components():
    roots = installed_extension_roots()
    assert "lfx-arcmira" in roots
    result = load_extension(
        Path(lfx_arcmira.__file__).parent,
        slot=SLOT_OFFICIAL,
        distribution="lfx-arcmira",
    )
    assert result.ok, result.errors
    components = {component.class_name: component for component in result.components}
    assert set(components) == {"ArcmiraTranscriptSearch", "ArcmiraEntityResolve"}
    for name, component in components.items():
        assert component.bundle == "arcmira"
        assert component.slot == SLOT_OFFICIAL
        instance = component.klass()
        assert instance.name == name
        assert "api_key" in {field.name for field in instance.inputs}


def test_saved_component_ids_migrate_without_changing_inputs():
    root = Path(__file__).resolve().parents[4]
    table, error = load_migration_table(root / "src/lfx/src/lfx/extension/migration/migration_table.json")
    assert error is None
    assert table is not None
    for name in ("ArcmiraTranscriptSearch", "ArcmiraEntityResolve"):
        node = {"id": "saved-node", "type": name, "node": {"template": {"query": {"value": "climate"}}}}
        flow = {"data": {"nodes": [{"id": "saved-node", "type": "genericNode", "data": node}], "edges": []}}
        report = migrate_flow_payload(flow, table=table)
        assert report.rewritten_count == 1
        assert node["type"] == f"ext:arcmira:{name}@official"
        assert node["node"]["template"] == {"query": {"value": "climate"}}
        assert migrate_flow_payload(flow, table=table).rewritten_count == 0
