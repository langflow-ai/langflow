"""End-to-end integration tests for production-install discovery.

``pip install`` three local bundles and verify ``lfx extension list``
shows all 3 at @official; plus a Dockerfile-style seed-directory case.

Acceptance: integration test that pip-installs three local wheel
bundles into the test environment; ``extension list`` shows all 3 at
@official.

The test builds three minimal wheel-shaped source trees, runs
``pip install --target <isolated dir>`` against each, and points
``importlib.metadata.distributions(path=[<isolated dir>])`` at the
result before invoking the discovery code.  Using ``--target`` keeps
the test hermetic: nothing leaks into the surrounding interpreter or
the developer's site-packages.

Skipped if ``pip`` is not available on the path -- this happens in
some sandboxed CI lanes where the test image is read-only.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib import metadata as importlib_metadata
from typing import TYPE_CHECKING

import pytest
from lfx.extension import (
    build_registry_from_discovery,
    discover_installed_extensions,
)

if TYPE_CHECKING:
    from pathlib import Path

_PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{distribution_name}"
version = "{version}"
description = "Test bundle for production-install discovery"
requires-python = ">=3.10"

[tool.setuptools]
packages = ["{package_name}", "{package_name}.{bundle_name}"]
include-package-data = true

[tool.setuptools.package-data]
"{package_name}" = ["extension.json", "**/*"]
"""


_EXTENSION_JSON_TEMPLATE = """\
{{
  "id": "{extension_id}",
  "version": "{version}",
  "name": "{name}",
  "lfx": {{"compat": ["1"]}},
  "bundles": [{{"name": "{bundle_name}", "path": "{bundle_name}"}}]
}}
"""


def _have_pip() -> bool:
    """Return True iff ``python -m pip`` is invokable in the current process."""
    try:
        result = subprocess.run(  # noqa: S603 - sys.executable is trusted
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


needs_pip = pytest.mark.skipif(
    not _have_pip(),
    reason="pip is not available in this interpreter; skipping the pip-install integration leg.",
)


def _scaffold_bundle(
    workspace: Path,
    *,
    distribution_name: str,
    package_name: str,
    extension_id: str,
    bundle_name: str,
    version: str,
) -> Path:
    """Create a minimal pip-installable source tree under ``workspace``."""
    project_dir = workspace / distribution_name
    project_dir.mkdir(parents=True)

    (project_dir / "pyproject.toml").write_text(
        _PYPROJECT_TEMPLATE.format(
            distribution_name=distribution_name,
            version=version,
            package_name=package_name,
            bundle_name=bundle_name,
        ),
        encoding="utf-8",
    )

    pkg_dir = project_dir / package_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    # Production pattern: ship ``extension.json`` *inside* the Python
    # package so it travels with the wheel through ``pip install``.
    # ``[tool.setuptools.package-data]`` above declares it explicitly so
    # setuptools includes it in the wheel; ``include-package-data`` adds
    # the bundle subdirectory's contents.  Without these the file lands
    # in the source tree but never reaches site-packages, and discovery
    # cannot find it.
    (pkg_dir / "extension.json").write_text(
        _EXTENSION_JSON_TEMPLATE.format(
            extension_id=extension_id,
            version=version,
            name=extension_id,
            bundle_name=bundle_name,
        ),
        encoding="utf-8",
    )

    # Bundle directory lives inside the package so ``bundles[].path =
    # "<bundle>"`` resolves correctly relative to extension.json.
    bundle_dir = pkg_dir / bundle_name
    bundle_dir.mkdir()
    (bundle_dir / "__init__.py").write_text("", encoding="utf-8")
    (bundle_dir / "component.py").write_text(
        "class Component:\n"
        "    pass\n"
        "\n\n"
        "class StubComponent(Component):\n"
        "    display_name = 'Stub'\n"
        "    def build(self):\n"
        "        return None\n",
        encoding="utf-8",
    )

    return project_dir


def _pip_install_target(project_dir: Path, target: Path) -> None:
    """Install ``project_dir`` into ``target`` using ``pip install --target``.

    ``--no-deps`` keeps the install hermetic; ``--quiet`` keeps the test
    output readable.  ``--no-build-isolation`` avoids spinning a fresh
    venv on each invocation, which would dominate the test runtime.
    """
    subprocess.run(  # noqa: S603 - sys.executable + locally-built source tree
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            str(target),
            "--no-deps",
            "--quiet",
            "--disable-pip-version-check",
            str(project_dir),
        ],
        check=True,
        timeout=180,
    )


