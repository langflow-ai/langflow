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

This covers the *deserialize-side* half of the M1 proof gate: a saved flow
from pre-migration Langflow loads without intervention and the bundle
distribution is wired correctly.

Not covered here -- explicitly out of scope for a unit-test-style
integration: the *runtime* half of the M1 dogfood gate ("save a flow on
pre-migration Langflow, upgrade, confirm it loads AND RUNS identically").
That requires standing up a real Langflow server, executing the flow
end-to-end, and comparing the search-result payload to a baseline.  It
lives in the manual dogfood checklist at
``src/bundles/duckduckgo/M1_DOGFOOD_CHECKLIST.md`` and runs against an
actual upgrade in a clean environment, not the test suite.  A completed
checklist must be linked in the PR description under "M1 dogfood
evidence" before merge.
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
def test_legacy_bare_name_flow_upgrades(migration_table) -> None:
    """Pre-Phase-A flow saved with the bare class name upgrades to the canonical ID.

    A flow that serialized ``DuckDuckGoSearchComponent`` (the bare class name
    Langflow used for years before the bundle move) must rewrite to
    ``ext:duckduckgo:DuckDuckGoSearchComponent@official``.
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
    """Package-level import-path form (re-exported by ``__init__.py``) also upgrades.

    Catches flows that referenced ``lfx.components.duckduckgo.DuckDuckGoSearchComponent``
    via the package-level re-export rather than the file-level dotted path.
    """
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("ddg-3", "lfx.components.duckduckgo.DuckDuckGoSearchComponent"))

    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET


@pytest.mark.integration
def test_lfx_duckduckgo_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace.

    Catches the case where the package layout drifts from what
    ``langflow.extensions`` references in the entry-point.

    Skipped when the bundle is not installed in the test environment
    (lfx's own venv does not list lfx-duckduckgo as a dep); the langflow
    workspace venv pulls it in transitively from langflow's pyproject.
    """
    try:
        from lfx_duckduckgo import DuckDuckGoSearchComponent
    except ImportError:
        pytest.skip("lfx-duckduckgo not installed in this test environment")

    # The class must round-trip its canonical class name (used by the
    # migration table's ``bare_class_name`` entry).
    assert DuckDuckGoSearchComponent.__name__ == "DuckDuckGoSearchComponent"


@pytest.mark.integration
def test_pilot_loads_and_resolves_to_runtime_class() -> None:
    """The loader resolves the migration-table target to a usable Component class.

    This is the deserialize-side complement of the manual dogfood gate:
    the migration-table tests above prove the rewrite happens, and this
    test proves the rewritten target ``ext:duckduckgo:DuckDuckGoSearchComponent@official``
    resolves to a Component class that:

        1. Imports without side-effects under :func:`load_extension`.
        2. Is the same ``DuckDuckGoSearchComponent`` symbol the bundle's
           Python package exports (so a saved flow that points at the
           rewritten ID cannot end up bound to a different class than a
           ``from lfx_duckduckgo import ...`` import would resolve).
        3. Declares the user-visible inputs / outputs the pre-extraction
           component shipped, so a saved flow's input wiring stays valid
           after the upgrade.

    Network execution of the actual DuckDuckGo search is **not** covered
    here; that lives in the manual dogfood checklist because it requires
    a real environment swap and live network. This test closes the gap
    between "the rewrite happens" and "the rewritten target is usable",
    which is the strongest invariant we can lock in without a network.
    """
    try:
        import lfx_duckduckgo
    except ImportError:
        pytest.skip("lfx-duckduckgo not installed in this test environment")

    from lfx.extension import SLOT_OFFICIAL, load_extension
    from lfx_duckduckgo import DuckDuckGoSearchComponent as ExpectedClass

    # Locate the bundle root that ships in the wheel: the directory that
    # contains the inner extension.json and the components/ tree.
    package_dir = Path(lfx_duckduckgo.__file__).parent
    bundle_root = package_dir

    result = load_extension(bundle_root, slot=SLOT_OFFICIAL, distribution="lfx-duckduckgo")
    assert result.ok, [e.code for e in result.errors]

    by_class = {comp.class_name: comp for comp in result.components}
    assert "DuckDuckGoSearchComponent" in by_class, (
        f"loader did not register DuckDuckGoSearchComponent; got: {sorted(by_class)}"
    )
    loaded = by_class["DuckDuckGoSearchComponent"]

    # Migration-table target shape: every legacy reference rewrites to this ID.
    assert loaded.bundle == "duckduckgo"
    assert loaded.slot == SLOT_OFFICIAL
    expected_namespaced_id = f"ext:{loaded.bundle}:{loaded.class_name}@{loaded.slot}"
    assert expected_namespaced_id == EXPECTED_TARGET

    # The class the loader registered must be the same symbol the bundle
    # exports.  If these diverge, a saved flow could bind to a stale or
    # shadow copy after migration, which is exactly what dogfood is
    # supposed to catch -- here we lock it in for CI.
    assert loaded.klass is ExpectedClass

    # Spot-check the input shape so a saved flow's wiring keeps resolving:
    # ``input_value`` is the field every pre-migration flow targets.
    input_names = {getattr(inp, "name", None) for inp in loaded.klass.inputs}
    assert "input_value" in input_names, (
        f"DuckDuckGoSearchComponent dropped its canonical 'input_value' input; "
        f"got: {sorted(n for n in input_names if n)}"
    )

    # Output method names anchor the runtime contract -- the migration
    # would silently break flows wired to ``dataframe`` if the bundle
    # renamed it.
    output_names = {getattr(out, "name", None) for out in loaded.klass.outputs}
    assert "dataframe" in output_names, (
        f"DuckDuckGoSearchComponent dropped its canonical 'dataframe' output; "
        f"got: {sorted(n for n in output_names if n)}"
    )


def _is_editable_install(dist: importlib_metadata.Distribution) -> bool:
    """Detect an editable install (``pip install -e``).

    Editable installs surface only the ``.dist-info`` entries in
    ``dist.files``; the package contents live in the source tree and are
    reachable via the ``.pth`` file, not via ``dist.files``.  We check for
    this by looking for an ``editable`` flag in ``direct_url.json`` (the
    PEP 660 marker) so the test can exercise the wheel layout differently
    when only the editable shape is available.
    """
    direct_url = dist.read_text("direct_url.json")
    if not direct_url:
        return False
    # JSON encoders may or may not insert whitespace; parse rather than
    # string-match to be robust against either form.
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("dir_info", {}).get("editable"))


