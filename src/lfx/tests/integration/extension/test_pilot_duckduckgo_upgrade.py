"""Integration test for the DuckDuckGo pilot: legacy flows upgrade cleanly.

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

This covers the *deserialize-side* half of the M1 proof gate plus the
build-pipeline runtime contract: a saved flow from pre-migration Langflow
loads without intervention, the bundle distribution is wired correctly,
the migration target resolves to a class built from the same source as
the bundle export, and that loader-registered class's build method runs
end-to-end against a stubbed network wrapper to produce the canonical
output schema (``content`` / ``snippet`` columns, ``max_results``
slicing, ``max_snippet_length`` truncation, canonical query template).

Not covered here -- the part that genuinely requires a real environment
swap: standing up a pre-migration Langflow release, saving a flow,
upgrading to the post-migration release, loading that same flow JSON,
and confirming real DuckDuckGo search results haven't drifted between
versions.  That's the M1 manual dogfood gate; checklist lives at
``src/bundles/duckduckgo/M1_DOGFOOD_CHECKLIST.md`` and must be filled
in by a non-Extension-team engineer and linked in the PR description
under "M1 dogfood evidence" before merge.  The automated tests below
mean the dogfood is now answering one specific question -- "did real
search results change?" -- rather than re-verifying the full
load-and-run pipeline.
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
        2. Comes from the bundle's own source file (not a shadow copy
           elsewhere on sys.path) so a saved flow that points at the
           rewritten ID cannot end up bound to a stale or wrong class.
           Object identity vs. ``from lfx_duckduckgo import ...`` does
           NOT hold -- the loader stages bundle modules under
           ``_lfx_ext.<slot>.<bundle>`` so the registered class is a
           distinct ``type`` instance with identical source; the
           invariant we lock in is "same source file, same qualified
           name", which is what saved flows actually depend on.
        3. Declares the user-visible inputs / outputs the pre-extraction
           component shipped, so a saved flow's input wiring stays valid
           after the upgrade.

    The companion :func:`test_pilot_build_pipeline_runs_against_stub_wrapper`
    test below extends this further by actually invoking the loaded
    class's build method against a stubbed network wrapper, proving the
    loaded class is not just symbolically identical but also runnable to
    the canonical output schema.

    Network execution of the *real* DuckDuckGo backend is not covered in
    automated tests; that lives in the manual dogfood checklist because
    it requires a real environment swap and live network. What remains
    for the dogfood is therefore the pre/post version-swap step and
    confirmation that real search results haven't drifted -- not the
    "does the rewritten class run" question, which is locked in here.
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

    # The class the loader registered must come from the same source file
    # as the bundle's exported symbol.  We can't assert object identity
    # (``loaded.klass is ExpectedClass``) because the loader stages bundle
    # modules under its own ``_lfx_ext.<slot>.<bundle>`` namespace, so the
    # class object the registry holds is a different ``type`` instance
    # than ``from lfx_duckduckgo import ...`` resolves to -- even though
    # they have identical source.  The invariant a saved flow actually
    # depends on is "the loaded class is built from the bundle's own
    # source file, not a shadow copy elsewhere on sys.path", which we
    # express via the source file and the qualified class name.
    import inspect

    assert inspect.getsourcefile(loaded.klass) == inspect.getsourcefile(ExpectedClass), (
        f"loaded class came from a different source file: "
        f"loaded={inspect.getsourcefile(loaded.klass)!r} "
        f"expected={inspect.getsourcefile(ExpectedClass)!r}"
    )
    assert loaded.klass.__name__ == ExpectedClass.__name__
    assert loaded.klass.__qualname__ == ExpectedClass.__qualname__

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


@pytest.mark.integration
def test_pilot_build_pipeline_runs_against_stub_wrapper() -> None:
    """Instantiate the loaded class and run its build method against a stub.

    The previous test proved the migration target resolves to a class
    built from the same source file as the bundle export.  This one goes
    one step further: it instantiates the loaded class, patches its single
    network seam
    (``_build_wrapper``) to return a stub whose ``.run()`` produces a
    canned newline-separated result string, and invokes
    :meth:`DuckDuckGoSearchComponent.fetch_content_dataframe` -- the
    method the canonical ``dataframe`` output is wired to.

    Passing this assertion means a flow that referenced any legacy form
    of the component (bare class name, full import path, package import
    path, pre-Phase-A slot ID) will, after the migration table rewrites
    it, both deserialize to the right class **and** execute that class's
    build pipeline to the canonical output schema.  The only thing left
    for the manual M1 dogfood gate is to confirm real search results
    against the live DuckDuckGo backend haven't drifted between the
    pre- and post-migration releases -- the runtime contract itself is
    locked in here.

    Network is never touched: the stub is the entire wrapper surface
    ``fetch_content`` uses.  Failure modes this guards against:
        - The post-migration class drops or renames the ``_build_wrapper``
          seam, breaking flows that wire output ``dataframe`` through.
        - The output ``DataFrame`` no longer carries the ``content`` /
          ``snippet`` columns flows downstream depend on.
        - ``max_results`` slicing logic regresses (e.g. silently returns
          the unsliced result list, leaking memory on large queries).
    """
    try:
        import lfx_duckduckgo
    except ImportError:
        pytest.skip("lfx-duckduckgo not installed in this test environment")

    from lfx.extension import SLOT_OFFICIAL, load_extension

    package_dir = Path(lfx_duckduckgo.__file__).parent
    result = load_extension(package_dir, slot=SLOT_OFFICIAL, distribution="lfx-duckduckgo")
    assert result.ok, [e.code for e in result.errors]
    loaded = next(c for c in result.components if c.class_name == "DuckDuckGoSearchComponent")

    # Instantiate the *loaded* class -- not the bundle's exported one --
    # because the loaded class (built under ``_lfx_ext.<slot>.<bundle>``)
    # is what saved flows actually resolve to after the migration table
    # rewrites their references.  The sibling test asserts the loaded
    # class comes from the same source file as the bundle export; this
    # test exercises that loaded class's runtime behaviour.
    component = loaded.klass()

    # The build pipeline reads three attributes off ``self``; the
    # Component base populates them at runtime from declared inputs, but
    # for an isolation test we set them directly so we are not exercising
    # the full input-binding machinery here.
    component.input_value = "claude shannon"
    component.max_results = 3
    component.max_snippet_length = 32

    # The single network seam: ``_build_wrapper`` returns an object whose
    # ``.run(query)`` returns newline-separated result strings.  The stub
    # mimics that shape so ``fetch_content`` exercises every branch of
    # its parser (split, slice, snippet truncation, dict construction).
    canned_results = (
        "First result about Claude Shannon's information theory work\n"
        "Second result on the 1948 paper, A Mathematical Theory of Communication\n"
        "Third result on Bell Labs and switching circuits\n"
        # max_results=3 should cause the parser to drop this entry.
        "Fourth result that must not appear in the DataFrame"
    )

    class _StubWrapper:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def run(self, query: str) -> str:
            self.calls.append(query)
            return canned_results

    stub = _StubWrapper()
    component._build_wrapper = lambda: stub  # type: ignore[method-assign]

    dataframe = component.fetch_content_dataframe()

    # The wrapper was invoked with the canonical query shape so a future
    # regression that changes the query template surfaces immediately.
    assert stub.calls == ["claude shannon (site:*)"], (
        f"DuckDuckGoSearchComponent changed its query template: {stub.calls!r}"
    )

    # The DataFrame output schema is the runtime contract every saved
    # flow downstream of this component expects.  The build pipeline
    # produces rows with ``content`` and ``snippet`` columns; ``text``
    # is the Data.text field and is exposed via the DataFrame index.
    rows = dataframe.to_dict(orient="records") if hasattr(dataframe, "to_dict") else list(dataframe)
    assert len(rows) == 3, f"max_results=3 slicing regressed; got {len(rows)} rows: {rows!r}"

    for row in rows:
        # The component stores both the full content and a snippet; downstream
        # flows index into either, so both must be present on every row.
        assert "content" in row, f"Data row missing 'content' key: {row!r}"
        assert "snippet" in row, f"Data row missing 'snippet' key: {row!r}"
        # Snippet truncation honours ``max_snippet_length=32``.
        assert len(row["snippet"]) <= 32, f"snippet exceeds max_snippet_length=32: {row['snippet']!r}"
        # And the snippet is a strict prefix of the full content so flows
        # comparing the two see the same canonical shape they did before.
        assert row["content"].startswith(row["snippet"]), (
            f"snippet is not a prefix of content: snippet={row['snippet']!r} content={row['content']!r}"
        )

    first = rows[0]
    assert first["content"] == "First result about Claude Shannon's information theory work"
    assert first["snippet"] == first["content"][:32]
    assert "Fourth result" not in {row["content"] for row in rows}


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

    This is the contract :func:`load_installed_extensions` reads at
    server startup; if the wheel doesn't include the manifest, the bundle
    never registers and ``pip install langflow`` silently fails to pull
    in the pilot bundle.

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
        # (the path the loader walks at runtime).
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
