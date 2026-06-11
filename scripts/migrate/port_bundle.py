#!/usr/bin/env python3
"""Mechanical port helper for ``src/lfx/src/lfx/components/<provider>/`` -> ``src/bundles/<provider>/``.

Writes the bundle skeleton documented in ``src/bundles/PORTING.md``,
deletes the in-tree provider directory, and patches the three known
cross-cutting touchpoints (workspace ``pyproject.toml``,
``src/lfx/src/lfx/components/__init__.py``).

What this script does:
    1. Validates the candidate (provider directory exists, no ``from
       langflow`` imports, no ``deactivated`` duplicate).
    2. Lays out ``src/bundles/<bundle>/{pyproject.toml,README.md,
       src/lfx_<bundle>/{__init__.py,extension.json,components/<bundle>/{__init__.py}}}``.
    3. Moves every ``*.py`` file from the in-tree provider directory into
       the bundle's ``components/<bundle>/`` directory, byte-for-byte.
    4. Removes the in-tree directory.
    5. Strips the three references in
       ``src/lfx/src/lfx/components/__init__.py``.
    6. Adds the dep, the workspace source, and the workspace member entry
       to the root ``pyproject.toml`` (uses the
       ``# langflow-extensions:bundle-{deps,sources,members}-end`` marker
       pairs so the anchors survive dep reordering / pin bumps).

What this script does NOT do (humans-only):
    * Run ``uv lock``, ``LFX_DEV=1 scripts/build_component_index.py``,
      ``ruff``, or any other verification step.  See ``src/bundles/PORTING.md``
      § 7 for the manual block.

What this script does on a best-effort basis (review before commit):
    * Discovers ``class <Name>(...)`` declarations in each moved file and
      wires the corresponding re-exports into both ``__init__.py`` files.
    * Renders migration-table JSON entries and an integration-test scaffold
      to stdout when ``--migration-release`` is given, so the human edits
      become "paste-in" rather than "hand-write".

Run mode:
    Default is dry-run (prints the planned changes).  Pass ``--apply`` to
    actually mutate the tree; the diff should be reviewed in ``git diff``
    before committing.

Surface deliberately tiny: every step is one of {mkdir, write_text,
shutil.move, regex substitute}.  The script intentionally does NOT depend
on lfx, hatchling, tomllib-as-writer, or any other heavyweight piece;
stdlib only.  This is the same constraint
``scripts/migrate/check_bare_names.py`` runs under so the script can run
in any CI checkout.

Usage:
    python scripts/migrate/port_bundle.py --bundle arxiv               # dry-run
    python scripts/migrate/port_bundle.py --bundle arxiv --apply       # write
    python scripts/migrate/port_bundle.py --bundle arxiv \
        --display-name "arXiv Search" \
        --migration-release 1.10.0 --apply
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _current_lfx_floor() -> str:
    """Return the ``lfx`` dependency floor for a freshly-ported bundle.

    Reads the workspace lfx version from ``src/lfx/pyproject.toml`` and pins
    ``lfx>=X.Y.0.dev0,<(X+1).0.0`` -- floored at the current major.minor
    line's first pre-release (the branch's own canonical ``X.Y.0.devN``
    nightlies sort below a plain ``X.Y.0`` under PEP 440, so they must be
    admitted by the floor), capped below the next lfx major.  Mirrors
    ``lfx_floor_spec`` in ``scripts/ci/sync_bundle_lfx_pin.py`` (each script
    is kept standalone, so keep the two in step); that script re-syncs every
    existing bundle on ``make patch``.
    """
    lfx_pyproject = (REPO_ROOT / "src" / "lfx" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "(\d+)\.(\d+)\.\d+', lfx_pyproject, re.MULTILINE)
    if not match:
        msg = "Could not read lfx version from src/lfx/pyproject.toml"
        raise ValueError(msg)
    major, minor = int(match.group(1)), int(match.group(2))
    return f"lfx>={major}.{minor}.0.dev0,<{major + 1}.0.0"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


PYPROJECT_TEMPLATE = """\
[project]
name = "lfx-{bundle}"
version = "0.1.0"
description = "{display_name} component(s) as a standalone Langflow Extension Bundle."
readme = "README.md"
requires-python = ">=3.10,<3.15"
license = {{ text = "MIT" }}
authors = [
    {{ name = "Langflow", email = "contact@langflow.org" }},
]
keywords = ["langflow", "lfx", "extension", "bundle", "{bundle}"]

