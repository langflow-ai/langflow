"""Integration test: legacy DataStax / AstraDB flows upgrade cleanly.

Third pilot extraction (after ``duckduckgo`` and ``arxiv``); the bundle
houses 11 components plus the shared ``AstraDBBaseComponent`` mixin
that used to live at ``lfx.base.datastax.astradb_base``.  Verifies the
save/upgrade/load contract for flows that referenced any of the legacy
``lfx.components.datastax.*`` forms:

    1. Saved flows that used the bare class name (the form Langflow
       serialized for years pre-extraction) rewrite to
       ``ext:datastax:<Class>@official``.
    2. Saved flows that used the full dotted import path rewrite to the
       same canonical ID.
    3. Saved flows that used the package-level re-export path rewrite
       to the same canonical ID.
    4. The lfx-datastax distribution is importable and ships the
       manifest in a location ``importlib.metadata.files`` can discover.
    5. The loader resolves the canonical ID to a Component class built
       from the bundle's own source.

Not covered here -- the same gap the duckduckgo/arxiv pilots leave to
the manual dogfood: standing up a pre-migration Langflow release,
saving a flow that uses an AstraDB component against a live cluster,
upgrading, and confirming the loaded flow still talks to AstraDB
correctly.  The datastax bundle's manual dogfood gate is the same
checklist shape; the automated tests below mean the dogfood is
answering "does the live SDK still work?" rather than re-verifying
the full load-and-rewrite pipeline.
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"

# Every bundle class is exercised through the migration table to lock in
# the four-shape entry block per class (bare name + two import paths +
# pre-Phase-A legacy slot).
BUNDLE_CLASSES: tuple[tuple[str, str], ...] = (
    ("AstraDBVectorStoreComponent", "astradb_vectorstore"),
    ("AstraDBDataAPIComponent", "astradb_data_api"),
    ("AstraDBGraphVectorStoreComponent", "astradb_graph"),
    ("AstraDBCQLToolComponent", "astradb_cql"),
    ("AstraDBToolComponent", "astradb_tool"),
    ("AstraDBChatMemory", "astradb_chatmemory"),
    ("AstraVectorizeComponent", "astradb_vectorize"),
    ("GraphRAGComponent", "graph_rag"),
    ("HCDVectorStoreComponent", "hcd"),
    ("Dotenv", "dotenv"),
    ("GetEnvVar", "getenvvar"),
)


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
        "data": {"id": node_id, "type": type_value, "node": {"template": {}}},
    }


def _saved_flow(*nodes: dict) -> dict:
    return {"data": {"nodes": list(nodes), "edges": []}}


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "module_stem"), BUNDLE_CLASSES)
def test_legacy_bare_name_flow_upgrades(migration_table, class_name: str, module_stem: str) -> None:  # noqa: ARG001
    """Bare class name rewrites to the canonical namespaced ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    expected = f"ext:datastax:{class_name}@official"
    flow = _saved_flow(_saved_flow_node(f"ds-bare-{class_name}", class_name))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected
    [record] = report.records
    assert record.legacy_form_kind == "bare_class_name"
    assert record.new_value == expected


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "module_stem"), BUNDLE_CLASSES)
def test_legacy_import_path_flow_upgrades(migration_table, class_name: str, module_stem: str) -> None:
    """Full dotted import path rewrites to the canonical namespaced ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    expected = f"ext:datastax:{class_name}@official"
    legacy = f"lfx.components.datastax.{module_stem}.{class_name}"
    flow = _saved_flow(_saved_flow_node(f"ds-full-{class_name}", legacy))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "module_stem"), BUNDLE_CLASSES)
def test_short_import_path_flow_upgrades(migration_table, class_name: str, module_stem: str) -> None:  # noqa: ARG001
    """Package-level import-path (via ``__init__.py`` re-export) rewrites cleanly."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    expected = f"ext:datastax:{class_name}@official"
    legacy = f"lfx.components.datastax.{class_name}"
    flow = _saved_flow(_saved_flow_node(f"ds-short-{class_name}", legacy))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected


