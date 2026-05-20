"""Scaffolder for ``lfx extension init``.

Writes the *basic* single-Bundle template at the requested directory:

    <target>/
        extension.json     -- v0 manifest with ``$schema`` pointer
        README.md          -- one-page intro
        components/
            __init__.py
            hello.py       -- one minimal Component subclass
        tests/
            __init__.py
            test_hello.py  -- one well-formed unit test
        .gitignore         -- standard Python ignores

Out-of-scope templates (``full``, ``service``, ``route``, multi-bundle,
starter-projects) are explicitly refused with
``template-deferred-in-this-milestone``.  The CLI surface is responsible
for translating the ``--template`` flag into the same code; everything
non-trivial lives here so the CLI is a thin shell.

Design constraints honored:

    - The generated extension MUST validate clean against the manifest
      validator with zero errors.  The basic template is exercised by a
      test that runs ``init`` then immediately ``validate``.
    - The generated test file MUST be syntactically valid Python and
      written so a future ``extension test`` runner can collect and
      execute it without modification.  The test file uses ``pytest``
      conventions because that's the only supported test framework
      across the lfx tree.
    - All emitted text is deterministic given an :class:`InitOptions`
      tuple so snapshot tests are stable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.extension.errors import ExtensionError
from lfx.extension.manifest import _EXTENSION_ID_RE, EXTENSION_SCHEMA_URL

# The runtime validator's regex is the canonical source for what counts as
# a valid bundle name / extension id.  Importing it here (rather than
# recompiling local copies) eliminates a security-relevant drift surface:
# a future tightening of the runtime check applies to the template
# scaffolder for free, and the AC round-trip test that catches drift is
# preserved by definition.
from lfx.extension.manifest import BUNDLE_NAME_RE as _BUNDLE_NAME_RE

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


# ---------------------------------------------------------------------------
# Public template name and option dataclass
# ---------------------------------------------------------------------------

BASIC_TEMPLATE: str = "basic"
"""The only template accepted in this milestone.  The CLI surface refuses
unknown values with ``template-deferred-in-this-milestone``."""

# Reserved for the deferred-template error message.  Kept in sync with the
# spec (Bundle Separation Developer Guide §2: "richer templates ... are a
# later milestone").
_DEFERRED_TEMPLATE_NAMES: frozenset[str] = frozenset({"full", "service", "route", "multi-bundle", "starter-projects"})


_MIN_IDENTIFIER_LENGTH: int = 2
"""Manifest identifiers (id, bundle name) must be at least 2 characters
long; mirrors the schema regex's quantifier.  Hoisted as a constant so
the derivation helpers don't carry an unexplained literal."""


@dataclass(frozen=True)
class InitOptions:
    """Resolved options for a single ``init`` invocation.

    Frozen so the CLI can't mutate them mid-render and so tests can
    parametrize over multiple shapes by constructing fresh instances.
    """

    target: Path
    """Directory to create.  Must NOT already exist as a non-empty dir."""
    extension_id: str
    """Manifest ``id`` field, lowercase-hyphenated."""
    bundle_name: str
    """Bundle name in the manifest.  Lowercase snake_case, derived from
    ``extension_id`` by replacing hyphens with underscores."""
    display_name: str
    """Human-readable display name shown in Langflow's palette."""
    template: str = BASIC_TEMPLATE


