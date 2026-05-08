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

from .conftest import FakeDist, FakeEntryPoint, make_installed_extension


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

    The default value calls into ``importlib.metadata.distributions``; we
    don't expect any test-runtime distribution to ship an extension
    manifest, so the result is a no-op partition (everything kept).  This
    exercises the default-path code without coupling the test to the host
    environment's installed packages.
    """
    plain = FakeDist("plain-pkg", tmp_path, files=[Path("plain_pkg/__init__.py")])
    ep = FakeEntryPoint("PlainComponent", plain)
    kept, skipped = filter_plugin_entry_points([ep])
    assert kept == [ep]
    assert skipped == []


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
