"""Integration test for the LE-1023 pilot: legacy DuckDuckGo flows upgrade cleanly.

Verifies the save/upgrade/load contract for flows referencing
``DuckDuckGoSearchComponent`` from the pre-extraction Langflow:

    1. A saved flow uses the legacy bare class name ``DuckDuckGoSearchComponent``
       (the form Langflow serialized for years before the bundle move).
    2. The migration table rewrites it to the canonical post-Phase-A
       namespaced ID ``ext:duckduckgo:DuckDuckGoSearchComponent@official``.
    3. A second flow uses the legacy import path
       ``lfx.components.duckduckgo.duck_duck_go_search_run.DuckDuckGoSearchComponent``;
       same rewrite outcome.
    4. The lfx-duckduckgo distribution is importable and ships the manifest
       in a location ``importlib.metadata.files`` can discover.

This is the regression suite the B1 acceptance criteria require: saved flows
from pre-migration Langflow must load without intervention.
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"
EXPECTED_TARGET = "ext:duckduckgo:DuckDuckGoSearchComponent@official"


@pytest.fixture(scope="module")
def migration_table():
    return load_migration_table(TABLE_PATH)


def _saved_flow_node(node_id: str, type_value: str) -> dict:
    """Build a minimal saved-flow node skeleton for testing."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": type_value,
            "node": {"template": {}},
        },
    }


def _saved_flow(*nodes: dict) -> dict:
    """Wrap nodes in the canonical Langflow flow envelope."""
    return {"data": {"nodes": list(nodes), "edges": []}}


@pytest.mark.integration
def test_legacy_bare_name_flow_upgrades(migration_table) -> None:
    """A pre-Phase-A flow saved with bare class name ``DuckDuckGoSearchComponent``
    upgrades to the canonical namespaced ID.
    """
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("ddg-1", "DuckDuckGoSearchComponent"))

    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1, "exactly one node should rewrite"
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    [record] = report.records
    assert record.legacy_form_kind == "bare_class_name"
    assert record.new_value == EXPECTED_TARGET


@pytest.mark.integration
def test_legacy_import_path_flow_upgrades(migration_table) -> None:
    """A pre-Phase-A flow saved with the dotted import path upgrades cleanly.

    Some Langflow versions serialized the full module path instead of the
    bare class name; both legacy forms must rewrite to the same target.
    """
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node(
            "ddg-2",
            "lfx.components.duckduckgo.duck_duck_go_search_run.DuckDuckGoSearchComponent",
        )
    )

    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
def test_short_import_path_flow_upgrades(migration_table) -> None:
    """The package-level import path ``lfx.components.duckduckgo.DuckDuckGoSearchComponent``
    (the form re-exported by ``__init__.py``) also upgrades.
    """
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node("ddg-3", "lfx.components.duckduckgo.DuckDuckGoSearchComponent")
    )

    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET


@pytest.mark.integration
def test_lfx_duckduckgo_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace.

    Catches the case where the package layout drifts from what
    ``langflow.extensions`` references in the entry-point.
    """
    from lfx_duckduckgo import DuckDuckGoSearchComponent

    # The class must round-trip its canonical class name (used by the
    # migration table's ``bare_class_name`` entry).
    assert DuckDuckGoSearchComponent.__name__ == "DuckDuckGoSearchComponent"


@pytest.mark.integration
def test_lfx_duckduckgo_ships_manifest() -> None:
    """``importlib.metadata`` can find ``extension.json`` for the installed dist.

    This is the contract LE-1022's :func:`load_installed_extensions` reads
    at server startup; if the wheel doesn't include the manifest, the
    bundle never registers and the AC ("pip install langflow still pulls
    in the pilot bundle as before") fails silently.
    """
    try:
        dist = importlib_metadata.distribution("lfx-duckduckgo")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-duckduckgo not installed in this test environment")

    files = dist.files or []
    manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
    assert manifests, (
        "lfx-duckduckgo distribution does not ship extension.json in its "
        "wheel; the loader will skip it.  Check pyproject's "
        "[tool.hatch.build.targets.wheel] include rules."
    )

    # Round-trip the manifest: it must parse, declare lfx.compat=['1'],
    # and point at a bundle named 'duckduckgo'.
    manifest_path = Path(dist.locate_file(manifests[0]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-duckduckgo"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "duckduckgo" for b in manifest["bundles"])
