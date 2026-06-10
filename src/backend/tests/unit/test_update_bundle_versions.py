"""Tests for ``scripts/ci/update_bundle_versions.py``.

The nightly build calls this script to rename every ``src/bundles/*``
package to its ``-nightly`` counterpart and re-point the root
``pyproject.toml`` at the renamed distributions. These tests exercise the
real script module so regressions in the rename/dep regexes are caught
without running a nightly. The extras-suffix cases exist because the
``lfx-bundles`` metapackage is referenced as ``lfx-bundles[all]`` (and
docling as ``lfx-docling[local]`` etc.) -- a dep regex that cannot see
through ``[extras]`` leaves the root pointing at the stable distribution
while the workspace member is renamed, which breaks the nightly resolve.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = REPO_ROOT / "scripts" / "ci" / "update_bundle_versions.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("update_bundle_versions", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_bundle_versions"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


_ROOT_PYPROJECT = """\
[project]
name = "langflow"
version = "1.11.0"
dependencies = [
    "lfx-bundles[all]>=1.0,<2.0",
    "lfx-duckduckgo>=0.1.0,<1.0.0",
]

[project.optional-dependencies]
docling = [
    "lfx-docling[local]>=0.1.0",
]

[tool.uv.sources]
lfx-bundles = { workspace = true }
lfx-duckduckgo = { workspace = true }
lfx-docling = { workspace = true }
"""

_METAPACKAGE_PYPROJECT = """\
[project]
name = "lfx-bundles"
version = "1.0.0"
dependencies = [
    "lfx>=1.11.0,<2.0.0",
]

[project.optional-dependencies]
aiml = ["openai>=1.68.2,<3.0.0"]
tavily = []
all = [
    "lfx-bundles[aiml]",
    "lfx-bundles[tavily]",
]

[project.entry-points."lfx.bundles"]
lfx_bundles = "lfx_bundles"
"""


class TestRenameBundlePyproject:
    def test_metapackage_self_ref_extras_follow_the_rename(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(_METAPACKAGE_PYPROJECT, encoding="utf-8")

        renamed = mod.rename_bundle_pyproject(pyproject, "1.11.0.dev38", "38")

        assert renamed == ("lfx-bundles", "lfx-bundles-nightly", "1.0.0.dev38")
        content = pyproject.read_text(encoding="utf-8")
        assert 'name = "lfx-bundles-nightly"' in content
        assert 'version = "1.0.0.dev38"' in content
        assert '"lfx-nightly==1.11.0.dev38"' in content
        assert '"lfx-bundles-nightly[aiml]"' in content
        assert '"lfx-bundles-nightly[tavily]"' in content
        # No stable self-ref left behind to pull the stable dist from PyPI.
        assert '"lfx-bundles[' not in content

    def test_rename_is_idempotent(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(_METAPACKAGE_PYPROJECT, encoding="utf-8")

        first = mod.rename_bundle_pyproject(pyproject, "1.11.0.dev38", "38")
        after_first = pyproject.read_text(encoding="utf-8")
        second = mod.rename_bundle_pyproject(pyproject, "1.11.0.dev38", "38")

        assert first == second
        assert pyproject.read_text(encoding="utf-8") == after_first


class TestUpdateRootPyprojectForBundle:
    def test_extras_suffixed_main_dep_is_rewritten_with_extras_preserved(self, tmp_path):
        root = tmp_path / "pyproject.toml"
        root.write_text(_ROOT_PYPROJECT, encoding="utf-8")

        mod.update_root_pyproject_for_bundle(root, "lfx-bundles", "lfx-bundles-nightly", "1.0.0.dev38")

        content = root.read_text(encoding="utf-8")
        assert '"lfx-bundles-nightly[all]==1.0.0.dev38"' in content
        assert '"lfx-bundles[all]' not in content
        assert "lfx-bundles-nightly = { workspace = true }" in content

    def test_extras_suffixed_optional_dep_is_rewritten(self, tmp_path):
        root = tmp_path / "pyproject.toml"
        root.write_text(_ROOT_PYPROJECT, encoding="utf-8")

        mod.update_root_pyproject_for_bundle(root, "lfx-docling", "lfx-docling-nightly", "0.1.5.dev38")

        content = root.read_text(encoding="utf-8")
        assert '"lfx-docling-nightly[local]==0.1.5.dev38"' in content
        assert '"lfx-docling[local]' not in content

    def test_plain_dep_keeps_working(self, tmp_path):
        root = tmp_path / "pyproject.toml"
        root.write_text(_ROOT_PYPROJECT, encoding="utf-8")

        mod.update_root_pyproject_for_bundle(root, "lfx-duckduckgo", "lfx-duckduckgo-nightly", "0.1.2.dev38")

        content = root.read_text(encoding="utf-8")
        assert '"lfx-duckduckgo-nightly==0.1.2.dev38"' in content
        assert "lfx-duckduckgo-nightly = { workspace = true }" in content

    def test_root_update_is_idempotent(self, tmp_path):
        root = tmp_path / "pyproject.toml"
        root.write_text(_ROOT_PYPROJECT, encoding="utf-8")

        mod.update_root_pyproject_for_bundle(root, "lfx-bundles", "lfx-bundles-nightly", "1.0.0.dev38")
        after_first = root.read_text(encoding="utf-8")
        mod.update_root_pyproject_for_bundle(root, "lfx-bundles", "lfx-bundles-nightly", "1.0.0.dev38")

        assert root.read_text(encoding="utf-8") == after_first
