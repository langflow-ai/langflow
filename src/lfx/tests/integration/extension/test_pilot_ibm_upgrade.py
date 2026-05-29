"""Integration test for the third-pilot port: legacy IBM flows upgrade cleanly.

Mirror of ``test_pilot_arxiv_upgrade.py`` against the three components
that ship in ``lfx-ibm``: ``DB2VectorStoreComponent``,
``WatsonxAIComponent``, and ``WatsonxEmbeddingsComponent``.  Together
with the duckduckgo and arxiv suites this exercises the porting recipe
documented in ``src/bundles/PORTING.md`` end-to-end for both a
single-class bundle and a multi-class bundle.

Verifies the save/upgrade/load contract for flows referencing any of
the three IBM components from the pre-extraction Langflow:

    1. A saved flow uses one of the legacy bare class names; the
       migration table rewrites it to the canonical post-Phase-A
       namespaced ID ``ext:ibm:<Class>@official``.
    2. A second flow uses each legacy import-path form (full and
       package-level); same outcome.
    3. The lfx-ibm distribution is importable AND ships the manifest in
       a location ``importlib.metadata.files`` can discover (or, for
       editable installs, that ``direct_url.json`` resolves).
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"

# Each entry: (class_name, legacy_full_path_module, expected_target).
COMPONENTS = [
    (
        "DB2VectorStoreComponent",
        "lfx.components.ibm.db2_vector",
        "ext:ibm:DB2VectorStoreComponent@official",
    ),
    (
        "WatsonxAIComponent",
        "lfx.components.ibm.watsonx",
        "ext:ibm:WatsonxAIComponent@official",
    ),
    (
        "WatsonxEmbeddingsComponent",
        "lfx.components.ibm.watsonx_embeddings",
        "ext:ibm:WatsonxEmbeddingsComponent@official",
    ),
]


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
@pytest.mark.parametrize(("class_name", "_legacy_module", "expected_target"), COMPONENTS)
def test_legacy_bare_name_flow_upgrades(migration_table, class_name, _legacy_module, expected_target) -> None:
    """Pre-Phase-A flow saved with the bare class name upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node(f"ibm-bare-{class_name}", class_name))

    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1, "exactly one node should rewrite"
    assert flow["data"]["nodes"][0]["data"]["type"] == expected_target
    [record] = report.records
    assert record.legacy_form_kind == "bare_class_name"
    assert record.new_value == expected_target


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "legacy_module", "expected_target"), COMPONENTS)
def test_legacy_import_path_flow_upgrades(migration_table, class_name, legacy_module, expected_target) -> None:
    """A pre-Phase-A flow saved with the dotted import path upgrades cleanly."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(
        _saved_flow_node(
            f"ibm-import-{class_name}",
            f"{legacy_module}.{class_name}",
        )
    )

    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected_target
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "_legacy_module", "expected_target"), COMPONENTS)
def test_short_import_path_flow_upgrades(migration_table, class_name, _legacy_module, expected_target) -> None:
    """Package-level import-path form (re-exported by ``__init__.py``) also upgrades."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node(f"ibm-short-{class_name}", f"lfx.components.ibm.{class_name}"))

    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected_target


@pytest.mark.integration
def test_lfx_ibm_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace.

    Catches the case where the package layout drifts from what
    ``langflow.extensions`` references in the entry-point.

    Skipped when the bundle is not installed in the test environment
    (lfx's own venv does not list lfx-ibm as a dep); the langflow
    workspace venv pulls it in transitively from langflow's pyproject.
    """
    try:
        from lfx_ibm import (
            DB2VectorStoreComponent,
            WatsonxAIComponent,
            WatsonxEmbeddingsComponent,
        )
    except ImportError:
        pytest.skip("lfx-ibm not installed in this test environment")

    # The classes must round-trip their canonical class names (used by
    # the migration table's ``bare_class_name`` entries).
    assert DB2VectorStoreComponent.__name__ == "DB2VectorStoreComponent"
    assert WatsonxAIComponent.__name__ == "WatsonxAIComponent"
    assert WatsonxEmbeddingsComponent.__name__ == "WatsonxEmbeddingsComponent"


def _is_editable_install(dist: importlib_metadata.Distribution) -> bool:
    """Detect an editable install (``pip install -e``)."""
    direct_url = dist.read_text("direct_url.json")
    if not direct_url:
        return False
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("dir_info", {}).get("editable"))


@pytest.mark.integration
def test_lfx_ibm_ships_manifest() -> None:
    """``importlib.metadata`` can find ``extension.json`` for the installed dist.

    This is the contract :func:`load_installed_extensions` reads at
    server startup; if the wheel doesn't include the manifest, the bundle
    never registers and ``pip install langflow`` silently fails to pull
    in the pilot bundle.
    """
    try:
        dist = importlib_metadata.distribution("lfx-ibm")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-ibm not installed in this test environment")

    if _is_editable_install(dist):
        # Editable install: walk the source tree to verify manifest layout.
        import lfx_ibm

        package_dir = Path(lfx_ibm.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file(), (
            f"lfx-ibm source tree at {package_dir} does not ship "
            "extension.json next to __init__.py; the wheel build will "
            "not include it either.  Check pyproject's "
            "[tool.hatch.build.targets.wheel] include rules."
        )
    else:
        # Non-editable wheel install: assert dist.files surfaces the manifest.
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests, (
            "lfx-ibm distribution does not ship extension.json in its "
            "wheel; the loader will skip it.  Check pyproject's "
            "[tool.hatch.build.targets.wheel] include rules."
        )
        manifest_path = Path(dist.locate_file(manifests[0]))

    # Round-trip the manifest: it must parse, declare lfx.compat=['1'],
    # and point at a bundle named 'ibm'.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-ibm"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "ibm" for b in manifest["bundles"])
