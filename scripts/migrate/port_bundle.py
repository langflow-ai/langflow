#!/usr/bin/env python3
r"""Mechanical port helper for ``src/lfx/src/lfx/components/<provider>/`` -> ``src/bundles/<provider>/``.

Writes the bundle skeleton documented in ``src/bundles/PORTING.md``,
moves the in-tree provider directory (and any shared base under
``lfx.base.<provider>``) into the bundle, patches every cross-cutting
touchpoint, and -- when given ``--migration-release`` -- writes the
migration table entries and integration-test scaffold directly.

What this script does
=====================

Phase A -- bundle layout (always):
    1. Validates the candidate (provider directory exists, no
       ``from langflow`` imports, no ``deactivated`` duplicate).
    2. Lays out ``src/bundles/<bundle>/{pyproject.toml,README.md,
       src/lfx_<bundle>/{__init__.py,extension.json,components/<bundle>/{__init__.py}}}``.
       The components ``__init__.py`` preserves the lazy-import shape
       (``_dynamic_imports`` dict + ``__getattr__`` + ``__dir__``) so
       saved flows that reference the package-level re-export keep
       resolving without an eager third-party import.
    3. Moves every ``*.py`` file from the in-tree provider directory
       into the bundle's ``components/<bundle>/`` directory.
    4. If a shared base exists at ``src/lfx/src/lfx/base/<bundle>/``,
       moves it into ``src/bundles/<bundle>/src/lfx_<bundle>/base/``
       and rewrites intra-bundle imports
       ``from lfx.base.<bundle>...`` -> ``from lfx_<bundle>.base...``.

Phase B -- in-tree cleanup:
    5. Removes the in-tree component directory.
    6. Strips the three references in
       ``src/lfx/src/lfx/components/__init__.py``.
    7. Moves the per-file ruff ignores under
       ``src/lfx/src/lfx/components/<bundle>/`` from the root
       ``pyproject.toml`` into the bundle's own ``pyproject.toml``
       (under ``[tool.ruff.lint.per-file-ignores]``).

Phase C -- workspace + external consumers:
    8. Adds the dep, the workspace source, and the workspace member
       entry to the root ``pyproject.toml`` (uses the
       ``# langflow-extensions:bundle-{deps,sources,members}-end``
       marker pairs so the anchors survive dep reordering / pin bumps).
    9. Rewrites every external consumer that imported
       ``lfx.components.<bundle>`` or ``lfx.base.<bundle>``:
       ``--rewrite-consumers`` greps the repo (excluding the bundle dir
       and the in-tree dir, both already moved) and applies the
       canonical substitutions ``lfx.components.<bundle>`` ->
       ``lfx_<bundle>.components.<bundle>``,
       ``lfx.components.<bundle>.<Class>`` (re-export form) ->
       ``lfx_<bundle>.<Class>``,
       ``lfx.base.<bundle>`` -> ``lfx_<bundle>.base``.
   10. Auto-discovers backend test directories at
       ``src/backend/tests/unit/base/<bundle>/`` and moves them into
       ``src/bundles/<bundle>/tests/`` with patch paths rewritten.

Phase D -- artefacts (when --migration-release is set):
   11. Appends the four-entry-per-class migration block directly to
       ``migration_table.json`` (was: paste-in stdout pre-1.0.).
   12. Writes ``test_pilot_<bundle>_upgrade.py`` directly to
       ``src/lfx/tests/integration/extension/``.
   13. Removes the bundle's category from
       ``src/lfx/src/lfx/_assets/component_index.json`` and
       recomputes the embedded SHA256 (requires ``uv run`` because
       the script depends on ``orjson`` -- the same library
       ``scripts/build_component_index.py`` uses).
   14. Patches the two non-uv-sync Dockerfiles
       (``docker/build_and_push_backend.Dockerfile`` and
       ``docker/build_and_push_base.Dockerfile``) to install the bundle.

Phase E -- optional cleanup (when --remove-base-extra is set):
   15. Removes ``<bundle> = [...]`` from
       ``src/backend/base/pyproject.toml`` extras and any
       ``langflow-base[<bundle>]`` reference from ``complete``.  Only
       safe when the bundle's runtime deps cover everything the extra
       used to install -- the porter MUST review the diff.

Run mode
========

    Dry-run by default (prints the planned actions, makes no changes).
    Pass ``--apply`` to mutate the tree; review with ``git diff`` before
    committing.

Usage
=====

::

    # Dry-run -- print the planned actions.
    python scripts/migrate/port_bundle.py --bundle arxiv

    # Full apply with migration release, consumer rewrites, ruff ignore
    # migration, and Dockerfile updates.
    python scripts/migrate/port_bundle.py \\
        --bundle datastax --display-name "DataStax / AstraDB" \\
        --migration-release 1.10.0 --apply --rewrite-consumers \\
        --update-index --update-dockerfiles --remove-base-extra
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LFX_COMPONENTS = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "components"
LFX_BASE = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "base"
BUNDLES_DIR = REPO_ROOT / "src" / "bundles"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
BASE_PYPROJECT = REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml"
COMPONENT_INDEX_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "_assets" / "component_index.json"
MIGRATION_TABLE = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"
BACKEND_BASE_TESTS = REPO_ROOT / "src" / "backend" / "tests" / "unit" / "base"
DOCKER_BACKEND = REPO_ROOT / "docker" / "build_and_push_backend.Dockerfile"
DOCKER_BASE = REPO_ROOT / "docker" / "build_and_push_base.Dockerfile"
PILOT_TEST_DIR = REPO_ROOT / "src" / "lfx" / "tests" / "integration" / "extension"


def _current_lfx_floor() -> str:
    """Return the ``lfx`` dependency floor for a freshly-ported bundle.

    Reads the workspace lfx version from ``src/lfx/pyproject.toml`` and pins
    ``lfx>=X.Y.0,<(X+1).0.0`` -- floored at the current major.minor line,
    capped below the next lfx major.  Mirrors ``lfx_floor_spec`` in
    ``scripts/ci/sync_bundle_lfx_pin.py`` (each script is kept standalone, so
    keep the two in step); that script re-syncs every existing bundle on
    ``make patch``.
    """
    lfx_pyproject = (REPO_ROOT / "src" / "lfx" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "(\d+)\.(\d+)\.\d+', lfx_pyproject, re.MULTILINE)
    if not match:
        msg = "Could not read lfx version from src/lfx/pyproject.toml"
        raise ValueError(msg)
    major, minor = int(match.group(1)), int(match.group(2))
    return f"lfx>={major}.{minor}.0,<{major + 1}.0.0"


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
include = [
    "src/lfx_{bundle}/extension.json",
{wheel_include_extra}    "src/lfx_{bundle}/components/**/*.py",
]

[tool.hatch.build.targets.sdist]
include = [
    "src/lfx_{bundle}",
    "extension.json",
    "README.md",
    "pyproject.toml",
]
{ruff_section}"""


RUFF_SECTION_TEMPLATE = """\

[tool.ruff.lint.per-file-ignores]
{ruff_entries}"""


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


# Preserves the lazy-import shape that ``lfx.components.<bundle>``
# pre-extraction used: a TYPE_CHECKING import block, a ``_dynamic_imports``
# dict mapping ``ClassName -> module_stem``, and a ``__getattr__`` /
# ``__dir__`` pair that resolves attributes on first access.  Saved flows
# that reference the package-level re-export
# (``lfx.components.<bundle>.<Class>``, migration-table-rewritten to
# ``lfx_<bundle>.components.<bundle>.<Class>``) keep resolving without
# eagerly importing every component module at package load.
COMPONENTS_INIT_TEMPLATE = '''\
"""Lazy component re-exports for the ``{bundle}`` bundle.

Mirrors the pre-extraction layout of ``lfx.components.{bundle}`` so saved
flows that referenced the module-level class
(e.g. ``lfx.components.{bundle}.<Class>``) keep resolving via the
migration table after rewrite to
``lfx_{bundle}.components.{bundle}.<Class>``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
{type_checking_imports}

_dynamic_imports = {dynamic_imports_dict}

__all__ = {all_list}


def __getattr__(attr_name: str) -> Any:
    if attr_name not in _dynamic_imports:
        msg = f"module {{__name__!r}} has no attribute {{attr_name!r}}"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import {{attr_name!r}} from {{__name__!r}}: {{e}}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
'''


