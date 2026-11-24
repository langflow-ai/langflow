"""Integration test: legacy paddle flows upgrade cleanly.

Mirrors ``test_pilot_firecrawl_upgrade.py`` for ``PaddleOCRComponent`` (the
``lfx-paddle`` bundle).
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"
EXPECTED_TARGET = "ext:paddle:PaddleOCRComponent@official"


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
    """Pre-Phase-A flow with the bare class name upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("paddle-1", "PaddleOCRComponent"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    [record] = report.records
    assert record.legacy_form_kind == "bare_class_name"
    assert record.new_value == EXPECTED_TARGET


@pytest.mark.integration
def test_legacy_import_path_flow_upgrades(migration_table) -> None:
    """Dotted import-path form upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("paddle-2", "lfx.components.paddle.paddleocr.PaddleOCRComponent"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
def test_short_import_path_flow_upgrades(migration_table) -> None:
    """Package-level import-path form (via ``__init__.py`` re-export) upgrades."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("paddle-3", "lfx.components.paddle.PaddleOCRComponent"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET


@pytest.mark.integration
def test_legacy_slot_flow_upgrades(migration_table) -> None:
    """The pre-Phase-A ``@official-pre-a`` slot form upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("paddle-4", "ext:paddle:PaddleOCRComponent@official-pre-a"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    assert report.records[0].legacy_form_kind == "legacy_slot"


@pytest.mark.integration
def test_lfx_paddle_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace."""
    try:
        from lfx_paddle import PaddleOCRComponent
    except ImportError:
        pytest.skip("lfx-paddle not installed in this test environment")

    assert PaddleOCRComponent.__name__ == "PaddleOCRComponent"


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
def test_lfx_paddle_ships_manifest() -> None:
    """``importlib.metadata`` can find ``extension.json`` for the installed dist."""
    try:
        dist = importlib_metadata.distribution("lfx-paddle")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-paddle not installed in this test environment")

    if _is_editable_install(dist):
        import lfx_paddle

        package_dir = Path(lfx_paddle.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file()
    else:
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests
        manifest_path = Path(dist.locate_file(manifests[0]))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-paddle"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "paddle" for b in manifest["bundles"])
