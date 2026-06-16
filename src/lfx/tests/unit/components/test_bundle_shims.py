"""Contract tests for the lfx-bundles import shims under ``lfx/components/``.

Providers consolidated into the lfx-bundles metapackage (and partners
graduated to standalone ``lfx-<provider>`` distributions) leave a one-file
module-aliasing shim at their old in-tree location.  The shim contract,
locked here:

  1. First line is the ``# lfx-bundles-shim`` marker -- the in-tree component
     walk (:func:`lfx.interface.components._discover_shimmed_component_dirs`)
     keys on it to avoid double registration.
  2. The shim dir contains exactly one ``.py`` file (no implementations, no
     third-party deps) -- this is how "lfx ships no components" coexists with
     working legacy imports.
  3. ``sys.modules[__name__]`` is aliased to the bundle package (module
     aliasing, not star-import, so submodule trees resolve).
  4. When the bundle distribution itself is missing, the shim raises an
     actionable ``ModuleNotFoundError`` naming exactly what to install --
     the WORDING IS PART OF THE CONTRACT (docs reference it).
  5. A missing *transitive* dependency (bundle present, SDK absent) is
     re-raised untouched so a real bug is never misreported as "install
     missing".

The mechanism tests run against a synthetic shim + synthetic target so they
are hermetic; the source-level tests sweep every real shim without importing
it (env-independent); one adaptive live test exercises whichever branch the
current environment is in.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

# tests/unit/components/<this file> -> parents[3] = the src/lfx package root.
COMPONENTS_DIR = Path(__file__).resolve().parents[3] / "src" / "lfx" / "components"
SHIM_MARKER = "# lfx-bundles-shim"

# The two install-message shapes the shims are allowed to emit.
_METAPACKAGE_MSG = "pip install lfx-bundles"
_PARTNER_MSG_PREFIX = "pip install lfx-"


def _shim_dirs() -> list[Path]:
    """Every provider dir under lfx/components whose __init__ carries the marker."""
    found = []
    for child in sorted(COMPONENTS_DIR.iterdir()):
        init_py = child / "__init__.py"
        if child.is_dir() and init_py.is_file():
            try:
                head = init_py.read_text(encoding="utf-8").lstrip()
            except OSError:
                continue
            if head.startswith(SHIM_MARKER):
                found.append(child)
    return found


SHIM_DIRS = _shim_dirs()


# ---------------------------------------------------------------------------
# Source-level contract sweep (no imports; env-independent)
# ---------------------------------------------------------------------------


def test_shims_exist() -> None:
    """The consolidation left shims behind; an empty list means the sweep is broken."""
    assert SHIM_DIRS, f"no marker shims found under {COMPONENTS_DIR}"


@pytest.mark.parametrize("shim_dir", SHIM_DIRS, ids=lambda p: p.name)
def test_shim_is_one_file_stub(shim_dir: Path) -> None:
    """Contract #2: a shim dir ships exactly one .py file and no subpackages."""
    py_files = list(shim_dir.rglob("*.py"))
    assert py_files == [shim_dir / "__init__.py"], (
        f"{shim_dir.name}: shim dir must contain exactly __init__.py, found {py_files}"
    )


@pytest.mark.parametrize("shim_dir", SHIM_DIRS, ids=lambda p: p.name)
def test_shim_source_contract(shim_dir: Path) -> None:
    """Contracts #1, #3, #4 at the source level, for every real shim.

    The alias target must be ``lfx_bundles.<provider>`` (metapackage) or
    ``lfx_<provider>.components.<provider>`` (graduated partner), the
    name-check must guard the matching top-level package, and the install
    message must name the matching distribution.
    """
    provider = shim_dir.name
    # Bundle names are lowercase (BUNDLE_NAME_RE), so a mixed-case in-tree dir
    # (e.g. FAISS, Notion) aliases to its lowercased bundle (faiss, notion).
    # A few dirs are cross-bundle shims: their lone component lives in a
    # differently-named bundle (e.g. vectorstores' LocalDBComponent is
    # Chroma-backed, so it aliases the ``chroma`` bundle).
    cross_bundle = {"vectorstores": "chroma"}
    slug = cross_bundle.get(provider, provider.lower())
    src = (shim_dir / "__init__.py").read_text(encoding="utf-8")

    assert src.startswith(SHIM_MARKER), f"{provider}: first line must be the {SHIM_MARKER!r} marker"
    assert "sys.modules[__name__] = importlib.import_module(" in src, f"{provider}: must module-alias"

    meta_target = f'importlib.import_module("lfx_bundles.{slug}")'
    partner_target = f'importlib.import_module("lfx_{slug}.components.{slug}")'
    is_meta = meta_target in src
    is_partner = partner_target in src
    assert is_meta or is_partner, f"{provider}: alias target is neither metapackage nor partner shape"

    if is_meta:
        assert 'exc.name == "lfx_bundles"' in src, f"{provider}: name-check must guard lfx_bundles"
        assert _METAPACKAGE_MSG in src, f"{provider}: locked install message missing ({_METAPACKAGE_MSG!r})"
    else:
        assert f'exc.name == "lfx_{slug}"' in src, f"{provider}: name-check must guard lfx_{slug}"
        assert f"{_PARTNER_MSG_PREFIX}{slug}" in src, (
            f"{provider}: locked install message missing ('pip install lfx-{slug}')"
        )
    # Contract #5: anything other than the bundle-missing case re-raises.
    assert src.rstrip().endswith("raise"), f"{provider}: must re-raise non-bundle import errors untouched"


