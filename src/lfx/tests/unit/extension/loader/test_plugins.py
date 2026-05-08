"""Tests for manifest-first precedence over ``langflow.plugins``.

Covers the AC item: "package with manifest + legacy component entry-point
loads its components ONCE via the manifest, not twice."  We model "loaded
once" by partitioning the entry points; the manifest-shipping distribution
ends up in ``skipped`` while non-component entry-points on a manifest-less
distribution stay in ``kept``.

Also covers the supporting primitives:
    - PEP-503 distribution-name canonicalization
    - ``installed_extension_roots`` skips distributions without a manifest
    - ``installed_extension_roots`` survives ``files=None``
    - ``manifest_owning_distributions`` is the canonical-name set
    - ``filter_plugin_entry_points`` is defensive on ``dist=None`` and
      consults the real environment when ``skip`` is omitted
"""

from __future__ import annotations

from importlib import metadata as importlib_metadata
from pathlib import Path

from lfx.extension import (
    filter_component_entry_points,
    filter_plugin_entry_points,
    installed_extension_roots,
    manifest_owning_distributions,
)
from lfx.extension.loader._plugins import canonicalize_distribution

from .conftest import (
    FakeDist,
    FakeEntryPoint,
    make_installed_extension,
    make_installed_pyproject_extension,
    make_installed_pyproject_malformed_extension,
    make_installed_pyproject_no_extension,
)


class _FakePluginComponent:
    """Base class whose name ends in 'Component' -- triggers loader heuristic."""


class _LegacyPluginComponent(_FakePluginComponent):
    """Stands in for a legacy component-style entry-point value.

    Inherits from a base whose name ends in 'Component' so
    ``is_component_subclass`` recognizes it as a component class without
    requiring the real heavyweight Component machinery.
    """


def _route_register(_app):
    """Stands in for a non-component entry-point value (route registrar)."""


# ---------------------------------------------------------------------------
# installed_extension_roots
# ---------------------------------------------------------------------------


def test_finds_manifest_shipping_distribution(tmp_path: Path) -> None:
    dist = make_installed_extension(tmp_path, "lfx-pilot")
    roots = installed_extension_roots(distributions=[dist])
    assert "lfx-pilot" in roots
    assert (roots["lfx-pilot"] / "extension.json").is_file()


def test_canonicalizes_distribution_name(tmp_path: Path) -> None:
    """PEP-503: ``Lfx_Pilot`` and ``lfx-pilot`` are the same distribution."""
    dist = make_installed_extension(tmp_path, "lfx-pilot")
    # Override the metadata Name to test the canonicalize path.
    dist._name = "LFX_Pilot"
    roots = installed_extension_roots(distributions=[dist])
    assert list(roots) == ["lfx-pilot"]


def test_ignores_distributions_without_manifest(tmp_path: Path) -> None:
    plain_dist = FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    roots = installed_extension_roots(distributions=[plain_dist])
    assert roots == {}


def test_handles_files_none(tmp_path: Path) -> None:
    dist = FakeDist("orphan", tmp_path, files=None)
    roots = installed_extension_roots(distributions=[dist])
    assert roots == {}


# ---------------------------------------------------------------------------
# pyproject.toml manifest discovery (the AC's second supported manifest form)
# ---------------------------------------------------------------------------


def test_finds_pyproject_only_distribution(tmp_path: Path) -> None:
    """A distribution shipping pyproject.toml with [tool.langflow.extension] is found."""
    dist = make_installed_pyproject_extension(tmp_path, "lfx-pyproject")
    roots = installed_extension_roots(distributions=[dist])
    assert "lfx-pyproject" in roots
    assert (roots["lfx-pyproject"] / "pyproject.toml").is_file()


def test_pyproject_without_extension_section_is_ignored(tmp_path: Path) -> None:
    """A pyproject.toml without [tool.langflow.extension] is NOT treated as a manifest.

    Defensive: many regular packages ship pyproject.toml; we must only
    accept it as a manifest source when the section actually exists.
    """
    dist = make_installed_pyproject_no_extension(tmp_path, "plain-pyproject")
    roots = installed_extension_roots(distributions=[dist])
    assert roots == {}