# Runtime deps: lfx (the BUNDLE_API surface) plus any third-party imports
# the bundle's components rely on.  REVIEW THIS LIST -- the script ports
# only ``lfx``; add any other deps the moved component(s) import.
# lfx is floored at the current major.minor line and capped below the next
# lfx major (e.g. "lfx>=1.10.0,<2.0.0"); the floor is read from
# src/lfx/pyproject.toml at port time and re-synced on ``make patch`` via
# scripts/ci/sync_bundle_lfx_pin.py.  Fine-grained BUNDLE_API compatibility
# is enforced via extension.json's lfx.compat list against BUNDLE_API_VERSION.
dependencies = [
    "{lfx_floor}",
]

[project.urls]
Homepage = "https://github.com/langflow-ai/langflow"
Documentation = "https://docs.langflow.org/extensions"
Repository = "https://github.com/langflow-ai/langflow"

# Manifest-shipping distributions are discovered via the
# ``langflow.extensions`` entry-point.  Editable installs whose
# ``dist.files`` only surfaces dist-info entries fall back to this
# entry-point to find the manifest.
[project.entry-points."langflow.extensions"]
lfx-{bundle} = "lfx_{bundle}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
# extension.json + components live inside the lfx_{bundle} package so
# ``importlib.metadata.files(dist)`` finds them and the loader resolves
# bundles[].path relative to the manifest's directory.
packages = ["src/lfx_{bundle}"]
include = ["src/lfx_{bundle}/extension.json", "src/lfx_{bundle}/components/**/*.py"]

[tool.hatch.build.targets.sdist]
include = [
    "src/lfx_{bundle}",
    "extension.json",
    "README.md",
    "pyproject.toml",
]
"""


EXTENSION_JSON_TEMPLATE = """\
{{
  "$schema": "https://schemas.langflow.org/extension/v1.json",
  "id": "lfx-{bundle}",
  "version": "0.1.0",
  "name": "{display_name}",
  "description": "{display_name} component(s) as a standalone Langflow Extension Bundle.",
  "lfx": {{
    "compat": ["1"]
  }},
  "bundles": [
    {{
      "name": "{bundle}",
      "path": "components/{bundle}"
    }}
  ]
}}
"""


PACKAGE_INIT_TEMPLATE = '''\
"""lfx-{bundle}: {display_name} bundle.

Distribution unit ``lfx-{bundle}``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:{bundle}:<Class>@official``.
"""

{package_reexports}
'''


COMPONENTS_INIT_TEMPLATE = '''\
"""Component re-exports for the ``{bundle}`` bundle.

Saved-flow migration entries that target ``lfx.components.{bundle}.<Class>``
resolve through this package, so the moved Component class(es) must be
importable from here by name.
"""

{component_reexports}
'''


README_TEMPLATE = """\
# lfx-{bundle}

{display_name} component(s) as a standalone Langflow Extension Bundle.

## Install

```bash
pip install lfx-{bundle}
```

The bundle is registered automatically via the `langflow.extensions`
entry-point.  After install, restart your Langflow server; the bundle's
components will appear in the palette under the `{bundle}` group.

## Develop

```bash
cd src/bundles/{bundle}
pip install -e .
lfx extension validate src/lfx_{bundle}
```

## Migration