@pytest.mark.integration
def test_lfx_datastax_distribution_is_importable() -> None:
    """The bundle is importable in the development workspace."""
    try:
        import lfx_datastax
    except ImportError:
        pytest.skip("lfx-datastax not installed in this test environment")

    # Every declared class must be reachable from the package root --
    # ``bare_class_name`` migration entries depend on this.
    for class_name, _module_stem in BUNDLE_CLASSES:
        klass = getattr(lfx_datastax, class_name, None)
        assert klass is not None, f"lfx_datastax does not re-export {class_name!r}"
        assert klass.__name__ == class_name


@pytest.mark.integration
def test_lfx_datastax_shared_base_is_importable() -> None:
    """The shared ``AstraDBBaseComponent`` mixin (moved from lfx.base.datastax) resolves."""
    try:
        from lfx_datastax.base import AstraDBBaseComponent
    except ImportError:
        pytest.skip("lfx-datastax not installed in this test environment")

    assert AstraDBBaseComponent.__name__ == "AstraDBBaseComponent"


@pytest.mark.integration
def test_pilot_loads_and_resolves_to_runtime_class() -> None:
    """The loader resolves every canonical ID to a class built from the bundle's source.

    Catches the case where the package layout drifts from what the
    migration table targets: every ``ext:datastax:<Class>@official`` ID
    must resolve to a Component class that was loaded from the bundle's
    own files (not a shadow copy elsewhere on sys.path).  The loader
    stages bundle modules under ``_lfx_ext.<slot>.<bundle>`` so object
    identity vs. the bundle's exported symbol does NOT hold; the
    invariant we lock in here is "same source file, same qualified
    name", which is what saved flows actually depend on.
    """
    try:
        import lfx_datastax
    except ImportError:
        pytest.skip("lfx-datastax not installed in this test environment")

    import inspect

    from lfx.extension import SLOT_OFFICIAL, load_extension

    package_dir = Path(lfx_datastax.__file__).parent
    result = load_extension(package_dir, slot=SLOT_OFFICIAL, distribution="lfx-datastax")
    assert result.ok, [e.code for e in result.errors]

    by_class = {comp.class_name: comp for comp in result.components}
    for class_name, _module_stem in BUNDLE_CLASSES:
        assert class_name in by_class, f"loader did not register {class_name}; got: {sorted(by_class)}"
        loaded = by_class[class_name]
        assert loaded.bundle == "datastax"
        assert loaded.slot == SLOT_OFFICIAL
        assert f"ext:{loaded.bundle}:{loaded.class_name}@{loaded.slot}" == (f"ext:datastax:{class_name}@official")

        # Loaded class must come from the same source file as the bundle's
        # exported symbol so saved-flow references cannot end up bound to
        # a stale shadow copy.
        expected_cls = getattr(lfx_datastax, class_name)
        assert inspect.getsourcefile(loaded.klass) == inspect.getsourcefile(expected_cls), (
            f"loaded {class_name} came from a different source file: "
            f"loaded={inspect.getsourcefile(loaded.klass)!r} "
            f"expected={inspect.getsourcefile(expected_cls)!r}"
        )
        assert loaded.klass.__name__ == expected_cls.__name__


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
def test_lfx_datastax_ships_manifest() -> None:
    """``importlib.metadata`` finds ``extension.json`` for the installed dist.

    Editable installs (``pip install -e``) hide package files from
    ``dist.files`` -- only ``dist-info`` entries appear -- so for the
    editable mode we instead resolve the manifest via the source-tree
    path and assert the same content.
    """
    try:
        dist = importlib_metadata.distribution("lfx-datastax")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-datastax not installed in this test environment")

    if _is_editable_install(dist):
        import lfx_datastax

        package_dir = Path(lfx_datastax.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file(), (
            f"lfx-datastax source tree at {package_dir} does not ship "
            "extension.json next to __init__.py; the wheel build will "
            "not include it either.  Check pyproject's "
            "[tool.hatch.build.targets.wheel] include rules."
        )
    else:
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests, (
            "lfx-datastax distribution does not ship extension.json in its "
            "wheel; the loader will skip it.  Check pyproject's "
            "[tool.hatch.build.targets.wheel] include rules."
        )
        manifest_path = Path(dist.locate_file(manifests[0]))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-datastax"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "datastax" for b in manifest["bundles"])