def test_malformed_pyproject_section_surfaces_manifest_invalid(tmp_path: Path) -> None:
    """A pyproject with [tool.langflow.extension] missing required fields surfaces manifest-invalid.

    Detection MUST be presence-only: if the section exists but pydantic
    validation fails, the distribution is still discovered as a
    manifest-shipping Extension and ``load_installed_extensions`` produces
    a typed ``manifest-invalid`` :class:`LoadResult`. Conflating "section
    absent" with "section malformed" would silently drop the
    distribution, hiding the typo from operators and skipping the
    manifest-first suppression of legacy component entry-points.
    """
    from lfx.extension import load_installed_extensions

    dist = make_installed_pyproject_malformed_extension(tmp_path, "lfx-bad-pyproject")
    # Discovery must classify the distribution as manifest-shipping despite
    # the broken section, so manifest-first precedence still suppresses any
    # legacy entry-points it might have.
    owners = manifest_owning_distributions(distributions=[dist])
    assert "lfx-bad-pyproject" in owners

    # And load_installed_extensions must produce a typed failure result, not
    # silently return an empty list.
    results = load_installed_extensions(distributions=[dist])
    assert len(results) == 1, f"expected exactly one LoadResult, got {results}"
    result = results[0]
    assert not result.ok
    codes = [e.code for e in result.errors]
    assert "manifest-invalid" in codes, codes
    assert result.distribution == "lfx-bad-pyproject"
    err = next(e for e in result.errors if e.code == "manifest-invalid")
    assert err.hint  # AC: fix-hint payload on failure
    assert err.ref_url


def test_malformed_pyproject_section_suppresses_legacy_component_entry_point(tmp_path: Path) -> None:
    """Manifest-first precedence applies even when the pyproject manifest is malformed.

    If the section exists, the distribution is manifest-shipping by intent;
    its legacy ``langflow.plugins`` component entry-points must be
    suppressed regardless of whether the manifest itself validates --
    otherwise the AC's "loaded once via manifest" promise breaks for any
    pyproject author who typo'd a field.
    """
    dist = make_installed_pyproject_malformed_extension(tmp_path, "lfx-bad-pyproject")
    component_ep = FakeEntryPoint("BadComp", dist, loaded_value=_LegacyPluginComponent)

    owners = manifest_owning_distributions(distributions=[dist])
    kept, skipped = filter_component_entry_points([component_ep], skip=owners)
    assert [ep.name for ep in skipped] == ["BadComp"]
    assert kept == []


def test_extension_json_wins_over_pyproject(tmp_path: Path) -> None:
    """When both forms ship, extension.json wins (matches load_manifest order)."""
    pkg_dir = tmp_path / "lfx-both"
    pkg_dir.mkdir()
    manifest = {
        "id": "lfx-both",
        "version": "1.0.0",
        "name": "lfx-both",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": "both", "path": "components"}],
    }
    (pkg_dir / "extension.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "lfx-both"\n[tool.langflow.extension]\nid = "lfx-both"\n',
        encoding="utf-8",
    )
    dist = FakeDist(
        name="lfx-both",
        root=tmp_path,
        files=[Path("lfx-both") / "extension.json", Path("lfx-both") / "pyproject.toml"],
    )
    roots = installed_extension_roots(distributions=[dist])
    # Both forms point at the same root directory, but the manifest path
    # used for resolution should be the JSON file.
    assert "lfx-both" in roots
    assert (roots["lfx-both"] / "extension.json").is_file()


