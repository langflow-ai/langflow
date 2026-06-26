"""Tests for ``load_installed_extensions`` -- startup-time discovery flow.

Covers the AC item: "Tracked by distribution name; two same-named distributions
emit duplicate-distribution." Also exercises the lexicographically-first
manifest-path tiebreaker that drives the winner selection.
"""

from __future__ import annotations

import json
from pathlib import Path

from lfx.extension import (
    SLOT_OFFICIAL,
    load_installed_extensions,
)

from .conftest import FakeDist, component_source, make_installed_extension


def _populate_bundle(parent: Path, distribution_name: str) -> None:
    """Put a Component source file under the manifest-declared bundle path."""
    bundle_dir = parent / distribution_name / "components"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "thing.py").write_text(component_source(), encoding="utf-8")


def test_loads_each_installed_extension_once(tmp_path: Path) -> None:
    """Two distinct distributions both load at @official with identity attributed."""
    dist_a = make_installed_extension(tmp_path, "lfx-alpha")
    dist_b = make_installed_extension(tmp_path, "lfx-bravo")
    _populate_bundle(tmp_path, "lfx-alpha")
    _populate_bundle(tmp_path, "lfx-bravo")

    results = load_installed_extensions(distributions=[dist_a, dist_b])
    by_dist = {r.distribution: r for r in results}
    assert set(by_dist) == {"lfx-alpha", "lfx-bravo"}
    for canonical, result in by_dist.items():
        assert result.ok, [e.code for e in result.errors]
        assert result.slot == SLOT_OFFICIAL
        assert result.extension_id == canonical
        assert result.distribution == canonical
        # Component is attributed via the canonical PEP-503 name.
        assert result.components[0].distribution == canonical


def test_duplicate_distribution_emits_warning(tmp_path: Path) -> None:
    """Two distributions with the same canonical name surface duplicate-distribution.

    The lexicographically-first manifest path wins; the warning's location
    field names every involved manifest path so an operator can resolve.
    """
    # Two on-disk locations, same canonical distribution name.
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()

    manifest = {
        "id": "lfx-pilot",
        "version": "1.0.0",
        "name": "lfx-pilot",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "pilot", "path": "components"}],
    }
    (first_root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    (second_root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    (first_root / "components").mkdir()
    (first_root / "components" / "thing.py").write_text(component_source(), encoding="utf-8")

    dist_first = FakeDist(
        name="lfx-pilot",
        root=first_root.parent,
        files=[Path("first") / "extension.json"],
    )
    dist_second = FakeDist(
        name="lfx-pilot",
        root=second_root.parent,
        files=[Path("second") / "extension.json"],
    )

    results = load_installed_extensions(distributions=[dist_first, dist_second])
    assert len(results) == 1
    result = results[0]
    assert result.distribution == "lfx-pilot"
    # Winner is the lexicographically-first manifest path.
    assert result.source_path == first_root.resolve()
    # AC: duplicate-distribution is surfaced as an ERROR (LoadResult.ok=False)
    # so the events pipeline emits ``extension_error`` rather than treating
    # the conflict as a successful load.
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert "duplicate-distribution" in codes
    err = next(e for e in result.errors if e.code == "duplicate-distribution")
    # The location field names BOTH manifest paths so the operator can resolve.
    assert "first" in err.location
    assert "second" in err.location
    assert err.content == "lfx-pilot"
    assert err.hint  # AC: fix-hint payload
    # Winner's components still load -- only the conflict status changes.
    assert result.components, "Winner's components should still be loaded"


def test_no_installed_extensions_returns_empty(tmp_path: Path) -> None:
    """A distribution without a manifest contributes nothing."""
    plain_dist = FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    results = load_installed_extensions(distributions=[plain_dist])
    assert results == []


def test_editable_install_discovered_via_direct_url(tmp_path: Path) -> None:
    """Editable installs (``pip install -e``) typically expose only dist-info files.

    The dist-info pass finds no ``extension.json``; the loader must fall
    back to PEP 610 ``direct_url.json`` (``editable=true``) which records
    the source path.  Without this fallback, an ``lfx-duckduckgo`` linked
    via ``uv sync`` workspace member never reaches
    :func:`load_installed_extensions` -- the dogfood / dev case skipped
    the bundle entirely.
    """
    # Lay out a real extension on disk to be the "editable source".
    project_root = tmp_path / "src" / "bundles" / "duckduckgo"
    bundle_dir = project_root / "components"
    bundle_dir.mkdir(parents=True)
    (project_root / "extension.json").write_text(
        json.dumps(
            {
                "id": "lfx-pilot",
                "version": "1.0.0",
                "name": "lfx-pilot",
                "lfx": {"compat": ["1"]},
                "bundles": [{"name": "pilot", "path": "components"}],
            }
        ),
        encoding="utf-8",
    )
    (bundle_dir / "thing.py").write_text(component_source(), encoding="utf-8")

    class _EditableDist(FakeDist):
        """FakeDist that exposes the same surface as ``importlib.metadata.Distribution``.

        Editable installs leave ``files`` listing only dist-info entries;
        the manifest is reachable only via ``read_text("direct_url.json")``.
        """

        def __init__(self, name: str, project_root: Path) -> None:
            super().__init__(name=name, root=tmp_path, files=[Path("dist-info") / "METADATA"])
            self._direct_url = json.dumps(
                {
                    "url": project_root.resolve().as_uri(),
                    "dir_info": {"editable": True},
                }
            )

        def read_text(self, name: str) -> str | None:
            if name == "direct_url.json":
                return self._direct_url
            return None

        @property
        def entry_points(self):
            return []

    dist = _EditableDist("lfx-pilot", project_root)

    results = load_installed_extensions(distributions=[dist])
    assert len(results) == 1
    result = results[0]
    assert result.ok, [e.code for e in result.errors]
    assert result.distribution == "lfx-pilot"
    assert result.source_path == project_root.resolve()
    assert result.components, "Editable bundle's components must load"


def test_results_are_lexicographically_ordered(tmp_path: Path) -> None:
    """Order is deterministic so events / logging are reproducible."""
    for name in ("lfx-zeta", "lfx-alpha", "lfx-mike"):
        make_installed_extension(tmp_path, name)
        _populate_bundle(tmp_path, name)
    dists = [
        FakeDist(name="lfx-zeta", root=tmp_path, files=[Path("lfx-zeta") / "extension.json"]),
        FakeDist(name="lfx-alpha", root=tmp_path, files=[Path("lfx-alpha") / "extension.json"]),
        FakeDist(name="lfx-mike", root=tmp_path, files=[Path("lfx-mike") / "extension.json"]),
    ]
    results = load_installed_extensions(distributions=dists)
    assert [r.distribution for r in results] == ["lfx-alpha", "lfx-mike", "lfx-zeta"]