@dataclass
class InitResult:
    """Outcome of a single ``init_extension`` call.

    Mirrors the loader's :class:`~lfx.extension.LoadResult` shape so the
    CLI surface can format both with the same helpers.
    """

    target: Path
    files_written: list[Path] = field(default_factory=list)
    errors: list[ExtensionError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Identifier derivation
# ---------------------------------------------------------------------------


def derive_extension_id(directory_name: str) -> str:
    """Turn a directory name into a manifest-shaped extension id.

    Lowercases, replaces ``_`` and whitespace with ``-``, collapses
    repeats, and strips invalid prefix/suffix characters.  Shorter than
    two characters becomes ``my-extension`` so ``init x`` still produces
    a valid manifest.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9-]+", "-", directory_name).strip("-").lower()
    if len(cleaned) < _MIN_IDENTIFIER_LENGTH or not cleaned[0].isalpha():
        cleaned = "my-extension"
    return cleaned[:64]


def derive_bundle_name(extension_id: str) -> str:
    """Derive a bundle name from an extension id.

    Replace ``-`` with ``_`` (manifest schema requires snake_case for
    bundle names) and trim to the same length budget.  Falls back to
    ``my_bundle`` if the input is degenerate.
    """
    bundle = extension_id.replace("-", "_")
    if not _BUNDLE_NAME_RE.match(bundle):
        bundle = "my_bundle"
    return bundle


def derive_display_name(extension_id: str) -> str:
    """Title-case the extension id for the manifest's ``name`` field."""
    return " ".join(word.capitalize() for word in extension_id.split("-")) or "My Extension"


# ---------------------------------------------------------------------------
# File contents (deterministic strings)
# ---------------------------------------------------------------------------


def _humanise_bundle_name(bundle_name: str) -> str:
    """``my_bundle`` / ``my-bundle`` -> ``My Bundle`` for the sidebar header.

    Kept tiny and deterministic so the scaffold output stays snapshot-stable;
    the field is optional in the schema so authors can overwrite it after
    init without invalidating the manifest.
    """
    parts = bundle_name.replace("-", "_").split("_")
    return " ".join(word.capitalize() for word in parts if word) or bundle_name


def _manifest_payload(options: InitOptions) -> dict:
    """Build the manifest dict that gets written to ``extension.json``."""
    return {
        "$schema": EXTENSION_SCHEMA_URL,
        "id": options.extension_id,
        "version": "0.1.0",
        "name": options.display_name,
        "description": (
            f"Auto-generated by `lfx extension init`. Replace this description "
            f"with what {options.display_name} actually does."
        ),
        "lfx": {"compat": ["1"]},
        "bundles": [
            {
                "name": options.bundle_name,
                "path": f"components/{options.bundle_name}",
                # display_name + icon let the sidebar render a polished header
                # without the user having to manually edit the manifest; the
                # frontend humanises the bundle name if these are dropped, so
                # they're safe to delete once the author picks a real glyph.
                "display_name": _humanise_bundle_name(options.bundle_name),
                "icon": "Package",
            }
        ],
    }


def _component_source(options: InitOptions) -> str:
    """The minimal Component subclass shipped in the basic template.

    Hand-written rather than f-stringed so the result is stable and
    snapshot-testable; the only dynamic bit is the class name.
    """
    class_name = "".join(part.capitalize() for part in options.bundle_name.split("_")) + "HelloComponent"
    return f'''"""Auto-generated component for the {options.display_name} extension.

Replace ``build`` with your real logic.  See the Langflow Component docs
at https://docs.langflow.org/components for input/output options.
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output


class {class_name}(Component):
    display_name = "{options.display_name} Hello"
    description = "Returns a greeting; replace with your real component logic."
    icon = "sparkles"

    inputs = [
        MessageTextInput(
            name="name",
            display_name="Name",
            info="Who to greet.",
            value="World",
        ),
    ]
    outputs = [Output(display_name="Greeting", name="greeting", method="build")]

    def build(self) -> str:
        return f"Hello, {{self.name}}!"
'''


def _test_source(options: InitOptions) -> str:
    """A pytest-compatible smoke test for the auto-generated component.

    The test imports the component and exercises its ``run`` method with
    a constructed instance.  It does NOT depend on Langflow's full graph
    machinery -- the test is a sanity check that the module imports
    cleanly and the method runs, suitable for ``pytest`` collection by a
    future ``extension test`` runner.
    """
    class_name = "".join(part.capitalize() for part in options.bundle_name.split("_")) + "HelloComponent"
    return f'''"""Smoke tests for the auto-generated {options.display_name} component.

Run with ``pytest`` from the extension root.  A future
``extension test`` CLI will collect these the same way.
"""

from __future__ import annotations

from components.{options.bundle_name}.hello import {class_name}


def test_hello_returns_greeting() -> None:
    component = {class_name}()
    component.name = "Eric"
    assert component.build() == "Hello, Eric!"


def test_hello_default_name() -> None:
    component = {class_name}()
    component.name = "World"
    assert component.build() == "Hello, World!"
'''


def _readme(options: InitOptions) -> str:
    """A short, opinionated README that points at the right next steps."""
    return f"""# {options.display_name}

A Langflow Extension generated by `lfx extension init`.

## Layout

```
{options.target.name}/
├── extension.json                 # v0 manifest
├── README.md
├── components/
│   └── {options.bundle_name}/
│       ├── __init__.py
│       └── hello.py               # the sample Component
└── tests/
    ├── __init__.py
    └── test_hello.py              # smoke tests
```

## Develop

> **Prerequisite**: `langflow` (which brings `lfx`) must be installed in
> your active environment before running any of the commands below or
> executing the generated `pytest` suite.  Install it with
> `pip install langflow` or your package manager of choice.

```bash
# Validate the manifest + bundle without executing imports
lfx extension validate .

# Run the bundled smoke tests (requires langflow / lfx)
pytest

# Launch a Langflow dev server with this extension loaded
lfx extension dev .
```

After `lfx extension dev`, edit any file under `components/` and click
**Reload** in the Langflow palette to pick up the change.

## Ship

When you're ready to share the extension, build a wheel and `pip install`
it the way you would any Python package; the manifest at the root will
be picked up at server startup as a real `@official` Extension.
"""


def _pyproject_payload(options: InitOptions) -> str:
    """A minimal PEP 621 ``pyproject.toml`` so ``pip install -e .`` works.

    The author guide and quickstart both tell first-time authors to
    ``pip install -e .`` after ``lfx extension init``; without this file
    that step fails with ``Neither 'setup.py' nor 'pyproject.toml' found``.

    The ``[tool.langflow.extension]`` entry mirrors the ``extension.json``
    discovery path so an installed wheel is picked up at server startup
    even when the consumer copied the manifest into a non-default
    location.  The wheel still ships ``extension.json`` (declared under
    ``[tool.setuptools.package-data]``) so ``importlib.metadata.files()``
    can locate it the way :func:`discover_installed_extensions` expects.
    """
    distribution_name = f"lfx-{options.extension_id}".replace("_", "-")
    package_name = options.bundle_name
    return f"""\
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{distribution_name}"
version = "0.1.0"
description = "{options.display_name} -- a Langflow Extension."
requires-python = ">=3.10"
dependencies = []

[tool.setuptools]
package-dir = {{"" = "."}}

[tool.setuptools.packages.find]
where = ["."]
include = ["components*"]

[tool.setuptools.package-data]
"*" = ["extension.json"]

[tool.langflow.extension]
manifest = "extension.json"

[project.entry-points."langflow.extensions"]
{package_name} = "components.{package_name}"
"""


_GITIGNORE_BODY: str = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
.venv/
venv/
env/

# Build artifacts
build/
dist/
*.egg-info/

# Editor / OS
.idea/
.vscode/
.DS_Store

# Test / coverage
.pytest_cache/
.coverage
htmlcov/
"""


def _files_for(options: InitOptions) -> list[tuple[str, str]]:
    """Return the (relative-path, content) tuples to write.

    Centralized so tests can iterate the same shape the writer uses.
    """
    return [
        ("extension.json", json.dumps(_manifest_payload(options), indent=2, sort_keys=False) + "\n"),
        ("pyproject.toml", _pyproject_payload(options)),
        ("README.md", _readme(options)),
        (".gitignore", _GITIGNORE_BODY),
        (f"components/{options.bundle_name}/__init__.py", ""),
        (f"components/{options.bundle_name}/hello.py", _component_source(options)),
        ("tests/__init__.py", ""),
        ("tests/test_hello.py", _test_source(options)),
    ]


# ---------------------------------------------------------------------------
# Public entry point: init_extension
# ---------------------------------------------------------------------------


def init_extension(options: InitOptions) -> InitResult:
    """Materialize the basic template at ``options.target``.

    Pre-flight checks (in order):
        1. ``options.template`` must equal :data:`BASIC_TEMPLATE`; any
           other value -- including the named deferred templates --
           returns a typed ``template-deferred-in-this-milestone`` error.
        2. ``options.target`` must not already exist as a non-empty
           directory; if it does, return ``extension-target-exists``.
        3. The path must not already exist as a non-directory file; if
           it does, return ``extension-target-invalid``.
        4. ``options.extension_id`` and ``options.bundle_name`` must
           match the manifest schema patterns; if they don't, return
           ``extension-target-invalid`` with a hint pointing at the
           identifier-derivation helpers.

    On success, every file in :func:`_files_for` is written under
    ``target`` and recorded on ``InitResult.files_written``.  ``ok`` is
    False iff at least one error was emitted.

    The function is idempotent against an empty ``target``: it creates
    the directory if missing.  It does NOT support overwriting an
    existing populated directory; use ``rm -rf`` and re-run instead so
    accidental scaffolding never trashes hand-edited code.
    """
    result = InitResult(target=options.target)

    if options.template != BASIC_TEMPLATE:
        result.errors.append(
            ExtensionError(
                code="template-deferred-in-this-milestone",
                message=(f"Template {options.template!r} is reserved for a future milestone."),
                location=str(options.target),
                content=options.template,
                hint=(
                    f"Re-run with `--template {BASIC_TEMPLATE}` (the default) and add the additional "
                    "primitives by hand once your basic extension is working."
                ),
            )
        )
        return result

    if not _EXTENSION_ID_RE.match(options.extension_id):
        result.errors.append(
            ExtensionError(
                code="extension-target-invalid",
                message=(
                    f"Derived extension id {options.extension_id!r} does not match the manifest pattern; "
                    "rename the target directory to lowercase-hyphenated."
                ),
                location=str(options.target),
                content=options.extension_id,
                hint=("Pick a directory name that starts with a letter and uses only [a-z0-9-], 2-64 chars."),
            )
        )
        return result
    if not _BUNDLE_NAME_RE.match(options.bundle_name):
        result.errors.append(
            ExtensionError(
                code="extension-target-invalid",
                message=(f"Derived bundle name {options.bundle_name!r} does not match the manifest pattern."),
                location=str(options.target),
                content=options.bundle_name,
                hint=("Bundle names use lowercase snake_case starting with a letter, 2-64 chars."),
            )
        )
        return result

    if options.target.exists() and not options.target.is_dir():
        result.errors.append(
            ExtensionError(
                code="extension-target-invalid",
                message="target path exists but is not a directory",
                location=str(options.target),
                hint="Pick a different target path.",
            )
        )
        return result
    if options.target.is_dir() and any(options.target.iterdir()):
        result.errors.append(
            ExtensionError(
                code="extension-target-exists",
                message=(f"Target directory {options.target} is not empty; refusing to scaffold."),
                location=str(options.target),
                hint=("Either remove the directory first or pick a fresh target path."),
            )
        )
        return result

    options.target.mkdir(parents=True, exist_ok=True)
    for relative, content in _files_for(options):
        path = options.target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        result.files_written.append(path)
    return result


def deferred_template_names() -> Iterable[str]:
    """Return the templates the basic-only init explicitly recognizes.

    Surfaced so the CLI can list "you probably meant ..." hints when an
    author types a template name that's known-future.  Order is
    deterministic (sorted) for stable help output.
    """
    return sorted(_DEFERRED_TEMPLATE_NAMES)