def test_pyproject_only_extension_loads_at_official_slot(tmp_path: Path) -> None:
    """End-to-end: a pyproject-only Extension is discovered by load_installed_extensions.

    Without this path the AC's "extension.json or [tool.langflow.extension]"
    wording is half-implemented.
    """
    from lfx.extension import load_installed_extensions

    dist = make_installed_pyproject_extension(tmp_path, "lfx-pyproject")
    # Populate the bundle directory referenced by the pyproject manifest.
    bundle_dir = tmp_path / "lfx-pyproject" / "components"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "thing.py").write_text(
        "class Component:\n    pass\nclass Thing(Component):\n    pass\n",
        encoding="utf-8",
    )

    results = load_installed_extensions(distributions=[dist])
    assert len(results) == 1
    result = results[0]
    assert result.ok, [e.code for e in result.errors]
    assert result.distribution == "lfx-pyproject"
    assert result.extension_id == "lfx-pyproject"
    # Bundle name comes from the pyproject manifest section.
    assert result.bundle == "lfx_pyproject"
    assert result.components, "pyproject-form Extension should yield components"


def test_pyproject_only_distribution_suppresses_legacy_component_entry_point(tmp_path: Path) -> None:
    """Manifest-first precedence applies to pyproject-form Extensions too.

    A legacy ``langflow.plugins`` component entry-point on a pyproject-form
    manifest-shipping distribution must be skipped exactly like the JSON
    form, otherwise the same-distribution double-registration the AC
    forbids would still occur.
    """
    dist = make_installed_pyproject_extension(tmp_path, "lfx-pyproject")
    component_ep = FakeEntryPoint("PyComponent", dist, loaded_value=_LegacyPluginComponent)

    owners = manifest_owning_distributions(distributions=[dist])
    assert "lfx-pyproject" in owners
    kept, skipped = filter_component_entry_points([component_ep], skip=owners)
    assert [ep.name for ep in skipped] == ["PyComponent"]
    assert kept == []


# ---------------------------------------------------------------------------
# manifest_owning_distributions
# ---------------------------------------------------------------------------


def test_owning_distributions_is_set_of_canonical_names(tmp_path: Path) -> None:
    dist = make_installed_extension(tmp_path, "lfx-pilot")
    other = FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    owners = manifest_owning_distributions(distributions=[dist, other])
    assert owners == frozenset({"lfx-pilot"})


# ---------------------------------------------------------------------------
# filter_plugin_entry_points (the AC test)
# ---------------------------------------------------------------------------


def test_skips_manifest_shipping_distribution(tmp_path: Path) -> None:
    """Manifest-first precedence: AC test for "loaded once via manifest".

    Package with manifest + legacy component entry-point loads its
    components ONCE via the manifest, not twice.  We model "loaded once"
    by partitioning the entry points: the manifest's distribution lands in
    ``skipped`` (the loader's manifest path will register them), while
    non-component entry-points on a distribution that does NOT ship a
    manifest are kept (the legacy path still runs for those).
    """
    manifest_dist = make_installed_extension(tmp_path, "lfx-pilot")
    other_dist = FakeDist("legacy-pkg", tmp_path, files=[Path("legacy_pkg/__init__.py")])

    eps = [
        FakeEntryPoint("PilotComponent", manifest_dist),  # should be skipped
        FakeEntryPoint("LegacyComponent", other_dist),  # should be kept
    ]
    kept, skipped = filter_plugin_entry_points(
        eps,
        skip=manifest_owning_distributions(distributions=[manifest_dist, other_dist]),
    )
    assert [ep.name for ep in kept] == ["LegacyComponent"]
    assert [ep.name for ep in skipped] == ["PilotComponent"]


def test_keeps_entry_points_without_distribution() -> None:
    """Defensive: dist=None on an EntryPoint shouldn't drop it.

    Some Python packagers expose entry points without a back-reference to
    the owning distribution (e.g. older wheel formats).  We err on the side
    of compatibility and keep those entry points.
    """
    ep = FakeEntryPoint("Orphan", None)
    kept, skipped = filter_plugin_entry_points([ep], skip=frozenset({"lfx-pilot"}))
    assert kept == [ep]
    assert skipped == []


