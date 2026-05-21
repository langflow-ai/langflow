"""Discovery tests for installed-distribution + seed-directory sources.

Two integration pieces:

    * Three "installed" distributions surfaced via a fake
      ``importlib.metadata.distributions()`` iterator -- mirrors the
      ``pip install`` path without paying the cost of building real
      wheels in the unit-test pipeline. ``test_e2e_install.py`` covers
      the genuine ``pip install`` path; this file pins the in-process
      contract.

    * A seed directory with three bundle subdirectories.

Plus per-failure coverage: malformed manifests surface typed errors
without aborting the scan, and explicitly-configured-but-missing seed
roots emit ``seed-directory-not-found``.
"""

from __future__ import annotations

import json
import os
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.discovery import (
    DEFAULT_SEED_DIR,
    SEED_DIR_ENV_VAR,
    canonicalize_distribution,
    discover_all_extensions,
    discover_installed_extensions,
    discover_seed_extensions,
)
from lfx.extension.manifest import ManifestSource

# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

_BUNDLE_NAMES = ("openai", "anthropic", "qdrant")


def _manifest(extension_id: str, bundle_name: str, version: str = "1.0.0") -> dict[str, object]:
    """Build a minimal v0 manifest dict.  Bundle path is the bundle name."""
    return {
        "id": extension_id,
        "version": version,
        "name": f"{extension_id} bundle",
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": bundle_name, "path": bundle_name}],
    }