BASE_INIT_TEMPLATE = '''\
"""Shared base infrastructure for the {bundle} bundle.

Houses the mixin(s) every component in this bundle inherits from --
pre-extraction this lived at ``lfx.base.{bundle}``.  Moved into the
bundle (not kept in lfx) because it is {bundle}-specific and only ever
imported by the {bundle} components.
"""

{base_reexports}
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
components will appear in the palette under the `{bundle}` group with
the namespaced IDs `ext:{bundle}:<Class>@official`.

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
class RuffIgnore:
    """One ``[tool.ruff.lint.per-file-ignores]`` entry to migrate."""

    pattern: str  # e.g. ``"src/lfx/src/lfx/components/datastax/astradb_vectorstore.py"``
    codes: tuple[str, ...]  # e.g. ``("S110",)``


@dataclass(frozen=True)
class ConsumerRewrite:
    """One file path plus the substring substitutions to apply.

    Order matters: more-specific substitutions first.  The script does
    plain ``str.replace`` so a substitution like
    ``lfx.components.<bundle>.<Class>`` -> ``lfx_<bundle>.<Class>`` must
    run before the catch-all ``lfx.components.<bundle>`` ->
    ``lfx_<bundle>.components.<bundle>``.
    """

    path: Path
    substitutions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PortPlan:
    bundle: str
    display_name: str
    in_tree_dir: Path
    bundle_dir: Path
    component_files: tuple[ComponentFile, ...]
    migration_release: str | None
    # Nested subdirectories under the in-tree provider directory
    # (e.g. ``agentics/helpers/``, ``agentics/inputs/``).  Moved
    # wholesale into the bundle's ``components/<bundle>/`` so any
    # imports from ``lfx.components.<bundle>.<subdir>.<module>``
    # continue to resolve via the migration-rewritten path
    # ``lfx_<bundle>.components.<bundle>.<subdir>.<module>``.
    nested_subdirs: tuple[Path, ...]
    # Auto-detected extras.
    shared_base_dir: Path | None
    backend_test_dirs: tuple[Path, ...]
    ruff_ignores: tuple[RuffIgnore, ...]
    consumer_rewrites: tuple[ConsumerRewrite, ...]
    base_extra_present: bool
    # The original ``__init__.py``'s ``_dynamic_imports`` dict (if any),
    # used to preserve the lazy-import shape during port.
    legacy_dynamic_imports: dict[str, str] = field(default_factory=dict)
    legacy_all: tuple[str, ...] = ()


# Capture both class name and base list so we can filter out classes
# that obviously aren't Langflow components (pydantic BaseModels,
# dataclasses, vendor SDK schemas, ABCs, etc.).
_CLASS_DECL_RE = re.compile(r"^class\s+(?P<name>\w+)\s*\((?P<bases>[^)]*)\)", re.MULTILINE)

# Bases (or any token in the bases list) that mean "this is a runtime
# data shape, not a component" -- the loader doesn't register these and
# the migration table must not name them.  Match on the bare identifier
# so dotted/qualified forms like ``pydantic.BaseModel`` still trip the
# filter.
_NON_COMPONENT_BASES = frozenset(
    {
        "BaseModel",
        "BaseSettings",
        "RootModel",
        "TypedDict",
        "NamedTuple",
        "Enum",
        "IntEnum",
        "StrEnum",
        "Flag",
        "Exception",
        "Protocol",
        "ABC",
        "ABCMeta",
        "object",
    }
)
_DYNAMIC_IMPORTS_RE = re.compile(
    r"_dynamic_imports\s*=\s*\{(?P<body>.+?)\}",
    re.DOTALL,
)
_DICT_ENTRY_RE = re.compile(r'"(?P<key>[\w]+)"\s*:\s*"(?P<value>[\w.]+)"')
_ALL_RE = re.compile(r"__all__\s*=\s*\[(?P<body>.+?)\]", re.DOTALL)
_PER_FILE_IGNORES_ENTRY_RE = re.compile(
    r'^"(?P<pattern>[^"]+)"\s*=\s*\[(?P<body>[^\]]+)\]',
    re.MULTILINE,
)


def _discover_classes(source: str) -> tuple[str, ...]:
    """Return top-level Component-shaped class names declared in ``source``.

    Filters out classes whose first base is a known non-Component
    shape (``BaseModel``, ``Enum``, ``TypedDict``, ``ABC``, ``Exception``,
    etc.).  The filter is base-list-based rather than name-based because
    Langflow's naming convention is loose: some components don't end in
    ``Component`` (``Dotenv``, ``GetEnvVar``).
    """
    result: list[str] = []
    for m in _CLASS_DECL_RE.finditer(source):
        bases_raw = m.group("bases")
        # Pull bare base identifiers (last dotted segment, no kwargs).
        base_idents = {
            tok.split(".")[-1].strip() for tok in re.split(r"[,\s]+", bases_raw.strip()) if tok and "=" not in tok
        }
        if base_idents & _NON_COMPONENT_BASES:
            continue
        result.append(m.group("name"))
    return tuple(result)


def _parse_legacy_init(init_path: Path) -> tuple[dict[str, str], tuple[str, ...]]:
    """Pull ``_dynamic_imports`` and ``__all__`` out of the legacy ``__init__.py``.

    Returns ``(dynamic_imports, all_list)``.  An empty mapping / tuple
    means the legacy ``__init__.py`` did not use the lazy-import shape
    -- in that case the script falls back to discovering classes by
    AST-scanning the moved files (which is what the original script
    did for the ``arxiv`` and ``duckduckgo`` pilots).
    """
    if not init_path.is_file():
        return {}, ()
    text = init_path.read_text(encoding="utf-8")

    di_match = _DYNAMIC_IMPORTS_RE.search(text)
    dynamic_imports: dict[str, str] = {}
    if di_match:
        for entry in _DICT_ENTRY_RE.finditer(di_match.group("body")):
            dynamic_imports[entry.group("key")] = entry.group("value")

    all_list: tuple[str, ...] = ()
    all_match = _ALL_RE.search(text)
    if all_match:
        all_list = tuple(re.findall(r'"([^"]+)"', all_match.group("body")))

    return dynamic_imports, all_list


def _discover_external_consumers(
    bundle: str,
    in_tree_dir: Path,
    bundle_dir: Path,
    *,
    shared_base_dir: Path | None,
) -> tuple[ConsumerRewrite, ...]:
    """Grep the repo for files that import ``lfx.components.<bundle>`` or ``lfx.base.<bundle>``.

    Excludes:
        * The in-tree provider directory (about to be moved).
        * The bundle's own tree.
        * ``__pycache__``, ``.venv``, ``node_modules``, build artefacts.
        * The migration-table JSON (which legitimately contains those
          strings as ``import_path`` values that must NOT be rewritten).
    """
    needles = (f"lfx.components.{bundle}", f"lfx.base.{bundle}")
    consumers: dict[Path, list[tuple[str, str]]] = {}

    rg_cmd = [
        "rg",
        "--files-with-matches",
        "--no-config",
        "--glob",
        "!**/__pycache__/**",
        "--glob",
        "!**/.venv/**",
        "--glob",
        "!**/node_modules/**",
        "--glob",
        "!**/dist/**",
        "--glob",
        "!**/build/**",
        "--glob",
        f"!{in_tree_dir.relative_to(REPO_ROOT)}/**",
        "--glob",
        f"!{bundle_dir.relative_to(REPO_ROOT)}/**",
        # The shared base (if any) moves into the bundle in Phase A;
        # any ``lfx.base.<bundle>`` self-imports inside it are handled
        # by _move_shared_base, not by consumer rewrite.
        *(("--glob", f"!{shared_base_dir.relative_to(REPO_ROOT)}/**") if shared_base_dir is not None else ()),
        # The migration table legitimately contains the legacy paths as
        # data; never rewrite it.
        "--glob",
        "!src/lfx/src/lfx/extension/migration/migration_table.json",
        # The component_index also contains datastax category metadata
        # in stripped/embedded source-code values; handled via a
        # separate surgical removal pass, not via substring rewrite.
        "--glob",
        "!src/lfx/src/lfx/_assets/component_index.json",
        # Root + bundle pyprojects contain ruff per-file-ignores tied
        # to ``src/lfx/src/lfx/components/<bundle>/`` paths.  Those are
        # migrated separately by _strip_root_ruff_ignores +
        # _render_pyproject -- never touch them via consumer rewrite.
        "--glob",
        "!pyproject.toml",
        "--glob",
        "!src/backend/base/pyproject.toml",
        "--glob",
        "!src/lfx/pyproject.toml",
        "--glob",
        "!src/sdk/pyproject.toml",
        "--glob",
        "!src/bundles/**/pyproject.toml",
        # Markdown and docs are documentation -- rewrites there are
        # presentation-only and risk breaking the doc rendering.  The
        # porter can update docs by hand if needed.
        "--glob",
        "!**/*.md",
        "--glob",
        "!**/*.mdx",
        # JSON files are saved-flow artefacts (starter projects, legacy
        # version fixtures).  The migration table rewrites these at flow
        # load time -- the bare-name + full-path + short-path entries
        # in the four-entry block we just appended cover every legacy
        # form Langflow has serialized.  Mechanically rewriting the
        # JSONs would defeat the migration test suite's purpose
        # (verifying frozen historical snapshots still load).
        "--glob",
        "!**/*.json",
        "-e",
        needles[0],
        "-e",
        needles[1],
        str(REPO_ROOT),
    ]
    try:
        out = subprocess.check_output(rg_cmd, text=True)  # noqa: S603
    except FileNotFoundError as exc:
        msg = "ripgrep (rg) is required for --rewrite-consumers but was not found on PATH."
        raise SystemExit(msg) from exc
    except subprocess.CalledProcessError as exc:
        # rg returns 1 when no matches are found; that's a legitimate
        # outcome (no external consumers exist).
        if exc.returncode == 1:
            return ()
        raise

    # The substitution order matters: do the most specific rewrite first
    # so the catch-all doesn't shadow it.  These ordered pairs are what
    # the datastax port applied by hand.
    base_subs = (
        # ``from lfx.base.<bundle> import X`` -> ``from lfx_<bundle>.base import X``
        (f"from lfx.base.{bundle} import", f"from lfx_{bundle}.base import"),
        # ``lfx.base.<bundle>.<module>`` patch-path form
        (f"lfx.base.{bundle}.", f"lfx_{bundle}.base."),
        # ``lfx.components.<bundle>.<module>`` patch-path / import-path form
        (f"lfx.components.{bundle}.", f"lfx_{bundle}.components.{bundle}."),
        # ``from lfx.components.<bundle> import X`` (re-export form) ->
        # ``from lfx_<bundle> import X``
        (f"from lfx.components.{bundle} import", f"from lfx_{bundle} import"),
    )

    for raw in out.splitlines():
        path = Path(raw).resolve()
        try:
            path.relative_to(REPO_ROOT)
        except ValueError:
            continue
        consumers[path] = list(base_subs)

    return tuple(ConsumerRewrite(path=p, substitutions=tuple(subs)) for p, subs in sorted(consumers.items()))


def _discover_backend_test_dirs(bundle: str) -> tuple[Path, ...]:
    """Auto-detect backend test directories tied to this bundle.

    Returns paths that exist; up to two: the base/<bundle> tests and the
    components/<bundle> tests.  Either or both may be absent.
    """
    candidates = (
        BACKEND_BASE_TESTS / bundle,
        REPO_ROOT / "src" / "backend" / "tests" / "unit" / "components" / bundle,
    )
    return tuple(c for c in candidates if c.is_dir())


def _discover_ruff_ignores(bundle: str) -> tuple[RuffIgnore, ...]:
    """Find ``per-file-ignores`` entries pointing at the in-tree provider directory."""
    if not ROOT_PYPROJECT.is_file():
        return ()
    text = ROOT_PYPROJECT.read_text(encoding="utf-8")
    needle_dir = f"src/lfx/src/lfx/components/{bundle}/"
    found: list[RuffIgnore] = []
    for m in _PER_FILE_IGNORES_ENTRY_RE.finditer(text):
        pat = m.group("pattern")
        if needle_dir not in pat and not pat.startswith(needle_dir.rstrip("/")):
            continue
        codes = tuple(re.findall(r'"([A-Z]+\d+)"', m.group("body")))
        if codes:
            found.append(RuffIgnore(pattern=pat, codes=codes))
    return tuple(found)


def _discover_base_extra(bundle: str) -> bool:
    """Detect whether ``src/backend/base/pyproject.toml`` ships a ``<bundle>`` extra."""
    if not BASE_PYPROJECT.is_file():
        return False
    text = BASE_PYPROJECT.read_text(encoding="utf-8")
    return bool(re.search(rf"^{re.escape(bundle)}\s*=\s*\[", text, re.MULTILINE))


def _validate_candidate(
    bundle: str,
    *,
    display_name: str | None,
    migration_release: str | None,
    discover_consumers: bool,
) -> PortPlan:
    """Refuse early if the candidate is not eligible for the mechanical port."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", bundle):
        msg = (
            f"--bundle {bundle!r} is not a valid bundle name (lowercase "
            "snake_case, 2-64 chars, starts with a letter).  This script "
            "ports an in-tree provider folder named exactly the same."
        )
        raise SystemExit(msg)

    in_tree = LFX_COMPONENTS / bundle
    if not in_tree.is_dir():
        msg = f"In-tree provider directory not found: {in_tree}"
        raise SystemExit(msg)

    bundle_dir = BUNDLES_DIR / bundle
    if bundle_dir.exists():
        msg = f"Bundle directory already exists: {bundle_dir}.  Refusing to overwrite."
        raise SystemExit(msg)

    deactivated_dup = LFX_COMPONENTS / "deactivated" / bundle
    if deactivated_dup.is_dir():
        msg = (
            f"A deactivated duplicate exists at {deactivated_dup}.  Resolve "
            "the duplicate manually before porting -- see "
            "src/bundles/PORTING.md § 0."
        )
        raise SystemExit(msg)

    component_files: list[ComponentFile] = []
    nested_subdirs: list[Path] = []
    for src in sorted(in_tree.iterdir()):
        if src.is_dir():
            if src.name == "__pycache__":
                continue
            # Nested subpackage (e.g. ``agentics/helpers``); validate
            # its files for ``from langflow`` imports too, then plan
            # to move the whole subdir wholesale.
            for nested in src.rglob("*.py"):
                if "__pycache__" in nested.parts:
                    continue
                text = nested.read_text(encoding="utf-8")
                if "from langflow" in text:
                    msg = (
                        f"{nested} imports from ``langflow`` -- the bundle is "
                        "installed against the public BUNDLE_API surface (lfx), "
                        "not Langflow internals.  Either rewrite the import or "
                        "leave the component in-tree.  See src/bundles/PORTING.md § 0."
                    )
                    raise SystemExit(msg)
            nested_subdirs.append(src)
            continue
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

    if not component_files and not nested_subdirs:
        msg = f"No ``*.py`` files under {in_tree}; nothing to port."
        raise SystemExit(msg)

    if migration_release is not None and not re.fullmatch(r"\d+\.\d+\.\d+", migration_release):
        msg = f"--migration-release {migration_release!r} must be a three-segment SemVer (e.g. 1.10.0)."
        raise SystemExit(msg)

    resolved_display = display_name if display_name is not None else bundle.replace("_", " ").title()

    shared_base = LFX_BASE / bundle
    shared_base_dir = shared_base if shared_base.is_dir() else None

    backend_test_dirs = _discover_backend_test_dirs(bundle)
    ruff_ignores = _discover_ruff_ignores(bundle)
    base_extra_present = _discover_base_extra(bundle)

    legacy_dynamic, legacy_all = _parse_legacy_init(in_tree / "__init__.py")

    consumer_rewrites: tuple[ConsumerRewrite, ...] = ()
    if discover_consumers:
        consumer_rewrites = _discover_external_consumers(bundle, in_tree, bundle_dir, shared_base_dir=shared_base_dir)

    return PortPlan(
        bundle=bundle,
        display_name=resolved_display,
        in_tree_dir=in_tree,
        bundle_dir=bundle_dir,
        component_files=tuple(component_files),
        migration_release=migration_release,
        nested_subdirs=tuple(nested_subdirs),
        shared_base_dir=shared_base_dir,
        backend_test_dirs=backend_test_dirs,
        ruff_ignores=ruff_ignores,
        consumer_rewrites=consumer_rewrites,
        base_extra_present=base_extra_present,
        legacy_dynamic_imports=legacy_dynamic,
        legacy_all=legacy_all,
    )


# ---------------------------------------------------------------------------
# Phase A: layout
# ---------------------------------------------------------------------------


def _render_package_init(plan: PortPlan) -> str:
    """Package-level ``__init__.py`` body: import every Component class by name."""
    classes: list[str] = []
    if plan.legacy_all:
        # Preserve the order the original ``__init__.py`` declared.
        ordered = list(plan.legacy_all)
        for class_name in ordered:
            module = plan.legacy_dynamic_imports.get(class_name)
            if module is None:
                # Fall back to AST discovery for classes the legacy
                # ``__init__.py`` didn't list (e.g. ``hcd.py`` in the
                # datastax port -- the class was importable via the
                # full path but not the module-level re-export).
                module = next(
                    (cf.path.stem for cf in plan.component_files if class_name in cf.classes),
                    None,
                )
            if module is None:
                continue
            classes.append(f"from lfx_{plan.bundle}.components.{plan.bundle}.{module} import {class_name}")
        # Also append classes the legacy init missed (so the bundle's
        # exported surface is the full discovered set).
        legacy_set = set(plan.legacy_all)
        for cf in plan.component_files:
            if cf.path.name == "__init__.py":
                continue
            for cls in cf.classes:
                if cls in legacy_set:
                    continue
                classes.append(f"from lfx_{plan.bundle}.components.{plan.bundle}.{cf.path.stem} import {cls}")
    else:
        for cf in plan.component_files:
            if cf.path.name == "__init__.py":
                continue
            for cls in cf.classes:
                classes.append(f"from lfx_{plan.bundle}.components.{plan.bundle}.{cf.path.stem} import {cls}")  # noqa: PERF401

    if not classes:
        return (
            "# TODO(port_bundle): no top-level ``class <Name>(...):`` declarations were\n"
            "# discovered.  Add the Component class re-exports manually so saved-flow\n"
            "# migration entries that target ``lfx.components.<bundle>.<Class>`` resolve."
        )

    all_names = sorted({line.rsplit(" import ", 1)[1] for line in classes})
    all_block = "\n    ".join(f'"{n}",' for n in all_names)
    return "\n".join(classes) + f"\n\n__all__ = [\n    {all_block}\n]"


def _render_components_init(plan: PortPlan) -> str:
    """Lazy-import shape for ``lfx_<bundle>/components/<bundle>/__init__.py``."""
    if plan.legacy_dynamic_imports:
        dynamic = dict(plan.legacy_dynamic_imports)
    else:
        dynamic = {}
        for cf in plan.component_files:
            if cf.path.name == "__init__.py":
                continue
            for cls in cf.classes:
                dynamic[cls] = cf.path.stem

    # Cover anything in the discovery that the legacy init missed.
    legacy_known = set(plan.legacy_dynamic_imports)
    for cf in plan.component_files:
        if cf.path.name == "__init__.py":
            continue
        for cls in cf.classes:
            if cls in legacy_known:
                continue
            dynamic.setdefault(cls, cf.path.stem)

    if not dynamic:
        return COMPONENTS_INIT_TEMPLATE.format(
            bundle=plan.bundle,
            type_checking_imports="    pass",
            dynamic_imports_dict="{}",
            all_list="[]",
        )

    ordered = sorted(dynamic.items())
    type_checking = "\n".join(f"    from .{module} import {cls}" for cls, module in ordered)
    dict_lines = ",\n".join(f'    "{cls}": "{module}"' for cls, module in ordered)
    all_lines = ",\n".join(f'    "{cls}"' for cls, _ in ordered)
    return COMPONENTS_INIT_TEMPLATE.format(
        bundle=plan.bundle,
        type_checking_imports=type_checking,
        dynamic_imports_dict="{\n" + dict_lines + ",\n}",
        all_list="[\n" + all_lines + ",\n]",
    )


def _render_pyproject(plan: PortPlan) -> str:
    wheel_extra = ""
    ruff_section = ""
    if plan.shared_base_dir is not None:
        wheel_extra = f'    "src/lfx_{plan.bundle}/base/**/*.py",\n'
    if plan.ruff_ignores:
        # Rewrite paths so they live under the bundle's own tree.
        entries: list[str] = []
        in_tree_prefix = f"src/lfx/src/lfx/components/{plan.bundle}/"
        bundle_prefix = f"src/lfx_{plan.bundle}/components/{plan.bundle}/"
        for ri in plan.ruff_ignores:
            new_pat = ri.pattern.replace(in_tree_prefix, bundle_prefix)
            comma_codes = ", ".join(f'"{c}"' for c in ri.codes)
            entries.append(f'"{new_pat}" = [{comma_codes}]')
        ruff_section = RUFF_SECTION_TEMPLATE.format(ruff_entries="\n".join(entries))
    return PYPROJECT_TEMPLATE.format(
        bundle=plan.bundle,
        display_name=plan.display_name,
        lfx_floor=_current_lfx_floor(),
        wheel_include_extra=wheel_extra,
        ruff_section=ruff_section,
    )


def _move_shared_base(plan: PortPlan, *, apply: bool) -> list[str]:
    """Move ``lfx/base/<bundle>/`` into the bundle's ``lfx_<bundle>/base/``."""
    if plan.shared_base_dir is None:
        return []
    actions: list[str] = []
    dst_dir = plan.bundle_dir / "src" / f"lfx_{plan.bundle}" / "base"
    actions.append(f"mkdir -p {dst_dir.relative_to(REPO_ROOT)}")
    if apply:
        dst_dir.mkdir(parents=True, exist_ok=True)

    base_classes: list[tuple[str, str]] = []  # (module_stem, ClassName)
    for src in sorted(plan.shared_base_dir.iterdir()):
        if not src.is_file() or src.suffix != ".py":
            continue
        if src.name == "__init__.py":
            continue
        dst = dst_dir / src.name
        actions.append(f"move {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
        if apply:
            shutil.move(str(src), str(dst))
            # Rewrite intra-bundle imports inside the moved base file.
            content = dst.read_text(encoding="utf-8")
            new_content = content.replace(
                f"from lfx.base.{plan.bundle}.",
                f"from lfx_{plan.bundle}.base.",
            )
            if new_content != content:
                dst.write_text(new_content, encoding="utf-8")
        # Record class re-exports for the base/__init__.py.
        text = src.read_text(encoding="utf-8") if not apply else dst.read_text(encoding="utf-8")
        for cls in _discover_classes(text):
            base_classes.append((src.stem, cls))  # noqa: PERF401

    # Write base/__init__.py that re-exports every class from every
    # module under the base subpackage.
    init_path = dst_dir / "__init__.py"
    actions.append(f"write {init_path.relative_to(REPO_ROOT)}")
    if apply:
        if base_classes:
            reexports = "\n".join(f"from lfx_{plan.bundle}.base.{m} import {c}" for m, c in base_classes)
            all_list = "[\n    " + ",\n    ".join(f'"{c}"' for _, c in base_classes) + ",\n]"
            body = reexports + f"\n\n__all__ = {all_list}"
        else:
            body = "__all__: list[str] = []"
        init_path.write_text(
            BASE_INIT_TEMPLATE.format(bundle=plan.bundle, base_reexports=body),
            encoding="utf-8",
        )

    # Finally, remove the original ``lfx.base.<bundle>`` directory.
    actions.append(f"rm -r {plan.shared_base_dir.relative_to(REPO_ROOT)}")
    if apply and plan.shared_base_dir.exists():
        shutil.rmtree(plan.shared_base_dir)
    return actions


def _rewrite_intra_bundle_imports(plan: PortPlan, *, apply: bool, components_dir: Path) -> list[str]:
    """Rewrite intra-bundle imports in moved components.

    Two substitutions, applied recursively across the bundle's
    ``components/<bundle>/`` tree (so nested subpackages like
    ``agentics/helpers/`` and ``agentics/inputs/`` are covered):

    * ``lfx.base.<bundle>`` -> ``lfx_<bundle>.base``    (shared-base move)
    * ``lfx.components.<bundle>`` -> ``lfx_<bundle>.components.<bundle>``
      (cross-file imports between components/<bundle>/ siblings or
      subpackages -- agentics in particular has helpers/* files that
      import ``lfx_agentics.components.agentics.constants`` etc.)
    """
    actions: list[str] = []
    substitutions: list[tuple[str, str]] = []
    if plan.shared_base_dir is not None:
        substitutions.append((f"lfx.base.{plan.bundle}", f"lfx_{plan.bundle}.base"))
    if plan.nested_subdirs:
        substitutions.append((f"lfx.components.{plan.bundle}", f"lfx_{plan.bundle}.components.{plan.bundle}"))

    if not substitutions:
        return actions
    if not apply:
        for needle, repl in substitutions:
            actions.append(f"rewrite ``{needle}`` -> ``{repl}`` in {components_dir.relative_to(REPO_ROOT)}/**/*.py")
        return actions

    for f in sorted(components_dir.rglob("*.py")):
        content = f.read_text(encoding="utf-8")
        new_content = content
        for needle, repl in substitutions:
            new_content = new_content.replace(needle, repl)
        if new_content != content:
            f.write_text(new_content, encoding="utf-8")
            actions.append(f"rewrite imports in {f.relative_to(REPO_ROOT)}")
    return actions


def _layout_bundle(plan: PortPlan, *, apply: bool) -> list[str]:
    """Create the bundle directory tree, write static files, move sources."""
    actions: list[str] = []
    package_dir = plan.bundle_dir / "src" / f"lfx_{plan.bundle}"
    components_dir = package_dir / "components" / plan.bundle

    actions.append(f"mkdir -p {components_dir.relative_to(REPO_ROOT)}")
    if apply:
        components_dir.mkdir(parents=True, exist_ok=False)
        # Make ``components/`` a proper package.
        (components_dir.parent / "__init__.py").write_text("", encoding="utf-8")

    files = {
        plan.bundle_dir / "pyproject.toml": _render_pyproject(plan),
        plan.bundle_dir / "README.md": README_TEMPLATE.format(bundle=plan.bundle, display_name=plan.display_name),
        package_dir / "__init__.py": PACKAGE_INIT_TEMPLATE.format(
            bundle=plan.bundle,
            display_name=plan.display_name,
            package_reexports=_render_package_init(plan),
        ),
        package_dir / "extension.json": EXTENSION_JSON_TEMPLATE.format(
            bundle=plan.bundle, display_name=plan.display_name
        ),
        components_dir / "__init__.py": _render_components_init(plan),
    }
    for path, content in files.items():
        actions.append(f"write {path.relative_to(REPO_ROOT)}")
        if apply:
            path.write_text(content, encoding="utf-8")

    for cf in plan.component_files:
        src = cf.path
        if src.name == "__init__.py":
            # The package-level __init__.py is rendered above; the
            # legacy file is removed in the in-tree cleanup phase.
            continue
        dst = components_dir / src.name
        actions.append(f"move {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
        if apply:
            shutil.move(str(src), str(dst))

    # Move nested subpackages wholesale (e.g. ``agentics/helpers``,
    # ``agentics/inputs``).  Their internal ``lfx.components.<bundle>...``
    # imports get rewritten in-place by the subsequent intra-bundle
    # import rewrite pass below.
    for subdir in plan.nested_subdirs:
        dst = components_dir / subdir.name
        actions.append(f"move {subdir.relative_to(REPO_ROOT)}/ -> {dst.relative_to(REPO_ROOT)}/")
        if apply:
            shutil.move(str(subdir), str(dst))

    # Move the shared base (if any) and rewrite intra-bundle imports.
    actions += _move_shared_base(plan, apply=apply)
    actions += _rewrite_intra_bundle_imports(plan, apply=apply, components_dir=components_dir)
    return actions


# ---------------------------------------------------------------------------
# Phase B: in-tree cleanup
# ---------------------------------------------------------------------------


def _delete_in_tree(plan: PortPlan, *, apply: bool) -> list[str]:
    """Remove the legacy in-tree provider directory."""
    actions = [f"rm -r {plan.in_tree_dir.relative_to(REPO_ROOT)}"]
    if apply and plan.in_tree_dir.exists():
        shutil.rmtree(plan.in_tree_dir)
    return actions


def _patch_components_init(plan: PortPlan, *, apply: bool) -> list[str]:
    """Remove the three references to ``<bundle>`` in components/__init__.py."""
    target = LFX_COMPONENTS / "__init__.py"
    actions = [f"strip {plan.bundle!r} refs from {target.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    text = target.read_text(encoding="utf-8")
    patterns = (
        rf"^ {{8}}{re.escape(plan.bundle)},\n",
        rf'^ {{4}}"{re.escape(plan.bundle)}": "__module__",\n',
        rf'^ {{4}}"{re.escape(plan.bundle)}",\n',
    )
    new_text = text
    for pattern in patterns:
        new_text = re.sub(pattern, "", new_text, count=1, flags=re.MULTILINE)
    if new_text == text:
        # Some bundles were never registered in the central
        # ``components.__init__.py`` -- e.g. ``cometapi`` and ``vllm``
        # ship in-tree component directories but the parent init does
        # not list them.  Treat as a no-op so the rest of the port
        # (workspace patch, migration entries, etc.) still completes.
        actions[-1] = f"  (no {plan.bundle!r} refs in {target.relative_to(REPO_ROOT)}; nothing to strip)"
        return actions
    target.write_text(new_text, encoding="utf-8")
    return actions


def _strip_root_ruff_ignores(plan: PortPlan, *, apply: bool) -> list[str]:
    """Remove ``per-file-ignores`` entries pointing at the in-tree provider dir."""
    if not plan.ruff_ignores:
        return []
    actions = [
        f"remove {len(plan.ruff_ignores)} ruff per-file-ignore "
        f"entry(ies) from {ROOT_PYPROJECT.relative_to(REPO_ROOT)} "
        f"(migrated to bundle pyproject)"
    ]
    if not apply:
        return actions
    text = ROOT_PYPROJECT.read_text(encoding="utf-8")
    for ri in plan.ruff_ignores:
        # Remove the entire entry block (``"<pattern>" = [...]\n``);
        # the block may span multiple lines so we anchor on the
        # pattern line and consume up to the closing ``]\n``.
        # The bracketed body may contain newlines, so use re.DOTALL.
        block = re.compile(
            r'^"' + re.escape(ri.pattern) + r'"\s*=\s*\[[^\]]*\]\n',
            re.MULTILINE | re.DOTALL,
        )
        new_text = block.sub("", text, count=1)
        if new_text == text:
            msg = (
                f"Could not strip ruff per-file-ignore entry for "
                f"{ri.pattern!r}; the regex may not match the current "
                "layout.  Edit by hand."
            )
            raise SystemExit(msg)
        text = new_text
    ROOT_PYPROJECT.write_text(text, encoding="utf-8")
    return actions


# ---------------------------------------------------------------------------
# Phase C: workspace + external consumers
# ---------------------------------------------------------------------------


def _insert_before_marker(text: str, end_marker: str, payload: str, *, what: str) -> str:
    needle = end_marker
    idx = text.find(needle)
    if idx == -1:
        msg = (
            f"Could not locate the {what} end marker ({needle!r}) in "
            "pyproject.toml.  Re-add the ``langflow-extensions:bundle-*`` "
            "marker pair before re-running -- see src/bundles/PORTING.md."
        )
        raise SystemExit(msg)
    line_start = text.rfind("\n", 0, idx) + 1
    return text[:line_start] + payload + text[line_start:]


def _patch_root_pyproject(plan: PortPlan, *, apply: bool) -> list[str]:
    actions = [f"patch {ROOT_PYPROJECT.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    text = ROOT_PYPROJECT.read_text(encoding="utf-8")
    bundle = plan.bundle

    if f"lfx-{bundle}" in text:
        msg = f"lfx-{bundle} already referenced in {ROOT_PYPROJECT.relative_to(REPO_ROOT)}; not patching."
        raise SystemExit(msg)

    dep_line = f'    "lfx-{bundle}>=0.1.0",\n'
    source_line = f"lfx-{bundle} = {{ workspace = true }}\n"
    member_line = f'    "src/bundles/{bundle}",\n'

    new_text = _insert_before_marker(text, "# langflow-extensions:bundle-deps-end", dep_line, what="bundle-deps")
    new_text = _insert_before_marker(
        new_text, "# langflow-extensions:bundle-sources-end", source_line, what="bundle-sources"
    )
    new_text = _insert_before_marker(
        new_text, "# langflow-extensions:bundle-members-end", member_line, what="bundle-members"
    )
    ROOT_PYPROJECT.write_text(new_text, encoding="utf-8")
    return actions


def _rewrite_consumers(plan: PortPlan, *, apply: bool) -> list[str]:
    if not plan.consumer_rewrites:
        return []
    actions: list[str] = [f"rewrite imports in {len(plan.consumer_rewrites)} external consumer file(s)"]
    if not apply:
        for cr in plan.consumer_rewrites:
            actions.append(f"  - {cr.path.relative_to(REPO_ROOT)}")  # noqa: PERF401
        return actions
    for cr in plan.consumer_rewrites:
        content = cr.path.read_text(encoding="utf-8")
        new_content = content
        for needle, replacement in cr.substitutions:
            new_content = new_content.replace(needle, replacement)
        if new_content != content:
            cr.path.write_text(new_content, encoding="utf-8")
            actions.append(f"  rewrote {cr.path.relative_to(REPO_ROOT)}")
    return actions


def _move_backend_tests(plan: PortPlan, *, apply: bool) -> list[str]:
    if not plan.backend_test_dirs:
        return []
    actions: list[str] = []
    dst_dir = plan.bundle_dir / "tests"
    actions.append(f"mkdir -p {dst_dir.relative_to(REPO_ROOT)}")
    if apply:
        dst_dir.mkdir(parents=True, exist_ok=True)

    needle_base = f"lfx.base.{plan.bundle}"
    repl_base = f"lfx_{plan.bundle}.base"
    needle_components = f"lfx.components.{plan.bundle}"
    repl_components = f"lfx_{plan.bundle}.components.{plan.bundle}"
    needle_short = f"from lfx.components.{plan.bundle} import"
    repl_short = f"from lfx_{plan.bundle} import"

    for test_dir in plan.backend_test_dirs:
        for src in sorted(test_dir.iterdir()):
            if not src.is_file() or src.suffix != ".py":
                continue
            if src.name == "__init__.py":
                # The bundle's tests/ doesn't need a backend-pkg __init__
                # since bundle tests run under bundle's own pytest config.
                actions.append(f"rm {src.relative_to(REPO_ROOT)}")
                if apply:
                    src.unlink()
                continue
            dst = dst_dir / src.name
            actions.append(f"move {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
            if apply:
                shutil.move(str(src), str(dst))
                content = dst.read_text(encoding="utf-8")
                for needle, replacement in (
                    (needle_short, repl_short),
                    (needle_components, repl_components),
                    (needle_base, repl_base),
                ):
                    content = content.replace(needle, replacement)
                dst.write_text(content, encoding="utf-8")
        # Remove the now-empty source test dir.
        if apply and test_dir.exists() and not any(test_dir.iterdir()):
            test_dir.rmdir()
            actions.append(f"rmdir {test_dir.relative_to(REPO_ROOT)}")
    return actions


# ---------------------------------------------------------------------------
# Phase D: artefacts (migration table, pilot test, component index, dockerfiles)
# ---------------------------------------------------------------------------


def _build_migration_entries(plan: PortPlan) -> list[dict]:
    release = plan.migration_release
    if release is None:
        return []
    entries: list[dict] = []
    seen: set[str] = set()
    # Use legacy_dynamic_imports first (preserves ordering / module mapping
    # from the original __init__.py); fall back to AST discovery.
    if plan.legacy_dynamic_imports:
        items = list(plan.legacy_dynamic_imports.items())
    else:
        items = []
        for cf in plan.component_files:
            if cf.path.name == "__init__.py":
                continue
            for cls in cf.classes:
                items.append((cls, cf.path.stem))
    # Cover any class the legacy init missed (e.g. ``hcd.HCDVectorStoreComponent``
    # in the datastax port).
    legacy = set(plan.legacy_dynamic_imports)
    for cf in plan.component_files:
        if cf.path.name == "__init__.py":
            continue
        for cls in cf.classes:
            if cls in legacy:
                continue
            items.append((cls, cf.path.stem))

    for cls, module in items:
        if cls in seen:
            continue
        seen.add(cls)
        target = f"ext:{plan.bundle}:{cls}@official"
        entries.extend(
            [
                {"bare_class_name": cls, "target": target, "added_in": release},
                {
                    "import_path": f"lfx.components.{plan.bundle}.{module}.{cls}",
                    "target": target,
                    "added_in": release,
                },
                {
                    "import_path": f"lfx.components.{plan.bundle}.{cls}",
                    "target": target,
                    "added_in": release,
                },
                {
                    "legacy_slot": f"ext:{plan.bundle}:{cls}@official-pre-a",
                    "target": target,
                    "added_in": release,
                },
            ]
        )
    return entries


def _write_migration_entries(plan: PortPlan, *, apply: bool) -> list[str]:
    if plan.migration_release is None:
        return []
    entries = _build_migration_entries(plan)
    if not entries:
        return []
    actions = [
        f"append {len(entries)} entries to {MIGRATION_TABLE.relative_to(REPO_ROOT)} ({len(entries) // 4} class(es) x 4)"
    ]
    if not apply:
        return actions
    table = json.loads(MIGRATION_TABLE.read_text(encoding="utf-8"))
    table["entries"].extend(entries)
    MIGRATION_TABLE.write_text(
        json.dumps(table, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return actions


def _render_pilot_test(plan: PortPlan) -> str:
    bundle = plan.bundle
    items: list[tuple[str, str]] = []
    legacy = plan.legacy_dynamic_imports
    if legacy:
        for cls, module in legacy.items():
            items.append((cls, module))
    else:
        for cf in plan.component_files:
            if cf.path.name == "__init__.py":
                continue
            for cls in cf.classes:
                items.append((cls, cf.path.stem))  # noqa: PERF401
    # Cover anything legacy missed.
    seen = {c for c, _ in items}
    for cf in plan.component_files:
        if cf.path.name == "__init__.py":
            continue
        for cls in cf.classes:
            if cls not in seen:
                items.append((cls, cf.path.stem))
                seen.add(cls)
    classes_literal = ",\n".join(f'    ("{c}", "{m}")' for c, m in items)
    return f'''"""Integration test: legacy {bundle} flows upgrade cleanly.

Generated by scripts/migrate/port_bundle.py.  Mirrors the duckduckgo and
arxiv pilots: every bundle class is exercised through the migration
table via the four legacy forms (bare name, full import path, package
re-export path, pre-Phase-A slot), plus distribution importability,
manifest discovery, and loader resolution.
"""