def test_uses_real_distributions_by_default(tmp_path: Path) -> None:
    """When ``skip`` is omitted, the filter consults the real environment.

    The default value calls into ``importlib.metadata.distributions``;
    Langflow itself does not ship an extension manifest today, but if a
    transitive test-only dep ever does, ``kept`` / ``skipped`` could pick
    up additional entries we don't control. Robust assertion: pin the
    synthetic ``ep``'s placement (kept, not skipped) without requiring the
    output lists to be exactly ``[ep]`` / ``[]``.
    """
    plain = FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    ep = FakeEntryPoint("PlainComponent", plain)
    kept, skipped = filter_plugin_entry_points([ep])
    assert ep in kept
    assert ep not in skipped


# ---------------------------------------------------------------------------
# canonicalize_distribution
# ---------------------------------------------------------------------------


def test_canonicalize_distribution_matches_pep503() -> None:
    assert canonicalize_distribution("Lfx-Pilot") == "lfx-pilot"
    assert canonicalize_distribution("lfx_pilot") == "lfx-pilot"
    assert canonicalize_distribution("LFX...PILOT") == "lfx-pilot"


# ---------------------------------------------------------------------------
# Module-level smoke
# ---------------------------------------------------------------------------


def test_importlib_metadata_distribution_is_available() -> None:
    """Sanity check that the stdlib API the precedence helpers rely on exists."""
    assert hasattr(importlib_metadata, "distributions")


# ---------------------------------------------------------------------------
# filter_component_entry_points: type-aware (the runtime AC test)
# ---------------------------------------------------------------------------


def test_component_filter_skips_only_component_entry_points(tmp_path: Path) -> None:
    """AC: same distribution exposes BOTH a component EP and a non-component EP.

    Manifest-shipping distribution -> component EP gets skipped (manifest
    is the source of truth), but the non-component (route) EP keeps loading
    via the legacy path. This is the case the previous reviewer flagged as
    missing.
    """
    manifest_dist = make_installed_extension(tmp_path, "lfx-pilot")
    component_ep = FakeEntryPoint("PilotComponent", manifest_dist, loaded_value=_LegacyPluginComponent)
    route_ep = FakeEntryPoint("pilot_routes", manifest_dist, loaded_value=_route_register)

    kept, skipped = filter_component_entry_points(
        [component_ep, route_ep],
        skip=manifest_owning_distributions(distributions=[manifest_dist]),
    )
    assert [ep.name for ep in kept] == ["pilot_routes"]
    assert [ep.name for ep in skipped] == ["PilotComponent"]


def test_component_filter_keeps_components_on_non_manifest_distribution(tmp_path: Path) -> None:
    """A component EP on a distribution that does NOT ship a manifest stays kept.

    The legacy ``langflow.plugins`` path is still the registration channel
    for those distributions; filtering them would silently drop them.
    """
    other_dist = FakeDist("legacy-pkg", tmp_path, files=[Path("legacy_pkg/__init__.py")])
    component_ep = FakeEntryPoint("LegacyComponent", other_dist, loaded_value=_LegacyPluginComponent)
    kept, skipped = filter_component_entry_points([component_ep], skip=frozenset())
    assert [ep.name for ep in kept] == ["LegacyComponent"]
    assert skipped == []


def test_component_filter_handles_unloadable_entry_point(tmp_path: Path) -> None:
    """Defensive: an entry-point whose load() raises is treated as non-component.

    The resulting partition keeps it (so the legacy loader can decide what
    to do), rather than swallowing it as if it were component.
    """

    class _ExplodingEP(FakeEntryPoint):
        def load(self) -> object:
            msg = "boom"
            raise RuntimeError(msg)

    manifest_dist = make_installed_extension(tmp_path, "lfx-pilot")
    bad_ep = _ExplodingEP("Boom", manifest_dist, loaded_value=None)
    kept, skipped = filter_component_entry_points(
        [bad_ep],
        skip=manifest_owning_distributions(distributions=[manifest_dist]),
    )
    assert [ep.name for ep in kept] == ["Boom"]
    assert skipped == []