# ---------------------------------------------------------------------------
# lfx.base shims (shared-base trees moved with their bundle, e.g. datastax)
# ---------------------------------------------------------------------------

BASE_PKG_DIR = COMPONENTS_DIR.parent / "base"


def _base_shim_dirs() -> list[Path]:
    """Every dir under lfx/base whose __init__ carries the shim marker."""
    found = []
    for child in sorted(BASE_PKG_DIR.iterdir()):
        init_py = child / "__init__.py"
        if child.is_dir() and init_py.is_file():
            try:
                head = init_py.read_text(encoding="utf-8").lstrip()
            except OSError:
                continue
            if head.startswith(SHIM_MARKER):
                found.append(child)
    return found


BASE_SHIM_DIRS = _base_shim_dirs()


def test_base_shims_exist() -> None:
    """The datastax graduation moved lfx.base.datastax; its shim must exist.

    Stored flow code fields (starter projects, saved user flows) embed
    ``from lfx.base.datastax... import ...`` and are re-executed verbatim
    at build time, so moved base trees need shims exactly like moved
    component trees do.
    """
    assert BASE_SHIM_DIRS, f"no marker shims found under {BASE_PKG_DIR}"


@pytest.mark.parametrize("shim_dir", BASE_SHIM_DIRS, ids=lambda p: p.name)
def test_base_shim_is_one_file_stub(shim_dir: Path) -> None:
    py_files = list(shim_dir.rglob("*.py"))
    assert py_files == [shim_dir / "__init__.py"], (
        f"{shim_dir.name}: base shim dir must contain exactly __init__.py, found {py_files}"
    )


@pytest.mark.parametrize("shim_dir", BASE_SHIM_DIRS, ids=lambda p: p.name)
def test_base_shim_source_contract(shim_dir: Path) -> None:
    """Base shims alias to the bundle's base subpackage with the same guards."""
    provider = shim_dir.name
    src = (shim_dir / "__init__.py").read_text(encoding="utf-8")

    assert src.startswith(SHIM_MARKER), f"{provider}: first line must be the {SHIM_MARKER!r} marker"
    assert "sys.modules[__name__] = importlib.import_module(" in src, f"{provider}: must module-alias"

    meta_target = f'importlib.import_module("lfx_bundles.{provider}.base")'
    partner_target = f'importlib.import_module("lfx_{provider}.base")'
    is_meta = meta_target in src
    is_partner = partner_target in src
    assert is_meta or is_partner, f"{provider}: alias target is neither metapackage nor partner base shape"

    if is_meta:
        assert 'exc.name == "lfx_bundles"' in src, f"{provider}: name-check must guard lfx_bundles"
        assert _METAPACKAGE_MSG in src, f"{provider}: locked install message missing ({_METAPACKAGE_MSG!r})"
    else:
        assert f'exc.name == "lfx_{provider}"' in src, f"{provider}: name-check must guard lfx_{provider}"
        assert f"{_PARTNER_MSG_PREFIX}{provider}" in src, (
            f"{provider}: locked install message missing ('pip install lfx-{provider}')"
        )
    assert src.rstrip().endswith("raise"), f"{provider}: must re-raise non-bundle import errors untouched"


