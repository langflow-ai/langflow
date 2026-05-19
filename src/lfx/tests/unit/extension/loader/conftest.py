"""Shared fixtures and helpers for the extension-loader test suite.

Mirrors the package layout: each themed test file (load_extension, inline
bundles, distributions, types) imports from here so that synthetic
extensions and fake distributions are built the same way everywhere.

The autouse ``_scrub_synthetic_modules`` fixture is the only side-effecty
piece -- it strips the loader's ``_lfx_ext.<slot>...`` modules from
``sys.modules`` between tests so a later test's identically-named bundle
file gets re-imported clean rather than picking up a stale module.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable


_BASE_MANIFEST: dict = {
    "id": "lfx-pilot",
    "version": "1.2.3",
    "name": "Pilot Bundle",
    "lfx": {"compat": ["1"]},
    "bundles": [{"name": "pilot", "path": "components"}],
}


def component_source(class_name: str = "PilotThing", *, with_build: bool = True) -> str:
    """Return source text for a minimal Component subclass.

    The bundle defines its own toy ``Component`` base so the loader's
    subclass check fires without importing the real lfx Component (which
    drags in the full graph stack and is irrelevant to registration).
    """
    body = "    def build(self):\n        return None\n" if with_build else "    pass\n"
    return f"class Component:\n    pass\n\nclass {class_name}(Component):\n    display_name = 'X'\n{body}"


def make_extension(
    tmp_path: Path,
    *,
    manifest: dict | None = None,
    files: dict[str, str] | None = None,
) -> Path:
    """Lay out a synthetic extension at ``tmp_path``.

    Writes ``extension.json`` plus the bundle directory's Python files.
    Returns ``tmp_path`` so callers can chain ``load_extension(...)``.
    """
    manifest = manifest if manifest is not None else _BASE_MANIFEST
    (tmp_path / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    bundle_dir = tmp_path / manifest["bundles"][0]["path"]
    bundle_dir.mkdir(parents=True, exist_ok=True)
    files = files if files is not None else {"thing.py": component_source()}
    for name, source in files.items():
        target = bundle_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return tmp_path


def make_inline_bundle(parent: Path, name: str, files: dict[str, str] | None = None) -> Path:
    """Lay out a single inline bundle directory under ``parent``.

    Default file shape places one Component class named after the bundle
    so callers can assert on the registered ``namespaced_id``.
    """
    bundle_dir = parent / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    files = files if files is not None else {"thing.py": component_source(f"{name.capitalize()}Thing")}
    for fname, source in files.items():
        target = bundle_dir / fname
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    return bundle_dir


# ---------------------------------------------------------------------------
# Fake distributions for the manifest-first precedence tests
# ---------------------------------------------------------------------------


class FakeDist:
    """Minimal stand-in for ``importlib.metadata.Distribution``.

    Only the surface used by the loader is implemented: ``files``,
    ``locate_file``, ``metadata``.  Tests patch ``_name`` directly when they
    need to exercise the canonicalize-on-read path.
    """

    def __init__(self, name: str, root: Path, files: list[Path] | None = None) -> None:
        self._name = name
        self._root = root
        self._files = files

    @property
    def files(self) -> list[Path] | None:
        return self._files

    def locate_file(self, path: Path) -> Path:
        return self._root / path

    @property
    def metadata(self) -> dict[str, str]:
        return {"Name": self._name}


class FakeEntryPoint:
    """Minimal entry-point stand-in carrying ``name``, ``dist``, and a load() value.

    The optional ``loaded_value`` lets tests exercise the type-aware
    :func:`filter_component_entry_points` partition: pass a Component
    subclass to model a "legacy component entry-point" or a callable to
    model a route registrar.
    """

    def __init__(self, name: str, dist: FakeDist | None, loaded_value: object | None = None) -> None:
        self.name = name
        self.dist = dist
        self._loaded_value = loaded_value

    def load(self) -> object:
        return self._loaded_value


def make_installed_extension(parent: Path, distribution_name: str) -> FakeDist:
    """Create a fake installed extension distribution.

    The distribution's ``files`` list points at a real ``extension.json``
    so ``locate_file`` returns an existing path -- exactly the contract
    that ``installed_extension_roots`` consumes.
    """
    pkg_dir = parent / distribution_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": distribution_name,
        "version": "1.0.0",
        "name": distribution_name,
        "lfx": {"compat": ["1"]},
        "bundles": [{"name": distribution_name.replace("-", "_"), "path": "components"}],
    }
    manifest_file = pkg_dir / "extension.json"
    manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
    return FakeDist(
        name=distribution_name,
        root=parent,
        files=[Path(distribution_name) / "extension.json"],
    )


def make_installed_pyproject_extension(parent: Path, distribution_name: str) -> FakeDist:
    """Create a fake installed Extension whose manifest lives in pyproject.toml.

    Mirrors :func:`make_installed_extension` but exercises the
    ``[tool.langflow.extension]`` discovery path. ``files`` points at a
    real ``pyproject.toml`` containing a v0-shaped section so the
    installed-distribution discovery treats it as an Extension.
    """
    pkg_dir = parent / distribution_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    bundle_name = distribution_name.replace("-", "_")
    pyproject_text = f"""\
[project]
name = "{distribution_name}"

[tool.langflow.extension]
id = "{distribution_name}"
version = "1.0.0"
name = "{distribution_name}"

[tool.langflow.extension.lfx]
compat = ["1"]

[[tool.langflow.extension.bundles]]
name = "{bundle_name}"
path = "components"
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")
    return FakeDist(
        name=distribution_name,
        root=parent,
        files=[Path(distribution_name) / "pyproject.toml"],
    )


def make_installed_pyproject_no_extension(parent: Path, distribution_name: str) -> FakeDist:
    """Fake distribution shipping pyproject.toml WITHOUT [tool.langflow.extension].

    Used to assert that a stray pyproject.toml from an unrelated package is
    not mistakenly treated as a manifest.
    """
    pkg_dir = parent / distribution_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{distribution_name}"\n',
        encoding="utf-8",
    )
    return FakeDist(
        name=distribution_name,
        root=parent,
        files=[Path(distribution_name) / "pyproject.toml"],
    )


def make_installed_pyproject_malformed_extension(
    parent: Path,
    distribution_name: str,
) -> FakeDist:
    """Fake distribution shipping pyproject with [tool.langflow.extension] missing required fields.

    The section exists (so the loader must classify it as a manifest-shipping
    distribution) but the required ``id`` / ``version`` / ``bundles`` keys are
    missing. ``load_extension`` is expected to surface ``manifest-invalid`` --
    NOT silently drop the distribution.
    """
    pkg_dir = parent / distribution_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f"""\
[project]
name = "{distribution_name}"

[tool.langflow.extension]
# Intentionally missing id/version/lfx/bundles -- pydantic must reject.
description = "incomplete"
""",
        encoding="utf-8",
    )
    return FakeDist(
        name=distribution_name,
        root=parent,
        files=[Path(distribution_name) / "pyproject.toml"],
    )


# ---------------------------------------------------------------------------
# Autouse: scrub loader-installed modules between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _scrub_synthetic_modules() -> Iterable[None]:
    """Ensure tests don't leak imported modules across runs.

    The loader installs each bundle module under ``_lfx_ext.<slot>.<bundle>...``
    so absolute imports work; we strip those after every test so a later
    test's identically-named module gets re-imported clean.
    """
    yield
    for name in [m for m in sys.modules if m.startswith("_lfx_ext.")]:
        sys.modules.pop(name, None)