from __future__ import annotations

import json
from importlib import metadata as importlib_metadata
from pathlib import Path

import pytest
from lfx.extension.migration.loader import load_migration_table

REPO_ROOT = Path(__file__).resolve().parents[5]
TABLE_PATH = REPO_ROOT / "src" / "lfx" / "src" / "lfx" / "extension" / "migration" / "migration_table.json"

BUNDLE_CLASSES: tuple[tuple[str, str], ...] = (
{classes_literal},
)


@pytest.fixture(scope="module")
def migration_table():
    table, error = load_migration_table(TABLE_PATH)
    assert error is None, f"failed to load migration table: {{error}}"
    assert table is not None
    return table


def _saved_flow_node(node_id: str, type_value: str) -> dict:
    return {{
        "id": node_id,
        "type": "genericNode",
        "data": {{"id": node_id, "type": type_value, "node": {{"template": {{}}}}}},
    }}


def _saved_flow(*nodes: dict) -> dict:
    return {{"data": {{"nodes": list(nodes), "edges": []}}}}


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "module_stem"), BUNDLE_CLASSES)
def test_legacy_bare_name_flow_upgrades(migration_table, class_name: str, module_stem: str) -> None:  # noqa: ARG001
    """Bare class name rewrites to the canonical namespaced ID."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    expected = f"ext:{bundle}:{{class_name}}@official"
    flow = _saved_flow(_saved_flow_node(f"{bundle}-bare-{{class_name}}", class_name))
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

    expected = f"ext:{bundle}:{{class_name}}@official"
    legacy = f"lfx.components.{bundle}.{{module_stem}}.{{class_name}}"
    flow = _saved_flow(_saved_flow_node(f"{bundle}-full-{{class_name}}", legacy))
    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.integration
@pytest.mark.parametrize(("class_name", "module_stem"), BUNDLE_CLASSES)
def test_short_import_path_flow_upgrades(migration_table, class_name: str, module_stem: str) -> None:  # noqa: ARG001
    """Package-level import-path rewrites cleanly."""
    from lfx.extension.migration.rewrite import migrate_flow_payload

    expected = f"ext:{bundle}:{{class_name}}@official"
    legacy = f"lfx.components.{bundle}.{{class_name}}"
    flow = _saved_flow(_saved_flow_node(f"{bundle}-short-{{class_name}}", legacy))
    report = migrate_flow_payload(flow, table=migration_table)
    assert report.rewritten_count == 1
    assert flow["data"]["nodes"][0]["data"]["type"] == expected


@pytest.mark.integration
def test_lfx_{bundle}_distribution_is_importable() -> None:
    """The bundle is importable in the development workspace."""
    try:
        import lfx_{bundle}  # type: ignore[import-not-found]
    except ImportError:
        pytest.skip("lfx-{bundle} not installed in this test environment")

    for class_name, _module_stem in BUNDLE_CLASSES:
        klass = getattr(lfx_{bundle}, class_name, None)
        assert klass is not None, f"lfx_{bundle} does not re-export {{class_name!r}}"
        assert klass.__name__ == class_name


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
        import lfx_{bundle}  # type: ignore[import-not-found]

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


def _write_pilot_test(plan: PortPlan, *, apply: bool) -> list[str]:
    if plan.migration_release is None:
        return []
    dst = PILOT_TEST_DIR / f"test_pilot_{plan.bundle}_upgrade.py"
    if dst.exists():
        return [f"skip {dst.relative_to(REPO_ROOT)} (already exists; not overwriting)"]
    actions = [f"write {dst.relative_to(REPO_ROOT)}"]
    if apply:
        dst.write_text(_render_pilot_test(plan), encoding="utf-8")
    return actions


def _update_component_index(plan: PortPlan, *, apply: bool) -> list[str]:
    if not COMPONENT_INDEX_PATH.is_file():
        return []
    actions = [f"surgically remove {plan.bundle!r} category from {COMPONENT_INDEX_PATH.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    try:
        import orjson
    except ImportError as exc:
        msg = (
            "orjson is required for --update-index (same dep "
            "scripts/build_component_index.py uses).  Run this script "
            "under ``uv run``."
        )
        raise SystemExit(msg) from exc
    import hashlib

    with COMPONENT_INDEX_PATH.open("rb") as f:
        idx = json.loads(f.read())
    entry = next((e for e in idx["entries"] if e[0] == plan.bundle), None)
    if entry is None:
        actions.append(f"  (no {plan.bundle!r} entry in index; nothing to do)")
        return actions
    n_components = len(entry[1])
    idx["entries"] = [e for e in idx["entries"] if e[0] != plan.bundle]
    idx["metadata"]["num_modules"] -= 1
    idx["metadata"]["num_components"] -= n_components

    idx.pop("sha256", None)
    payload = orjson.dumps(idx, option=orjson.OPT_SORT_KEYS)
    idx["sha256"] = hashlib.sha256(payload).hexdigest()
    out = orjson.dumps(idx, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
    COMPONENT_INDEX_PATH.write_bytes(out + b"\n")
    actions.append(f"  removed {n_components} component(s) under {plan.bundle!r}; new sha256={idx['sha256']}")
    return actions


def _patch_backend_dockerfile(plan: PortPlan, *, apply: bool) -> list[str]:
    if not DOCKER_BACKEND.is_file():
        return []
    actions = [f"patch {DOCKER_BACKEND.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    text = DOCKER_BACKEND.read_text(encoding="utf-8")
    if f"./src/bundles/{plan.bundle}" in text:
        actions.append(f"  (lfx-{plan.bundle} already referenced; skipping)")
        return actions
    # Insert before the ``"./src/backend/base[complete..."`` line, after
    # any other ``./src/bundles/...`` line.
    bundle_line = f"        ./src/bundles/{plan.bundle} \\\n"
    pattern = re.compile(r"(\s+\./src/bundles/\w+ \\\n)(?!\s+\./src/bundles)", re.MULTILINE)
    new_text, count = pattern.subn(rf"\g<1>{bundle_line}", text, count=1)
    if count == 0:
        actions.append("  WARNING: no ``./src/bundles/...`` line found; patch by hand.")
        return actions
    DOCKER_BACKEND.write_text(new_text, encoding="utf-8")
    return actions


def _patch_base_dockerfile(plan: PortPlan, *, apply: bool) -> list[str]:
    if not DOCKER_BASE.is_file():
        return []
    actions = [f"patch {DOCKER_BASE.relative_to(REPO_ROOT)}"]
    if not apply:
        return actions
    text = DOCKER_BASE.read_text(encoding="utf-8")
    if f"/app/src/bundles/{plan.bundle}" in text:
        actions.append(f"  (lfx-{plan.bundle} already referenced; skipping)")
        return actions
    # Append a new ``uv pip install --no-deps`` block after the last
    # existing one (matched by ``/app/src/bundles/<existing>``).
    snippet = (
        f"\n# Bundle re-attach: ``lfx-{plan.bundle}`` ships the {plan.display_name}\n"
        f"# components as a standalone distribution.  ``--no-deps`` is intentional\n"
        f"# -- the bundle's runtime deps live in the langflow-base lockfile so\n"
        f"# installing them here would yank duplicates that fight the locked\n"
        f"# versions.\n"
        f"RUN --mount=type=cache,target=/root/.cache/uv \\\n"
        f"    RUSTFLAGS='--cfg reqwest_unstable' \\\n"
        f"    uv pip install --no-deps /app/src/bundles/{plan.bundle}\n"
    )
    pattern = re.compile(
        r"(uv pip install --no-deps /app/src/bundles/\w+\n)(?!.*uv pip install --no-deps /app/src/bundles)",
        re.DOTALL,
    )
    new_text, count = pattern.subn(rf"\g<1>{snippet}", text, count=1)
    if count == 0:
        actions.append(
            "  WARNING: no existing ``uv pip install --no-deps /app/src/bundles/...`` block found; patch by hand."
        )
        return actions
    DOCKER_BASE.write_text(new_text, encoding="utf-8")
    return actions


# ---------------------------------------------------------------------------
# Phase E: optional langflow-base[<bundle>] extra cleanup
# ---------------------------------------------------------------------------


def _remove_base_extra(plan: PortPlan, *, apply: bool) -> list[str]:
    if not plan.base_extra_present:
        return []
    actions = [
        f"remove ``{plan.bundle}`` extra + ``langflow-base[{plan.bundle}]`` ref "
        f"from {BASE_PYPROJECT.relative_to(REPO_ROOT)}"
    ]
    if not apply:
        return actions
    text = BASE_PYPROJECT.read_text(encoding="utf-8")
    # 1. Drop the extra definition line (``<bundle> = [...]``).
    extra_re = re.compile(
        rf"^{re.escape(plan.bundle)}\s*=\s*\[[^\]]*\]\n",
        re.MULTILINE,
    )
    new_text = extra_re.sub("", text, count=1)
    # 2. Drop the ``"langflow-base[<bundle>]",`` reference from
    # ``complete`` (always indented and followed by a newline).
    ref_re = re.compile(
        rf'\n\s*"langflow-base\[{re.escape(plan.bundle)}\]",',
    )
    new_text = ref_re.sub("", new_text, count=1)
    if new_text == text:
        actions.append("  (no changes; the script's regex did not match)")
        return actions
    BASE_PYPROJECT.write_text(new_text, encoding="utf-8")
    return actions


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Port an in-tree provider directory into a standalone Langflow "
            "Extension Bundle.  Writes the skeleton, moves the source files, "
            "rewrites external consumers, migrates ruff per-file ignores, "
            "patches the workspace, and -- with ``--migration-release`` -- "
            "appends migration entries, writes the pilot test, surgically "
            "removes the bundle's category from component_index.json, and "
            "patches both Dockerfiles."
        )
    )
    parser.add_argument("--bundle", required=True, help="Snake-case provider name.")
    parser.add_argument(
        "--display-name",
        default=None,
        help="Human-readable name used in extension.json and README.md.",
    )
    parser.add_argument(
        "--migration-release",
        default=None,
        help=(
            "SemVer release that introduces the bundle (e.g. ``1.10.0``).  "
            "Required for writing migration table entries and the pilot test."
        ),
    )
    parser.add_argument("--apply", action="store_true", help="Actually mutate the tree.")
    parser.add_argument(
        "--rewrite-consumers",
        action="store_true",
        help="Grep the repo for external consumers of ``lfx.components.<bundle>`` "
        "and ``lfx.base.<bundle>`` and rewrite their imports (requires ``rg`` on PATH).",
    )
    parser.add_argument(
        "--update-index",
        action="store_true",
        help="Surgically remove the bundle's category from component_index.json "
        "and recompute its sha256 (requires ``uv run``).",
    )
    parser.add_argument(
        "--update-dockerfiles",
        action="store_true",
        help="Patch ``docker/build_and_push_backend.Dockerfile`` and "
        "``docker/build_and_push_base.Dockerfile`` to install the bundle.",
    )
    parser.add_argument(
        "--remove-base-extra",
        action="store_true",
        help="Remove the ``<bundle>`` extra from langflow-base/pyproject.toml "
        "and any ``langflow-base[<bundle>]`` references from ``complete`` "
        "(only safe when the bundle's pyproject covers the same deps).",
    )
    args = parser.parse_args()

    plan = _validate_candidate(
        args.bundle,
        display_name=args.display_name,
        migration_release=args.migration_release,
        discover_consumers=args.rewrite_consumers,
    )

    actions: list[str] = []
    actions.append("== Phase A: bundle layout ==")
    actions += _layout_bundle(plan, apply=args.apply)
    actions.append("== Phase B: in-tree cleanup ==")
    actions += _delete_in_tree(plan, apply=args.apply)
    actions += _patch_components_init(plan, apply=args.apply)
    actions += _strip_root_ruff_ignores(plan, apply=args.apply)
    actions.append("== Phase C: workspace + consumers ==")
    actions += _patch_root_pyproject(plan, apply=args.apply)
    actions += _rewrite_consumers(plan, apply=args.apply)
    actions += _move_backend_tests(plan, apply=args.apply)
    if args.migration_release is not None or args.update_index or args.update_dockerfiles:
        actions.append("== Phase D: artefacts ==")
    if args.migration_release is not None:
        actions += _write_migration_entries(plan, apply=args.apply)
        actions += _write_pilot_test(plan, apply=args.apply)
    if args.update_index:
        actions += _update_component_index(plan, apply=args.apply)
    if args.update_dockerfiles:
        actions += _patch_backend_dockerfile(plan, apply=args.apply)
        actions += _patch_base_dockerfile(plan, apply=args.apply)
    if args.remove_base_extra:
        actions.append("== Phase E: optional cleanup ==")
        actions += _remove_base_extra(plan, apply=args.apply)

    mode = "apply" if args.apply else "dry-run"
    print(f"port_bundle ({mode}) for bundle {plan.bundle!r}:")
    print(f"  display_name        : {plan.display_name!r}")
    print(f"  in-tree dir         : {plan.in_tree_dir.relative_to(REPO_ROOT)}")
    print(
        f"  shared base dir     : {plan.shared_base_dir.relative_to(REPO_ROOT) if plan.shared_base_dir else '(none)'}"
    )
    print(f"  backend test dirs   : {[str(p.relative_to(REPO_ROOT)) for p in plan.backend_test_dirs]}")
    print(f"  ruff ignores        : {[ri.pattern for ri in plan.ruff_ignores]}")
    print(f"  external consumers  : {len(plan.consumer_rewrites)}")
    print(f"  langflow-base extra : {plan.base_extra_present}")
    print(f"  migration release   : {plan.migration_release or '(none)'}")
    print(f"  component classes   : {sum(len(cf.classes) for cf in plan.component_files)}")
    print()
    for action in actions:
        print(f"  {action}")

    if not args.apply:
        print()
        print("Dry-run.  Re-invoke with --apply to mutate the tree.")
    else:
        print()
        print("Done.  Manual follow-ups (always):")
        print("  * Review bundle pyproject's runtime deps and pin them carefully.")
        print("  * Run uv lock + uv sync.")
        print("  * Run ruff + pytest + lfx extension validate.")
        print("  * Inspect git diff before committing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
