"""Migration-table completeness guard for the lfx-bundles long tail.

Saved flows match components **by class name**.  When a provider moved into
``src/bundles/lfx-bundles/src/lfx_bundles/<provider>/`` its component classes
must be reachable through the canonical ``migration_table.json`` as an
``ext:<provider>:<Class>@<slot>`` target, or a flow that referenced the old
location silently fails to upgrade.

This test locks that invariant: for every provider folder under
``lfx_bundles`` it discovers the component class names *statically* (via
``ast`` -- many providers import optional SDKs at module top level and cannot
be imported in a bare test env) and asserts that each discovered class appears
as a migration target for that provider.  The table is complete today, so this
test passes; it exists so a future provider (or component class) moved into a
bundle **without** a corresponding table entry fails CI instead of shipping a
flow that cannot be upgraded.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from lfx.extension.migration.loader import MIGRATION_TABLE_PATH, load_migration_table

# ---------------------------------------------------------------------------
# Repo / bundle discovery
# ---------------------------------------------------------------------------

# .../src/lfx/tests/unit/extension/migration/<thisfile> -> repo root is 6 up.
_REPO_ROOT: Path = Path(__file__).resolve().parents[6]
_LFX_BUNDLES_ROOT: Path = _REPO_ROOT / "src" / "bundles" / "lfx-bundles" / "src" / "lfx_bundles"

# Matches the bundle + class segments of a canonical ``ext:<bundle>:<Class>@<slot>``
# target.  Kept local to the test so a schema-regex change can't silently widen
# what counts as "covered".
_TARGET_RE: re.Pattern[str] = re.compile(r"^ext:(?P<bundle>[a-z][a-z0-9_]*):(?P<klass>[A-Za-z_][A-Za-z0-9_]*)@")


def _discover_providers() -> list[str]:
    """Provider folders under ``lfx_bundles`` (each a package with ``__init__.py``)."""
    if not _LFX_BUNDLES_ROOT.is_dir():
        return []
    return sorted(
        entry.name
        for entry in _LFX_BUNDLES_ROOT.iterdir()
        if entry.is_dir() and entry.name != "__pycache__" and (entry / "__init__.py").exists()
    )


def _base_name(base: ast.expr) -> str | None:
    """Return the trailing identifier of a class base (``Foo`` or ``mod.Foo``)."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _discover_component_classes(provider_dir: Path) -> set[str]:
    """Statically collect component class names defined under ``provider_dir``.

    A "component" is any class whose base list contains an identifier ending in
    ``Component`` (e.g. ``class Foo(Component)`` or ``class Foo(LCToolComponent)``).
    We parse with ``ast`` rather than importing because many providers import
    optional third-party SDKs at module import time and would blow up here.
    Over-inclusion is fine: the table check below is what fails if a class is
    genuinely unmapped.
    """
    names: set[str] = set()
    for py_file in sorted(provider_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if any((name := _base_name(base)) is not None and name.endswith("Component") for base in node.bases):
                names.add(node.name)
    return names


_PROVIDERS: list[str] = _discover_providers()


@pytest.fixture(scope="module")
def migration_targets() -> dict[str, set[str]]:
    """Map ``bundle name -> {class names}`` from the canonical migration table."""
    table, error = load_migration_table(MIGRATION_TABLE_PATH, use_cache=False)
    assert error is None, f"migration table failed to load: {error}"
    assert table is not None
    targets: dict[str, set[str]] = {}
    for entry in table.entries:
        match = _TARGET_RE.match(entry.target)
        if match is not None:
            targets.setdefault(match.group("bundle"), set()).add(match.group("klass"))
    return targets


@pytest.mark.unit
def test_lfx_bundles_root_discovers_providers() -> None:
    """Guard the guard: discovery must actually find providers.

    If discovery silently finds nothing the parametrized test below would
    vacuously pass, so assert we enumerated at least one provider.
    """
    assert _LFX_BUNDLES_ROOT.is_dir(), f"lfx_bundles root not found at {_LFX_BUNDLES_ROOT}"
    assert _PROVIDERS, "no lfx_bundles providers discovered -- discovery logic is broken"


@pytest.mark.unit
@pytest.mark.parametrize("provider", _PROVIDERS)
def test_provider_components_have_migration_targets(provider: str, migration_targets: dict[str, set[str]]) -> None:
    """Every component class in a bundle must be an ``ext:<provider>:<Class>`` target.

    Saved flows resolve components by class name; an unmapped class means an old
    flow referencing it cannot be upgraded after the bundle move.
    """
    discovered = _discover_component_classes(_LFX_BUNDLES_ROOT / provider)
    assert discovered, (
        f"no component classes discovered under bundle {provider!r} -- "
        "either the bundle has no components (unexpected) or discovery is broken"
    )

    table_classes = migration_targets.get(provider, set())
    assert table_classes, (
        f"bundle {provider!r} has no ext:{provider}:...@ target in migration_table.json; "
        "saved flows using its components cannot be upgraded after the bundle move"
    )

    missing = discovered - table_classes
    assert not missing, (
        f"bundle {provider!r} component class(es) {sorted(missing)} are missing from "
        f"migration_table.json (no ext:{provider}:<Class>@ target); add a migration "
        "entry so saved flows referencing them upgrade correctly"
    )


@pytest.mark.unit
def test_funasr_import_paths_have_migration_targets() -> None:
    """Saved FunASR flows using either public import path must upgrade."""
    table, error = load_migration_table(MIGRATION_TABLE_PATH, use_cache=False)
    assert error is None, f"migration table failed to load: {error}"
    assert table is not None

    import_paths = {
        "lfx_bundles.funasr.funasr_transcription.FunASRTranscriptionComponent",
        "lfx_bundles.funasr.FunASRTranscriptionComponent",
    }
    target = "ext:funasr:FunASRTranscriptionComponent@official"
    observed = {entry.import_path: entry.target for entry in table.entries if entry.import_path in import_paths}
    assert observed == dict.fromkeys(import_paths, target)