Saved flows referencing the legacy class name(s) or the old import paths
under `lfx.components.{bundle}.*` are rewritten to the new namespaced
IDs by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
"""


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentFile:
    """A ported .py file plus the Component class names it declares."""

    path: Path
    classes: tuple[str, ...]


@dataclass(frozen=True)
class PortPlan:
    bundle: str
    display_name: str
    in_tree_dir: Path
    bundle_dir: Path
    component_files: tuple[ComponentFile, ...]
    migration_release: str | None


_CLASS_DECL_RE = re.compile(r"^class\s+(\w+)\s*\(", re.MULTILINE)


def _discover_classes(source: str) -> tuple[str, ...]:
    """Return top-level ``class Name(...):`` names in ``source``.

    Indented classes (nested inside functions or other classes) are
    skipped -- only the top-level Component subclasses participate in the
    re-export wiring.
    """
    return tuple(_CLASS_DECL_RE.findall(source))


def _validate_candidate(bundle: str, *, display_name: str | None, migration_release: str | None) -> PortPlan:
    """Refuse early if the candidate is not eligible for the mechanical port."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", bundle):
        msg = (
            f"--bundle {bundle!r} is not a valid bundle name (lowercase "
            "snake_case, 2-64 chars, starts with a letter).  This script "
            "ports an in-tree provider folder named exactly the same."
        )
        raise SystemExit(msg)

    in_tree = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components" / bundle
    if not in_tree.is_dir():
        msg = f"In-tree provider directory not found: {in_tree}"
        raise SystemExit(msg)

    bundle_dir = REPO_ROOT / "src" / "bundles" / bundle
    if bundle_dir.exists():
        msg = f"Bundle directory already exists: {bundle_dir}.  Refusing to overwrite."
        raise SystemExit(msg)

    deactivated_dup = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components" / "deactivated" / bundle
    if deactivated_dup.is_dir():
        msg = (
            f"A deactivated duplicate exists at {deactivated_dup}.  Resolve "
            "the duplicate manually before porting -- see "
            "src/bundles/PORTING.md § 0."
        )
        raise SystemExit(msg)

    component_files: list[ComponentFile] = []
    for src in sorted(in_tree.iterdir()):
        if not src.is_file() or src.suffix != ".py":
            continue
        text = src.read_text(encoding="utf-8")
        if "from langflow" in text:
            msg = (
                f"{src} imports from ``langflow`` -- the bundle is installed "
                "against the public BUNDLE_API surface (lfx), not Langflow "
                "internals.  Either rewrite the import or leave the component "
                "in-tree.  See src/bundles/PORTING.md § 0."
            )
            raise SystemExit(msg)
        classes = () if src.name == "__init__.py" else _discover_classes(text)
        component_files.append(ComponentFile(path=src, classes=classes))

    if not component_files:
        msg = f"No ``*.py`` files under {in_tree}; nothing to port."
        raise SystemExit(msg)

    if migration_release is not None and not re.fullmatch(r"\d+\.\d+\.\d+", migration_release):
        msg = f"--migration-release {migration_release!r} must be a three-segment SemVer (e.g. 1.10.0)."
        raise SystemExit(msg)

    resolved_display = display_name if display_name is not None else bundle.replace("_", " ").title()
    return PortPlan(
        bundle=bundle,
        display_name=resolved_display,
        in_tree_dir=in_tree,
        bundle_dir=bundle_dir,
        component_files=tuple(component_files),
        migration_release=migration_release,
    )


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _render_reexports(plan: PortPlan) -> tuple[str, str]:
    """Render the two ``__init__.py`` re-export blocks from discovered classes.

    Returns ``(package_init_body, components_init_body)``.  If no Component
    classes were discovered, both bodies fall back to a TODO comment that
    instructs the porter to wire the re-exports by hand.
    """
    all_classes: list[tuple[str, str]] = []  # (module_stem, ClassName)
    for cf in plan.component_files:
        if cf.path.name == "__init__.py":
            continue
        module_stem = cf.path.stem
        all_classes.extend((module_stem, cls) for cls in cf.classes)

    if not all_classes:
        todo = (
            "# TODO(port_bundle): no top-level ``class <Name>(...):`` declarations were\n"
            "# discovered.  Add the Component class re-exports manually so saved-flow\n"
            "# migration entries that target ``lfx.components.<bundle>.<Class>`` resolve."
        )
        return todo, todo

    # Package-level: ``from lfx_<bundle>.components.<bundle>.<module> import <Class>``.
    package_lines = [
        f"from lfx_{plan.bundle}.components.{plan.bundle}.{module} import {cls}" for module, cls in all_classes
    ]
    package_all = ", ".join(repr(cls) for _, cls in all_classes)
    package_body = "\n".join(package_lines) + f"\n\n__all__ = [{package_all}]"

    # Component-package level: relative ``from .<module> import <Class>``.
    component_lines = [f"from .{module} import {cls}" for module, cls in all_classes]
    component_body = "\n".join(component_lines) + f"\n\n__all__ = [{package_all}]"

    return package_body, component_body


