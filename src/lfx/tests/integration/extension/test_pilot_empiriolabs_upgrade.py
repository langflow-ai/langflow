"""Integration test: legacy empiriolabs flows upgrade cleanly.

Mirrors ``test_pilot_paddle_upgrade.py`` for the ``lfx-empiriolabs`` bundle,
which ships two components: ``EmpirioLabsModelComponent`` and
``EmpirioLabsImageGenerationComponent``.
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"
MODEL_TARGET = "ext:empiriolabs:EmpirioLabsModelComponent@official"
IMAGE_TARGET = "ext:empiriolabs:EmpirioLabsImageGenerationComponent@official"


@pytest.fixture(scope="module")
def migration_table():
    table, error = load_migration_table(TABLE_PATH)
    assert error is None, f"failed to load migration table: {error}"
    assert table is not None
    return table


def _saved_flow_node(node_id: str, type_value: str) -> dict:
    """Build a minimal saved-flow node skeleton for testing."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {"id": node_id, "type": type_value, "node": {"template": {}}},
    }


def _saved_flow(*nodes: dict) -> dict:
    return {"data": {"nodes": list(nodes), "edges": []}}


@pytest.mark.integration
def test_legacy_bare_name_flow_upgrades(migration_table) -> None:
    """Pre-Phase-A flows with the bare class names upgrade to the canonical IDs."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node("empiriolabs-1", "EmpirioLabsModelComponent"),
        _saved_flow_node("empiriolabs-2", "EmpirioLabsImageGenerationComponent"),
    )
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 2
    assert flow["data"]["nodes"][0]["data"]["type"] == MODEL_TARGET
    assert flow["data"]["nodes"][1]["data"]["type"] == IMAGE_TARGET
    assert {r.legacy_form_kind for r in report.records} == {"bare_class_name"}


@pytest.mark.integration
def test_legacy_import_path_flow_upgrades(migration_table) -> None:
    """Dotted import-path forms upgrade to the canonical IDs."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node("empiriolabs-1", "lfx.components.empiriolabs.empiriolabs.EmpirioLabsModelComponent"),
        _saved_flow_node(
            "empiriolabs-2",
            "lfx.components.empiriolabs.empiriolabs_image_generation.EmpirioLabsImageGenerationComponent",
        ),
    )
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 2
    assert flow["data"]["nodes"][0]["data"]["type"] == MODEL_TARGET
    assert flow["data"]["nodes"][1]["data"]["type"] == IMAGE_TARGET
    assert {r.legacy_form_kind for r in report.records} == {"import_path"}


@pytest.mark.integration
def test_short_import_path_flow_upgrades(migration_table) -> None:
    """Package-level import-path forms (via ``__init__.py`` re-export) upgrade."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node("empiriolabs-1", "lfx.components.empiriolabs.EmpirioLabsModelComponent"),
        _saved_flow_node("empiriolabs-2", "lfx.components.empiriolabs.EmpirioLabsImageGenerationComponent"),
    )
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 2
    assert flow["data"]["nodes"][0]["data"]["type"] == MODEL_TARGET
    assert flow["data"]["nodes"][1]["data"]["type"] == IMAGE_TARGET


@pytest.mark.integration
def test_legacy_slot_flow_upgrades(migration_table) -> None:
    """The pre-Phase-A ``@official-pre-a`` slot forms upgrade to the canonical IDs."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node("empiriolabs-1", "ext:empiriolabs:EmpirioLabsModelComponent@official-pre-a"),
        _saved_flow_node("empiriolabs-2", "ext:empiriolabs:EmpirioLabsImageGenerationComponent@official-pre-a"),
    )
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 2
    assert flow["data"]["nodes"][0]["data"]["type"] == MODEL_TARGET
    assert flow["data"]["nodes"][1]["data"]["type"] == IMAGE_TARGET
    assert {r.legacy_form_kind for r in report.records} == {"legacy_slot"}


@pytest.mark.integration
def test_lfx_empiriolabs_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace."""
    try:
        from lfx_empiriolabs import EmpirioLabsImageGenerationComponent, EmpirioLabsModelComponent
    except ImportError:
        pytest.skip("lfx-empiriolabs not installed in this test environment")

    assert EmpirioLabsModelComponent.__name__ == "EmpirioLabsModelComponent"
    assert EmpirioLabsImageGenerationComponent.__name__ == "EmpirioLabsImageGenerationComponent"


def _is_editable_install(dist: importlib_metadata.Distribution) -> bool:
    direct_url = dist.read_text("direct_url.json")
    if not direct_url:
        return False
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("dir_info", {}).get("editable"))


@pytest.mark.integration
def test_lfx_empiriolabs_ships_manifest() -> None:
    """``importlib.metadata`` can find ``extension.json`` for the installed dist."""
    try:
        dist = importlib_metadata.distribution("lfx-empiriolabs")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-empiriolabs not installed in this test environment")

    if _is_editable_install(dist):
        import lfx_empiriolabs

        package_dir = Path(lfx_empiriolabs.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file()
    else:
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests
        manifest_path = Path(dist.locate_file(manifests[0]))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-empiriolabs"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "empiriolabs" for b in manifest["bundles"])