def _write_extension_json(root: Path, manifest: dict[str, object]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    bundle_name = manifest["bundles"][0]["name"]  # type: ignore[index]
    (root / bundle_name).mkdir(exist_ok=True)
    (root / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root / "extension.json"


def _write_pyproject_extension(root: Path, manifest: dict[str, object]) -> Path:
    """Drop a pyproject.toml that declares ``[tool.langflow.extension]``.

    Used to confirm the loader accepts both manifest forms; one of the
    three "installed" distributions in :func:`fake_installed_distributions`
    uses this form so we get coverage automatically.
    """
    import sys

    if sys.version_info >= (3, 11):
        import tomllib  # type: ignore[import-not-found]
    else:
        import tomli as tomllib  # type: ignore[import-not-found]  # noqa: F401

    root.mkdir(parents=True, exist_ok=True)
    bundle_name = manifest["bundles"][0]["name"]  # type: ignore[index]
    (root / bundle_name).mkdir(exist_ok=True)
    body = "[tool.langflow.extension]\n"
    body += f'id = "{manifest["id"]}"\n'
    body += f'version = "{manifest["version"]}"\n'
    body += f'name = "{manifest["name"]}"\n'
    body += "\n"
    body += "[tool.langflow.extension.lfx]\n"
    body += 'compat = ["1"]\n'
    body += "\n"
    body += "[[tool.langflow.extension.bundles]]\n"
    body += f'name = "{bundle_name}"\n'
    body += f'path = "{bundle_name}"\n'
    (root / "pyproject.toml").write_text(body, encoding="utf-8")
    return root / "pyproject.toml"


# ---------------------------------------------------------------------------
# Fake importlib.metadata.Distribution
# ---------------------------------------------------------------------------


class _FakeDistribution(importlib_metadata.Distribution):
    """In-memory Distribution stub.

    ``importlib.metadata.Distribution`` is an ABC; this minimal subclass
    satisfies the two abstract members the discovery code uses
    (``files`` and ``locate_file``) plus ``metadata`` for the canonical
    name lookup.
    """

    def __init__(self, *, name: str, root: Path, manifest_relative: str) -> None:
        self._name = name
        self._root = root
        self._manifest_relative = manifest_relative

    @property
    def files(self) -> list[importlib_metadata.PackagePath]:  # type: ignore[override]
        path = importlib_metadata.PackagePath(self._manifest_relative)
        return [path]

    def locate_file(self, path: object) -> Path:  # type: ignore[override]
        return self._root / Path(str(path))

    def read_text(self, filename: str) -> str | None:  # type: ignore[override]
        if filename in {"METADATA", "PKG-INFO"}:
            return f"Metadata-Version: 2.1\nName: {self._name}\nVersion: 1.0.0\n"
        return None

    @property
    def metadata(self) -> object:  # type: ignore[override]
        # ``importlib.metadata.Distribution.metadata`` returns an
        # ``email.message.Message``; for our purposes a dict-like with
        # ``__getitem__`` is sufficient because the discovery code only
        # reads ``["Name"]``.
        class _Stub(dict):
            pass

        return _Stub({"Name": self._name})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_installed_distributions(tmp_path: Path) -> list[_FakeDistribution]:
    """Stand up three in-memory distributions that ship valid manifests.

    Two use ``extension.json``; one uses ``pyproject.toml`` so we exercise
    both manifest forms in a single integration sweep.
    """
    dists: list[_FakeDistribution] = []
    for index, bundle in enumerate(_BUNDLE_NAMES):
        ext_root = tmp_path / f"site-packages/lfx_{bundle}"
        ext_id = f"lfx-{bundle}"
        manifest = _manifest(extension_id=ext_id, bundle_name=bundle, version=f"1.{index}.0")
        if index == 1:
            manifest_path = _write_pyproject_extension(ext_root, manifest)
            relative = "pyproject.toml"
        else:
            manifest_path = _write_extension_json(ext_root, manifest)
            relative = "extension.json"
        # sanity: file actually landed where we said it would.
        assert manifest_path.exists()
        dists.append(_FakeDistribution(name=ext_id, root=ext_root, manifest_relative=relative))
    return dists


@pytest.fixture
def seed_dir_with_three_bundles(tmp_path: Path) -> Path:
    """Build a seed directory containing three valid bundle subdirectories."""
    seed = tmp_path / "seed"
    seed.mkdir()
    for index, bundle in enumerate(_BUNDLE_NAMES):
        sub = seed / f"lfx_{bundle}"
        manifest = _manifest(extension_id=f"lfx-{bundle}", bundle_name=bundle, version=f"2.{index}.0")
        _write_extension_json(sub, manifest)
    return seed


# ---------------------------------------------------------------------------
# Installed-distribution discovery
# ---------------------------------------------------------------------------


def test_discover_installed_finds_three_distributions(
    fake_installed_distributions: list[_FakeDistribution],
) -> None:
    extensions, errors = discover_installed_extensions(distributions=fake_installed_distributions)

    assert errors == []
    assert len(extensions) == 3
    ids = sorted(ext.extension_id for ext in extensions)
    assert ids == ["lfx-anthropic", "lfx-openai", "lfx-qdrant"]
    # Every installed Extension lives at @official by invariant.
    for ext in extensions:
        assert ext.source_kind == "installed"
        assert ext.slot == "official"


def test_discover_installed_records_carry_manifest_source(
    fake_installed_distributions: list[_FakeDistribution],
) -> None:
    extensions, _ = discover_installed_extensions(distributions=fake_installed_distributions)
    for ext in extensions:
        assert isinstance(ext.manifest, ManifestSource)
        assert ext.manifest.path.exists()
        assert ext.extension_root == ext.manifest.path.parent


def test_discover_installed_accepts_pyproject_form(
    fake_installed_distributions: list[_FakeDistribution],
) -> None:
    extensions, _ = discover_installed_extensions(distributions=fake_installed_distributions)
    by_id = {ext.extension_id: ext for ext in extensions}
    # The middle distribution (anthropic) used pyproject.toml.
    assert by_id["lfx-anthropic"].manifest.kind == "pyproject.toml"
    assert by_id["lfx-openai"].manifest.kind == "extension.json"


def test_discover_installed_skips_non_manifest_distributions(tmp_path: Path) -> None:
    """A regular Python package with no manifest should be silently ignored."""
    plain = tmp_path / "site-packages/regular"
    plain.mkdir(parents=True)
    (plain / "regular.py").write_text("# nothing to see here\n", encoding="utf-8")
    dist = _FakeDistribution(name="regular", root=plain, manifest_relative="regular.py")

    extensions, errors = discover_installed_extensions(distributions=[dist])
    assert extensions == []
    assert errors == []


def test_discover_installed_emits_typed_error_on_malformed_manifest(tmp_path: Path) -> None:
    """A malformed extension.json surfaces a typed error.

    The scan continues and the rest of the dist iterator is unaffected.
    """
    bad_root = tmp_path / "site-packages/lfx_broken"
    bad_root.mkdir(parents=True)
    (bad_root / "extension.json").write_text("{ this is not json", encoding="utf-8")
    bad = _FakeDistribution(name="lfx-broken", root=bad_root, manifest_relative="extension.json")

    good_root = tmp_path / "site-packages/lfx_openai"
    _write_extension_json(good_root, _manifest("lfx-openai", "openai"))
    good = _FakeDistribution(name="lfx-openai", root=good_root, manifest_relative="extension.json")

    extensions, errors = discover_installed_extensions(distributions=[bad, good])

    assert len(errors) == 1
    assert errors[0].code == "manifest-unreadable"
    assert "lfx-broken" in errors[0].content if errors[0].content else True
    assert len(extensions) == 1
    assert extensions[0].extension_id == "lfx-openai"


def test_discover_installed_emits_typed_error_on_schema_failure(tmp_path: Path) -> None:
    """A parseable but invalid manifest surfaces ``manifest-invalid``."""
    root = tmp_path / "site-packages/lfx_bad_schema"
    root.mkdir(parents=True)
    # Missing ``lfx`` field -- pydantic will reject this.
    (root / "extension.json").write_text(
        json.dumps({"id": "lfx-x", "version": "1.0.0", "name": "X", "bundles": []}),
        encoding="utf-8",
    )
    dist = _FakeDistribution(name="lfx-x", root=root, manifest_relative="extension.json")

    extensions, errors = discover_installed_extensions(distributions=[dist])
    assert extensions == []
    assert len(errors) == 1
    assert errors[0].code == "manifest-invalid"


def test_canonicalize_distribution_normalizes_per_pep503() -> None:
    assert canonicalize_distribution("LFX_OpenAI") == "lfx-openai"
    assert canonicalize_distribution("lfx.openai") == "lfx-openai"
    assert canonicalize_distribution("lfx--OpenAI") == "lfx-openai"


# ---------------------------------------------------------------------------
# Editable install entry-point fallback
# ---------------------------------------------------------------------------


class _EditableDistribution(importlib_metadata.Distribution):
    """In-memory editable Distribution stub.

    Mirrors what ``uv pip install -e`` / ``pip install -e`` produce: the
    distribution's ``files`` list contains only ``dist-info/`` entries
    (the actual source tree is reached via a ``.pth`` file rather than
    listed in RECORD), and the ``langflow.extensions`` entry-point is
    what the manifest discovery has to lean on.
    """

    def __init__(self, *, name: str, module_name: str) -> None:
        self._name = name
        self._module_name = module_name

    @property
    def files(self) -> list[importlib_metadata.PackagePath]:  # type: ignore[override]
        # Editable installs only surface dist-info entries -- no
        # ``extension.json`` and no source ``pyproject.toml``.
        slug = self._name.replace("-", "_")
        return [
            importlib_metadata.PackagePath(f"{slug}-0.1.0.dist-info/METADATA"),
            importlib_metadata.PackagePath(f"{slug}-0.1.0.dist-info/RECORD"),
            importlib_metadata.PackagePath(f"_editable_impl_{slug}.pth"),
        ]

    def locate_file(self, path: object) -> Path:  # type: ignore[override]
        return Path(str(path))

    def read_text(self, filename: str) -> str | None:  # type: ignore[override]
        if filename in {"METADATA", "PKG-INFO"}:
            return f"Metadata-Version: 2.1\nName: {self._name}\nVersion: 1.0.0\n"
        return None

    @property
    def metadata(self) -> object:  # type: ignore[override]
        class _Stub(dict):
            pass

        return _Stub({"Name": self._name})

    @property
    def entry_points(self) -> list[importlib_metadata.EntryPoint]:  # type: ignore[override]
        return [
            importlib_metadata.EntryPoint(
                name=self._name,
                value=self._module_name,
                group="langflow.extensions",
            )
        ]


def _make_editable_package(
    site_root: Path,
    *,
    module_name: str,
    manifest: dict[str, object],
) -> Path:
    """Stand up a real importable package on disk with an ``extension.json``."""
    pkg_dir = site_root / module_name
    bundle_name = manifest["bundles"][0]["name"]  # type: ignore[index]
    (pkg_dir / bundle_name).mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pkg_dir


def test_discover_installed_falls_back_to_entry_point_for_editable_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editable installs are discovered via the ``langflow.extensions`` entry-point.

    Reproduces the editable-install bug: ``dist.files`` only carries
    ``dist-info/`` entries, so the file-walk path finds no manifest.  The
    entry-point fallback resolves the package directory via
    :func:`importlib.util.find_spec` and locates ``extension.json`` there.
    """
    site = tmp_path / "src"
    site.mkdir()
    _make_editable_package(
        site,
        module_name="lfx_editable_bundle",
        manifest=_manifest("lfx-editable-bundle", "bundle"),
    )

    monkeypatch.syspath_prepend(str(site))
    # Drop any cached spec from a previous test invocation.
    import sys

    sys.modules.pop("lfx_editable_bundle", None)

    dist = _EditableDistribution(
        name="lfx-editable-bundle",
        module_name="lfx_editable_bundle",
    )

    extensions, errors = discover_installed_extensions(distributions=[dist])

    assert errors == []
    assert len(extensions) == 1
    ext = extensions[0]
    assert ext.extension_id == "lfx-editable-bundle"
    assert ext.source_kind == "installed"
    assert ext.bundle_name == "bundle"
    assert ext.manifest.kind == "extension.json"
    assert ext.extension_root == site / "lfx_editable_bundle"


def test_discover_installed_entry_point_fallback_handles_missing_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An entry-point pointing at an unimportable module yields no result, no crash."""
    # No package on sys.path corresponds to ``lfx_nonexistent``.
    monkeypatch.syspath_prepend(str(tmp_path))
    import sys

    sys.modules.pop("lfx_nonexistent_bundle", None)

    dist = _EditableDistribution(
        name="lfx-nonexistent-bundle",
        module_name="lfx_nonexistent_bundle",
    )

    extensions, errors = discover_installed_extensions(distributions=[dist])

    # Unresolvable entry-point is treated as "no manifest here", same as a
    # regular non-extension package -- no error, no record.
    assert extensions == []
    assert errors == []


def test_discover_installed_entry_point_fallback_skipped_when_files_have_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``dist.files`` already exposes the manifest, the entry-point path is unused.

    Guards the wheel-install codepath (the common case) from being
    accidentally rerouted through ``find_spec`` -- which would otherwise
    re-import every bundle package on every startup.
    """
    site = tmp_path / "site-packages/lfx_wheelish"
    _write_extension_json(site, _manifest("lfx-wheelish", "wheelish"))
    monkeypatch.syspath_prepend(str(tmp_path / "site-packages"))

    # Sentinel: if find_spec is consulted, we'd notice.
    import importlib.util as _importlib_util

    calls = {"n": 0}
    real_find_spec = _importlib_util.find_spec

    def _tracking_find_spec(name: str, package: str | None = None) -> object:
        calls["n"] += 1
        return real_find_spec(name, package)

    monkeypatch.setattr(_importlib_util, "find_spec", _tracking_find_spec)

    dist = _FakeDistribution(
        name="lfx-wheelish",
        root=site,
        manifest_relative="extension.json",
    )
    extensions, errors = discover_installed_extensions(distributions=[dist])

    assert errors == []
    assert len(extensions) == 1
    assert calls["n"] == 0, "Wheel-install path should not consult find_spec"


# ---------------------------------------------------------------------------
# Seed-directory discovery
# ---------------------------------------------------------------------------


def test_discover_seed_finds_three_subdirectories(seed_dir_with_three_bundles: Path) -> None:
    extensions, errors = discover_seed_extensions(seed_dir_env=str(seed_dir_with_three_bundles))

    assert errors == []
    assert len(extensions) == 3
    for ext in extensions:
        assert ext.source_kind == "seed"
        assert ext.slot == "official"
        assert Path(ext.source).is_dir()


def test_discover_seed_supports_pathsep_multiple_roots(tmp_path: Path) -> None:
    """``$LANGFLOW_SEED_DIR`` accepts multiple roots joined by ``os.pathsep``."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _write_extension_json(root_a / "lfx_openai", _manifest("lfx-openai", "openai"))
    _write_extension_json(root_b / "lfx_anthropic", _manifest("lfx-anthropic", "anthropic"))

    composite = f"{root_a}{os.pathsep}{root_b}"
    extensions, errors = discover_seed_extensions(seed_dir_env=composite)

    assert errors == []
    assert {ext.extension_id for ext in extensions} == {"lfx-openai", "lfx-anthropic"}


def test_discover_seed_surfaces_missing_configured_dir(tmp_path: Path) -> None:
    """An explicitly-configured but missing seed dir emits a typed error."""
    missing = tmp_path / "does_not_exist"
    extensions, errors = discover_seed_extensions(seed_dir_env=str(missing))

    assert extensions == []
    assert len(errors) == 1
    assert errors[0].code == "seed-directory-not-found"


def test_discover_seed_silent_when_default_missing(tmp_path: Path) -> None:
    """A non-existent default seed dir is silently skipped (Mode A laptop)."""
    extensions, errors = discover_seed_extensions(seed_dir_env="", default=tmp_path / "missing")
    assert extensions == []
    assert errors == []


def test_discover_seed_skips_directories_without_manifest(tmp_path: Path) -> None:
    """Operators may stage non-extension content alongside bundles."""
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "garbage").mkdir()
    (seed / "garbage" / "README.md").write_text("just docs\n")
    _write_extension_json(seed / "lfx_openai", _manifest("lfx-openai", "openai"))

    extensions, errors = discover_seed_extensions(seed_dir_env=str(seed))

    assert errors == []
    assert [ext.extension_id for ext in extensions] == ["lfx-openai"]


def test_discover_seed_skips_dot_directories(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    hidden = seed / ".cache"
    hidden.mkdir()
    _write_extension_json(hidden, _manifest("lfx-hidden", "hidden"))
    _write_extension_json(seed / "lfx_visible", _manifest("lfx-visible", "visible"))

    extensions, _ = discover_seed_extensions(seed_dir_env=str(seed))
    ids = {ext.extension_id for ext in extensions}
    assert ids == {"lfx-visible"}


def test_discover_seed_emits_typed_error_on_malformed_manifest(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    bad = seed / "lfx_broken"
    bad.mkdir()
    (bad / "extension.json").write_text("{ not json", encoding="utf-8")
    # Plus a healthy neighbour to confirm the scan keeps going.
    _write_extension_json(seed / "lfx_openai", _manifest("lfx-openai", "openai"))

    extensions, errors = discover_seed_extensions(seed_dir_env=str(seed))

    assert {ext.extension_id for ext in extensions} == {"lfx-openai"}
    assert len(errors) == 1
    assert errors[0].code == "manifest-invalid"


def test_discover_seed_uses_default_when_env_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``seed_dir_env=None`` falls through to the live env-var lookup."""
    seed = tmp_path / "default_seed"
    _write_extension_json(seed / "lfx_openai", _manifest("lfx-openai", "openai"))
    monkeypatch.delenv(SEED_DIR_ENV_VAR, raising=False)

    extensions, errors = discover_seed_extensions(default=seed)
    assert errors == []
    assert {ext.extension_id for ext in extensions} == {"lfx-openai"}


def test_default_seed_dir_constant_is_opt_langflow_bundles() -> None:
    """Pinning the documented default so docs and code agree."""
    assert Path("/opt/langflow/bundles") == DEFAULT_SEED_DIR


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------


def test_discover_all_merges_installed_and_seed(
    fake_installed_distributions: list[_FakeDistribution],
    tmp_path: Path,
) -> None:
    """``discover_all_extensions`` returns installed first, then seeded."""
    seed = tmp_path / "seed"
    _write_extension_json(seed / "lfx_seed_only", _manifest("lfx-seed-only", "seed_only"))

    extensions, errors = discover_all_extensions(
        distributions=fake_installed_distributions,
        seed_dir_env=str(seed),
        default_seed_dir=None,
    )

    assert errors == []
    # Three installed + one seed.
    assert len(extensions) == 4
    # Installed precede seeded.
    assert [ext.source_kind for ext in extensions] == [
        "installed",
        "installed",
        "installed",
        "seed",
    ]
    assert any(ext.extension_id == "lfx-seed-only" for ext in extensions)


def test_discover_all_emits_seed_bundle_shadowed_when_ids_collide(
    fake_installed_distributions: list[_FakeDistribution],
    tmp_path: Path,
) -> None:
    """A seed bundle with the same id as an installed one is flagged, not silently dropped.

    Installed wins by precedence (documented contract); the operator
    still gets a typed ``seed-bundle-shadowed`` error so the shadow is
    visible instead of disappearing into discovery debug logs.
    """
    # ``fake_installed_distributions`` ships ``lfx-openai``; the seed dir
    # below carries the same id from a different on-disk source.
    seed = tmp_path / "seed"
    shadow_root = seed / "lfx_openai_shadow"
    _write_extension_json(shadow_root, _manifest("lfx-openai", "openai", version="9.9.9"))
    fresh_root = seed / "lfx_only_seed"
    _write_extension_json(fresh_root, _manifest("lfx-only-seed", "only_seed"))

    extensions, errors = discover_all_extensions(
        distributions=fake_installed_distributions,
        seed_dir_env=str(seed),
        default_seed_dir=None,
    )

    # The non-colliding seed bundle survives; the shadowed one does not.
    extension_ids = [ext.extension_id for ext in extensions]
    assert extension_ids.count("lfx-openai") == 1
    assert any(ext.extension_id == "lfx-openai" and ext.source_kind == "installed" for ext in extensions)
    assert any(ext.extension_id == "lfx-only-seed" for ext in extensions)

    shadow_errors = [err for err in errors if err.code == "seed-bundle-shadowed"]
    assert len(shadow_errors) == 1
    [err] = shadow_errors
    assert err.content == "lfx-openai"
    assert str(shadow_root.resolve(strict=False)) in err.location or str(shadow_root) in err.location


def test_discover_all_handles_partial_failures(tmp_path: Path) -> None:
    """A broken installed dist plus a missing seed dir both surface errors.

    Neither aborts the other source's scan.
    """
    bad_root = tmp_path / "site-packages/lfx_broken"
    bad_root.mkdir(parents=True)
    (bad_root / "extension.json").write_text("not json", encoding="utf-8")
    bad = _FakeDistribution(name="lfx-broken", root=bad_root, manifest_relative="extension.json")

    extensions, errors = discover_all_extensions(
        distributions=[bad],
        seed_dir_env=str(tmp_path / "seed_missing"),
        default_seed_dir=None,
    )

    assert extensions == []
    codes = sorted(err.code for err in errors)
    assert "manifest-unreadable" in codes
    assert "seed-directory-not-found" in codes