def _layout_bundle(plan: PortPlan, *, apply: bool) -> list[str]:
    """Create the bundle directory tree and write the static files."""
    actions: list[str] = []
    package_dir = plan.bundle_dir / "src" / f"lfx_{plan.bundle}"
    components_dir = package_dir / "components" / plan.bundle

    actions.append(f"mkdir -p {components_dir.relative_to(REPO_ROOT)}")
    if apply:
        components_dir.mkdir(parents=True, exist_ok=False)

    package_reexports, component_reexports = _render_reexports(plan)
    files = {
        plan.bundle_dir / "pyproject.toml": PYPROJECT_TEMPLATE.format(
            bundle=plan.bundle, display_name=plan.display_name, lfx_floor=_current_lfx_floor()
        ),
        plan.bundle_dir / "README.md": README_TEMPLATE.format(bundle=plan.bundle, display_name=plan.display_name),
        package_dir / "__init__.py": PACKAGE_INIT_TEMPLATE.format(
            bundle=plan.bundle,
            display_name=plan.display_name,
            package_reexports=package_reexports,
        ),
        package_dir / "extension.json": EXTENSION_JSON_TEMPLATE.format(
            bundle=plan.bundle, display_name=plan.display_name
        ),
        components_dir / "__init__.py": COMPONENTS_INIT_TEMPLATE.format(
            bundle=plan.bundle,
            component_reexports=component_reexports,
        ),
    }
    for path, content in files.items():
        actions.append(f"write {path.relative_to(REPO_ROOT)}")
        if apply:
            path.write_text(content, encoding="utf-8")

    for cf in plan.component_files:
        src = cf.path
        if src.name == "__init__.py":
            # The package-level __init__.py is rewritten as the placeholder
            # above; preserve its prior re-exports manually after porting.
            continue
        dst = components_dir / src.name
        actions.append(f"move {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
        if apply:
            shutil.move(str(src), str(dst))
    return actions


def _delete_in_tree(plan: PortPlan, *, apply: bool) -> list[str]:
    """Remove the legacy in-tree provider directory."""
    actions = [f"rm -r {plan.in_tree_dir.relative_to(REPO_ROOT)}"]
    if apply and plan.in_tree_dir.exists():
        shutil.rmtree(plan.in_tree_dir)
    return actions


def _patch_components_init(plan: PortPlan, *, apply: bool) -> list[str]:
    """Remove the three references to ``<bundle>`` in components/__init__.py."""
    target = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components" / "__init__.py"
    actions = [f"strip {plan.bundle!r} refs from {target.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    text = target.read_text(encoding="utf-8")
    patterns = (
        # Top import block (one ``    <bundle>,`` per line).
        rf"^ {{8}}{re.escape(plan.bundle)},\n",
        # _dynamic_imports table.
        rf'^ {{4}}"{re.escape(plan.bundle)}": "__module__",\n',
        # __all__ list.
        rf'^ {{4}}"{re.escape(plan.bundle)}",\n',
    )
    new_text = text
    for pattern in patterns:
        new_text = re.sub(pattern, "", new_text, count=1, flags=re.MULTILINE)
    if new_text == text:
        msg = (
            f"No occurrences of {plan.bundle!r} found in {target.relative_to(REPO_ROOT)}.  "
            "The script's regex pattern may be out of date with the file's "
            "current shape.  Edit by hand and re-run with --skip-init-patch."
        )
        raise SystemExit(msg)
    target.write_text(new_text, encoding="utf-8")
    return actions


def _insert_before_marker(text: str, end_marker: str, payload: str, *, what: str) -> str:
    """Insert ``payload`` immediately before the line containing ``end_marker``.

    ``end_marker`` is a literal substring expected on its own comment line
    (e.g. ``# langflow-extensions:bundle-deps-end``).  Raises SystemExit
    if the marker is absent so the porter notices that the maintenance-
    friendly anchors have drifted out of pyproject.toml.
    """
    needle = end_marker
    idx = text.find(needle)
    if idx == -1:
        msg = (
            f"Could not locate the {what} end marker ({needle!r}) in "
            "pyproject.toml.  Re-add the ``langflow-extensions:bundle-*`` "
            "marker pair before re-running -- see src/bundles/PORTING.md."
        )
        raise SystemExit(msg)
    # Rewind to the start of the line so the payload lands above the marker
    # with matching indentation.
    line_start = text.rfind("\n", 0, idx) + 1
    return text[:line_start] + payload + text[line_start:]


def _patch_root_pyproject(plan: PortPlan, *, apply: bool) -> list[str]:
    """Add the dep, the workspace source, and the workspace member entry."""
    target = REPO_ROOT / "pyproject.toml"
    actions = [f"patch {target.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    text = target.read_text(encoding="utf-8")
    bundle = plan.bundle

    if f"lfx-{bundle}" in text:
        msg = f"lfx-{bundle} already referenced in {target.relative_to(REPO_ROOT)}; not patching."
        raise SystemExit(msg)

    dep_line = f'    "lfx-{bundle}>=0.1.0",\n'
    source_line = f"lfx-{bundle} = {{ workspace = true }}\n"
    member_line = f'    "src/bundles/{bundle}",\n'

    new_text = _insert_before_marker(
        text,
        "# langflow-extensions:bundle-deps-end",
        dep_line,
        what="bundle-deps",
    )
    new_text = _insert_before_marker(
        new_text,
        "# langflow-extensions:bundle-sources-end",
        source_line,
        what="bundle-sources",
    )
    new_text = _insert_before_marker(
        new_text,
        "# langflow-extensions:bundle-members-end",
        member_line,
        what="bundle-members",
    )

    target.write_text(new_text, encoding="utf-8")
    return actions


# ---------------------------------------------------------------------------
# Paste-in scaffolds
# ---------------------------------------------------------------------------


def _render_migration_entries(plan: PortPlan) -> str:
    """Render JSON migration entries for paste-in to ``migration_table.json``.

    Emits four entries per discovered class, matching the keys
    ``lfx.extension.migration.loader`` reads:
        * ``bare_class_name`` -- the bare class name a saved flow may have used.
        * ``import_path`` -- ``lfx.components.<bundle>.<module>.<Class>``.
        * ``import_path`` -- ``lfx.components.<bundle>.<Class>`` (package re-export).
        * ``legacy_slot`` -- ``ext:<bundle>:<Class>@official-pre-a`` (the
          pre-Phase-A canonical slot, in case any in-flight saved flow
          serialized that form before this bundle landed).

    Bare-name uniqueness is enforced by ``scripts/migrate/check_bare_names.py``
    in CI, so the porter just pastes the block and lets CI catch collisions.
    """
    release = plan.migration_release or "X.Y.Z"
    entries: list[str] = []
    for cf in plan.component_files:
        if cf.path.name == "__init__.py":
            continue
        module_stem = cf.path.stem
        for cls in cf.classes:
            target = f"ext:{plan.bundle}:{cls}@official"
            entries.append(
                "    {\n"
                f'      "bare_class_name": "{cls}",\n'
                f'      "target": "{target}",\n'
                f'      "added_in": "{release}"\n'
                "    },\n"
                "    {\n"
                f'      "import_path": "lfx.components.{plan.bundle}.{module_stem}.{cls}",\n'
                f'      "target": "{target}",\n'
                f'      "added_in": "{release}"\n'
                "    },\n"
                "    {\n"
                f'      "import_path": "lfx.components.{plan.bundle}.{cls}",\n'
                f'      "target": "{target}",\n'
                f'      "added_in": "{release}"\n'
                "    },\n"
                "    {\n"
                f'      "legacy_slot": "ext:{plan.bundle}:{cls}@official-pre-a",\n'
                f'      "target": "{target}",\n'
                f'      "added_in": "{release}"\n'
                "    }"
            )
    return ",\n".join(entries)


def _render_test_scaffold(plan: PortPlan) -> str:
    """Render an integration-test scaffold for ``test_pilot_<bundle>_upgrade.py``.

    Structurally mirrors ``test_pilot_duckduckgo_upgrade.py``: a
    ``migration_table`` fixture, three saved-flow rewrite tests (bare,
    full import path, short import path), the bundle-importable check,
    and the manifest-shipped check.  The porter still owns the
    component-specific runtime assertions (build pipeline, output schema)
    -- those are too domain-specific to template.
    """
    bundle = plan.bundle
    first_class = next(
        (cls for cf in plan.component_files for cls in cf.classes if cf.path.name != "__init__.py"),
        f"{bundle.title()}Component",
    )
    target = f"ext:{bundle}:{first_class}@official"
    module_stem = next(
        (cf.path.stem for cf in plan.component_files if cf.classes),
        bundle,
    )
    full_path = f"lfx.components.{bundle}.{module_stem}.{first_class}"
    short_path = f"lfx.components.{bundle}.{first_class}"
    return f'''"""Integration test: legacy {bundle} flows upgrade cleanly.

Mirrors ``test_pilot_duckduckgo_upgrade.py`` for ``{first_class}``.
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"
EXPECTED_TARGET = "{target}"


@pytest.fixture(scope="module")
def migration_table():
    table, error = load_migration_table(TABLE_PATH)
    assert error is None, f"failed to load migration table: {{error}}"
    assert table is not None
    return table


def _saved_flow_node(node_id: str, type_value: str) -> dict:
    """Build a minimal saved-flow node skeleton for testing."""
    return {{
        "id": node_id,
        "type": "genericNode",
        "data": {{"id": node_id, "type": type_value, "node": {{"template": {{}}}}}},
    }}


def _saved_flow(*nodes: dict) -> dict:
    return {{"data": {{"nodes": list(nodes), "edges": []}}}}


@pytest.mark.integration
def test_legacy_bare_name_flow_upgrades(migration_table) -> None:
    """Pre-Phase-A flow with the bare class name upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("{bundle}-1", "{first_class}"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    [record] = report.records
    assert record.legacy_form_kind == "bare_class_name"
    assert record.new_value == EXPECTED_TARGET


@pytest.mark.integration
def test_legacy_import_path_flow_upgrades(migration_table) -> None:
    """Dotted import-path form upgrades to the canonical ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("{bundle}-2", "{full_path}"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
def test_short_import_path_flow_upgrades(migration_table) -> None:
    """Package-level import-path form (via ``__init__.py`` re-export) upgrades."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    flow = _saved_flow(_saved_flow_node("{bundle}-3", "{short_path}"))
    report = migrate_flow_payload(flow, table=migration_table)

    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == EXPECTED_TARGET


@pytest.mark.integration
def test_lfx_{bundle}_distribution_is_importable() -> None:
    """The bundle's package is importable in the development workspace."""
    try:
        from lfx_{bundle} import {first_class}
    except ImportError:
        pytest.skip("lfx-{bundle} not installed in this test environment")

    assert {first_class}.__name__ == "{first_class}"


def _is_editable_install(dist: importlib_metadata.Distribution) -> bool:
    direct_url = dist.read_text("direct_url.json")
    if not direct_url:
        return False
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return False
    return bool(payload.get("dir_info", {{}}).get("editable"))


@pytest.mark.integration
def test_lfx_{bundle}_ships_manifest() -> None:
    """``importlib.metadata`` can find ``extension.json`` for the installed dist."""
    try:
        dist = importlib_metadata.distribution("lfx-{bundle}")
    except importlib_metadata.PackageNotFoundError:
        pytest.skip("lfx-{bundle} not installed in this test environment")

    if _is_editable_install(dist):
        import lfx_{bundle}

        package_dir = Path(lfx_{bundle}.__file__).parent
        manifest_path = package_dir / "extension.json"
        assert manifest_path.is_file()
    else:
        files = dist.files or []
        manifests = [f for f in files if f.parts and f.parts[-1] == "extension.json"]
        assert manifests
        manifest_path = Path(dist.locate_file(manifests[0]))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "lfx-{bundle}"
    assert manifest["lfx"]["compat"] == ["1"]
    assert any(b["name"] == "{bundle}" for b in manifest["bundles"])
'''


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Port an in-tree provider directory into a standalone Langflow "
            "Extension Bundle.  Writes the skeleton, moves the source files, "
            "and patches the workspace; integration test and migration "
            "table edits are left to the human (see src/bundles/PORTING.md)."
        )
    )
    parser.add_argument(
        "--bundle",
        required=True,
        help="Snake-case provider name (matches src/lfx/src/lfx/components/<bundle>/).",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help=(
            "Human-readable name used in extension.json and README.md "
            "(e.g. ``arXiv Search``).  Defaults to ``<bundle>.replace('_', ' ').title()``, "
            "which is wrong for most providers -- pass this for any bundle "
            "whose canonical casing isn't auto-titlecase."
        ),
    )
    parser.add_argument(
        "--migration-release",
        default=None,
        help=(
            "SemVer release that introduces the bundle (e.g. ``1.10.0``).  "
            "When given, the script prints paste-in JSON migration entries "
            "and an integration-test scaffold alongside the action log."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually mutate the tree.  Default: dry-run (print actions only).",
    )
    args = parser.parse_args()

    plan = _validate_candidate(
        args.bundle,
        display_name=args.display_name,
        migration_release=args.migration_release,
    )

    actions: list[str] = []
    actions += _layout_bundle(plan, apply=args.apply)
    actions += _delete_in_tree(plan, apply=args.apply)
    actions += _patch_components_init(plan, apply=args.apply)
    actions += _patch_root_pyproject(plan, apply=args.apply)

    mode = "apply" if args.apply else "dry-run"
    print(f"port_bundle ({mode}) for bundle {plan.bundle!r}:")
    for action in actions:
        print(f"  {action}")

    if args.apply:
        b = plan.bundle
        print()
        print("Done.  Manual follow-ups (see src/bundles/PORTING.md § 4-7):")
        if plan.migration_release is None:
            print("  * Append migration entries (bare/import_path/legacy_slot) to migration_table.json.")
            print(f"  * Add tests/integration/extension/test_pilot_{b}_upgrade.py.")
            print("    Re-run with ``--migration-release X.Y.Z`` to print paste-in scaffolds for both.")
        print("  * Run uv lock + LFX_DEV=1 scripts/build_component_index.py + ruff + tests.")
    else:
        print()
        print("Dry-run.  Re-invoke with --apply to mutate the tree.")

    if plan.migration_release is not None:
        print()
        print("---- paste into src/lfx/src/lfx/extension/migration/migration_table.json ----")
        print(_render_migration_entries(plan))
        print(f"---- paste into src/lfx/tests/integration/extension/test_pilot_{plan.bundle}_upgrade.py ----")
        print(_render_test_scaffold(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