def test_walk_skip_detects_every_shim() -> None:
    """The in-tree walk's shim detector and the marker sweep agree exactly."""
    from lfx.interface.components import _discover_shimmed_component_dirs

    detected = _discover_shimmed_component_dirs([str(COMPONENTS_DIR)])
    assert detected == {d.name for d in SHIM_DIRS}


# ---------------------------------------------------------------------------
# Mechanism tests against a synthetic shim (hermetic)
# ---------------------------------------------------------------------------

_SYNTHETIC_SHIM = '''# lfx-bundles-shim
"""Synthetic shim used by the contract tests."""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("fake_lfx_target.alpha")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "fake_lfx_target" or exc.name.startswith("fake_lfx_target.")):
        msg = (
            "The 'alpha' components moved to the 'fake-lfx-target' distribution. "
            "Install it with:  pip install fake-lfx-target"
        )
        raise ModuleNotFoundError(msg, name="fake_lfx_target") from exc
    raise
'''


def _import_file_as(name: str, path: Path):
    """Import ``path`` under module name ``name`` (and clean up afterwards)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    # Module aliasing replaces the sys.modules entry; return what's installed.
    return sys.modules[name]


@pytest.fixture
def synthetic_shim(tmp_path: Path):
    """A synthetic shim file + cleanup of every module this test family installs."""
    shim_file = tmp_path / "shim" / "__init__.py"
    shim_file.parent.mkdir()
    shim_file.write_text(_SYNTHETIC_SHIM, encoding="utf-8")
    yield shim_file
    for mod in [m for m in sys.modules if m.startswith(("fake_lfx_target", "synthetic_shim_"))]:
        sys.modules.pop(mod, None)


def test_alias_resolves_when_target_installed(synthetic_shim: Path, tmp_path: Path, monkeypatch) -> None:
    """Contract #3: with the bundle present, the shim IS the target module."""
    target = tmp_path / "fake_lfx_target" / "alpha"
    target.mkdir(parents=True)
    (tmp_path / "fake_lfx_target" / "__init__.py").write_text("", encoding="utf-8")
    (target / "__init__.py").write_text("class AlphaComponent:\n    pass\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    module = _import_file_as("synthetic_shim_present", synthetic_shim)
    assert module.__name__ == "fake_lfx_target.alpha"  # aliased, not the shim itself
    assert module.AlphaComponent.__name__ == "AlphaComponent"


def test_locked_message_when_bundle_missing(synthetic_shim: Path) -> None:
    """Contract #4: bundle absent -> actionable ModuleNotFoundError, locked wording."""
    with pytest.raises(ModuleNotFoundError) as excinfo:
        _import_file_as("synthetic_shim_missing", synthetic_shim)
    assert excinfo.value.name == "fake_lfx_target"
    assert "pip install fake-lfx-target" in str(excinfo.value)
    # The original import failure is chained for debugging.
    assert isinstance(excinfo.value.__cause__, ModuleNotFoundError)


def test_transitive_dep_error_reraised_untouched(synthetic_shim: Path, tmp_path: Path, monkeypatch) -> None:
    """Contract #5: bundle present but its SDK missing -> the REAL error surfaces."""
    target = tmp_path / "fake_lfx_target" / "alpha"
    target.mkdir(parents=True)
    (tmp_path / "fake_lfx_target" / "__init__.py").write_text("", encoding="utf-8")
    (target / "__init__.py").write_text("import some_missing_sdk\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    with pytest.raises(ModuleNotFoundError) as excinfo:
        _import_file_as("synthetic_shim_transitive", synthetic_shim)
    assert excinfo.value.name == "some_missing_sdk"  # NOT rewritten to the install message
    assert "pip install fake-lfx-target" not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Adaptive live test against a real shim (exercises whichever env we're in)
# ---------------------------------------------------------------------------


def test_real_metapackage_shim_live() -> None:
    """In a bundle-installed env the alias works; bare-engine gets the locked message."""
    bundle_installed = importlib.util.find_spec("lfx_bundles") is not None
    if bundle_installed:
        module = importlib.import_module("lfx.components.tavily")
        assert module.__name__ == "lfx_bundles.tavily"
        assert hasattr(module, "TavilySearchComponent")
    else:
        with pytest.raises(ModuleNotFoundError, match="pip install lfx-bundles"):
            importlib.import_module("lfx.components.tavily")
        sys.modules.pop("lfx.components.tavily", None)
