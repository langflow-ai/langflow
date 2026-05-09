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
       to the root ``pyproject.toml``.

What this script does NOT do (humans-only):
    * Edit the migration table (release version + bare-name uniqueness
      check require human judgement).
    * Write the integration test
      (``src/lfx/tests/integration/extension/test_pilot_<bundle>_upgrade.py``).
    * Run ``uv lock``, ``LFX_DEV=1 scripts/build_component_index.py``,
      ``ruff``, or any other verification step.  See ``src/bundles/PORTING.md``
      § 7 for the manual block.

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
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


PYPROJECT_TEMPLATE = """\
[project]
name = "lfx-{bundle}"
version = "0.1.0"
description = "{display_name} component(s) as a standalone Langflow Extension Bundle."
readme = "README.md"
requires-python = ">=3.10,<3.14"
license = {{ text = "MIT" }}
authors = [
    {{ name = "Langflow", email = "contact@langflow.org" }},
]
keywords = ["langflow", "lfx", "extension", "bundle", "{bundle}"]

# Runtime deps: lfx (the BUNDLE_API surface) plus any third-party imports
# the bundle's components rely on.  REVIEW THIS LIST -- the script ports
# only ``lfx``; add any other deps the moved component(s) import.
dependencies = [
    "lfx>=0.5.0,<0.6.0",
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
registers the bundle's components under the namespaced ID
``ext:{bundle}:<Class>@official``.
"""
'''


COMPONENTS_INIT_PLACEHOLDER = """\
# Re-export the moved Component class(es) here so saved-flow migration
# entries that target ``lfx.components.<bundle>.<Class>`` keep working.
"""


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
class PortPlan:
    bundle: str
    display_name: str
    in_tree_dir: Path
    bundle_dir: Path
    component_files: tuple[Path, ...]


def _validate_candidate(bundle: str) -> PortPlan:
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

    component_files: list[Path] = []
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
        component_files.append(src)

    if not component_files:
        msg = f"No ``*.py`` files under {in_tree}; nothing to port."
        raise SystemExit(msg)

    display_name = bundle.replace("_", " ").title()
    return PortPlan(
        bundle=bundle,
        display_name=display_name,
        in_tree_dir=in_tree,
        bundle_dir=bundle_dir,
        component_files=tuple(component_files),
    )


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _layout_bundle(plan: PortPlan, *, apply: bool) -> list[str]:
    """Create the bundle directory tree and write the static files."""
    actions: list[str] = []
    package_dir = plan.bundle_dir / "src" / f"lfx_{plan.bundle}"
    components_dir = package_dir / "components" / plan.bundle

    actions.append(f"mkdir -p {components_dir.relative_to(REPO_ROOT)}")
    if apply:
        components_dir.mkdir(parents=True, exist_ok=False)

    files = {
        plan.bundle_dir / "pyproject.toml": PYPROJECT_TEMPLATE.format(
            bundle=plan.bundle, display_name=plan.display_name
        ),
        plan.bundle_dir / "README.md": README_TEMPLATE.format(bundle=plan.bundle, display_name=plan.display_name),
        package_dir / "__init__.py": PACKAGE_INIT_TEMPLATE.format(bundle=plan.bundle, display_name=plan.display_name),
        package_dir / "extension.json": EXTENSION_JSON_TEMPLATE.format(
            bundle=plan.bundle, display_name=plan.display_name
        ),
        components_dir / "__init__.py": COMPONENTS_INIT_PLACEHOLDER,
    }
    for path, content in files.items():
        actions.append(f"write {path.relative_to(REPO_ROOT)}")
        if apply:
            path.write_text(content, encoding="utf-8")

    for src in plan.component_files:
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

    # 1. Append the dep line at the end of the [project] dependencies list.
    dep_marker = '"lfx-duckduckgo>=0.1.0",\n'
    dep_replacement = dep_marker + f'    "lfx-{bundle}>=0.1.0",  # second-pilot port -- see src/bundles/PORTING.md\n'
    new_text, count = re.subn(re.escape(dep_marker), dep_replacement, text, count=1)
    if count == 0:
        msg = "Could not locate the duckduckgo dep line in pyproject.toml."
        raise SystemExit(msg)

    # 2. tool.uv.sources entry.
    src_marker = "lfx-duckduckgo = { workspace = true }\n"
    src_replacement = src_marker + f"lfx-{bundle} = {{ workspace = true }}\n"
    new_text, count = re.subn(re.escape(src_marker), src_replacement, new_text, count=1)
    if count == 0:
        msg = "Could not locate the duckduckgo workspace-source entry in pyproject.toml."
        raise SystemExit(msg)

    # 3. tool.uv.workspace members list.
    members_marker = '    "src/bundles/duckduckgo",\n'
    members_replacement = members_marker + f'    "src/bundles/{bundle}",\n'
    new_text, count = re.subn(re.escape(members_marker), members_replacement, new_text, count=1)
    if count == 0:
        msg = "Could not locate the duckduckgo workspace-member entry in pyproject.toml."
        raise SystemExit(msg)

    target.write_text(new_text, encoding="utf-8")
    return actions


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
        "--apply",
        action="store_true",
        help="Actually mutate the tree.  Default: dry-run (print actions only).",
    )
    args = parser.parse_args()

    plan = _validate_candidate(args.bundle)

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
        print("Done.  Manual follow-ups required (see src/bundles/PORTING.md § 4-7):")
        print(f"  * Edit src/bundles/{b}/src/lfx_{b}/__init__.py to re-export the moved class(es).")
        print(f"  * Edit src/bundles/{b}/src/lfx_{b}/components/{b}/__init__.py to re-export the class(es).")
        print("  * Append migration entries (bare/import_path/legacy_slot) to migration_table.json.")
        print(f"  * Add tests/integration/extension/test_pilot_{b}_upgrade.py.")
        print("  * Run uv lock + LFX_DEV=1 scripts/build_component_index.py + ruff + tests.")
    else:
        print()
        print("Dry-run.  Re-invoke with --apply to mutate the tree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