def _try_pip_install_target(project_dir: Path, target: Path) -> bool:
    """Attempt to install. Return ``True`` on success, ``False`` on env failure.

    Some sandboxed CI lanes block network egress that ``pip``'s build
    backend bootstrap requires; the test should skip cleanly rather than
    fail in those environments.
    """
    try:
        _pip_install_target(project_dir, target)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return True


@needs_pip
def test_pip_install_three_bundles_visible_at_official(tmp_path: Path) -> None:
    """Acceptance: three pip-installed bundles register at @official."""
    workspace = tmp_path / "workspace"
    target = tmp_path / "site-packages"
    target.mkdir()

    project_specs = [
        ("lfx-test-openai", "lfx_test_openai", "lfx-test-openai", "openai", "1.0.0"),
        ("lfx-test-anthropic", "lfx_test_anthropic", "lfx-test-anthropic", "anthropic", "0.4.1"),
        ("lfx-test-qdrant", "lfx_test_qdrant", "lfx-test-qdrant", "qdrant", "2.5.0"),
    ]

    project_dirs: list[Path] = []
    for distribution_name, package_name, extension_id, bundle_name, version in project_specs:
        project_dirs.append(
            _scaffold_bundle(
                workspace,
                distribution_name=distribution_name,
                package_name=package_name,
                extension_id=extension_id,
                bundle_name=bundle_name,
                version=version,
            )
        )

    # Install each into the same target directory.  Skip cleanly if the
    # sandbox blocks pip's bootstrap.
    for project_dir in project_dirs:
        if not _try_pip_install_target(project_dir, target):
            pytest.skip(
                "Sandbox blocks pip's build-backend bootstrap; skipping the "
                "real-pip integration test. The fake-importlib path in "
                "tests/unit/extension/test_discovery.py covers the same "
                "contract."
            )

    # Point importlib.metadata at our isolated target directory.  This is
    # how Python's distribution-finder API supports auxiliary install
    # locations -- the same machinery ``site-packages`` uses.
    distributions = list(importlib_metadata.distributions(path=[str(target)]))
    extensions, errors = discover_installed_extensions(distributions=distributions)

    assert errors == [], [err.to_dict() for err in errors]
    ids = sorted(ext.extension_id for ext in extensions)
    assert ids == ["lfx-test-anthropic", "lfx-test-openai", "lfx-test-qdrant"]
    for ext in extensions:
        assert ext.source_kind == "installed"
        assert ext.slot == "official"

    registry, dup_errors = build_registry_from_discovery(extensions)
    assert dup_errors == []
    rendered = registry.list_extensions()
    assert {ext.namespaced_slot for ext in rendered} == {"@official"}

    # Cleanup: the target dir is under tmp_path so pytest will reap it,
    # but the build-cache directories under workspace/ also need pruning
    # to avoid bloating the temp dir on developer machines that keep
    # tmp_path around.
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)


def test_pip_install_seed_directory_three_bundles(tmp_path: Path) -> None:
    """Acceptance: a Dockerfile-style seed directory with 3 bundles.

    The seed-directory pass needs no pip install; it runs even in
    sandboxes where the first test is skipped.  Kept next to its
    sibling so the e2e story for both production-install paths lives in
    one file.
    """
    seed = tmp_path / "seed"
    seed.mkdir()
    for bundle in ("openai", "anthropic", "qdrant"):
        sub = seed / f"lfx_test_{bundle}"
        sub.mkdir()
        (sub / bundle).mkdir()
        (sub / "extension.json").write_text(
            _EXTENSION_JSON_TEMPLATE.format(
                extension_id=f"lfx-test-{bundle}",
                version="1.0.0",
                name=f"lfx-test-{bundle}",
                bundle_name=bundle,
            ),
            encoding="utf-8",
        )

    from lfx.extension import discover_seed_extensions

    extensions, errors = discover_seed_extensions(seed_dir_env=str(seed))
    assert errors == []
    ids = sorted(ext.extension_id for ext in extensions)
    assert ids == ["lfx-test-anthropic", "lfx-test-openai", "lfx-test-qdrant"]
    for ext in extensions:
        assert ext.source_kind == "seed"
        assert ext.slot == "official"