@pytest.mark.integration
def test_lfx_duckduckgo_ships_manifest() -> None:
    """``importlib.metadata`` can find ``extension.json`` for the installed dist.

    This is the contract LE-1022's :func:`load_installed_extensions` reads
    at server startup; if the wheel doesn't include the manifest, the
    bundle never registers and the AC ("pip install langflow still pulls
    in the pilot bundle as before") fails silently.

    Editable installs (``pip install -e``) hide package files from
    ``dist.files`` -- only ``dist-info`` entries appear -- so for editable
    mode we instead resolve the manifest via the source-tree path encoded
    in ``direct_url.json`` and assert the same content.
    """
    try:
        dist = importlib_metadata.distribution("lfx-duckduckgo")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-duckduckgo not installed in this test environment")

    if _is_editable_install(dist):
        # Editable install: walk the source tree to verify manifest layout.
        # This is the same shape a real wheel install will ship; we just
        # cannot use dist.files to discover it.
        import lfx_duckduckgo

        package_dir = Path(lfx_duckduckgo.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file(), (
            f"lfx-duckduckgo source tree at {package_dir} does not ship "
            "extension.json next to __init__.py; the wheel build will "
            "not include it either.  Check pyproject's "
            "[tool.hatch.build.targets.wheel] include rules."
        )
    else:
        # Non-editable wheel install: assert dist.files surfaces the manifest
        # (the path LE-1022's loader walks at runtime).
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests, (
            "lfx-duckduckgo distribution does not ship extension.json in its "
            "wheel; the loader will skip it.  Check pyproject's "
            "[tool.hatch.build.targets.wheel] include rules."
        )
        manifest_path = Path(dist.locate_file(manifests[0]))

    # Round-trip the manifest: it must parse, declare lfx.compat=['1'],
    # and point at a bundle named 'duckduckgo'.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-duckduckgo"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "duckduckgo" for b in manifest["bundles"])
