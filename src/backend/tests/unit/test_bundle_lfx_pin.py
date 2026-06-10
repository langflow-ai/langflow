"""Tests for ``scripts/ci/sync_bundle_lfx_pin.py``.

The ``make patch`` target calls this script to keep every ``src/bundles/*``
package's ``lfx`` runtime-dependency floor in step with the Langflow/LFX
``major.minor`` line. These tests exercise the real script module so a
regression in the floor format or the dependency regex is caught without
running ``make``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = REPO_ROOT / "scripts" / "ci" / "sync_bundle_lfx_pin.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sync_bundle_lfx_pin", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_bundle_lfx_pin"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


# ---------------------------------------------------------------------------
# lfx_floor_spec
# ---------------------------------------------------------------------------


class TestLfxFloorSpec:
    # The .dev0 floor is load-bearing: nightlies are canonical X.Y.0.devN
    # pre-releases, which PEP 440 sorts BELOW X.Y.0, so a plain >=X.Y.0
    # floor makes the branch's own nightly lfx unresolvable.
    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("1.10.0", "lfx>=1.10.0.dev0,<2.0.0"),
            ("1.10.3", "lfx>=1.10.0.dev0,<2.0.0"),  # patch within a minor -> same floor
            ("1.11.0", "lfx>=1.11.0.dev0,<2.0.0"),
            ("2.0.0", "lfx>=2.0.0.dev0,<3.0.0"),
            ("v1.10.0", "lfx>=1.10.0.dev0,<2.0.0"),  # leading v tolerated
            ("10.4.2", "lfx>=10.4.0.dev0,<11.0.0"),  # multi-digit major
        ],
    )
    def test_floor(self, version, expected):
        assert mod.lfx_floor_spec(version) == expected

    @pytest.mark.parametrize("bad", ["", "1.10", "abc", "1", "x.y.z"])
    def test_rejects_unparseable(self, bad):
        with pytest.raises(ValueError, match="Unparseable version"):
            mod.lfx_floor_spec(bad)


# ---------------------------------------------------------------------------
# rewrite_lfx_dep
# ---------------------------------------------------------------------------


class TestRewriteLfxDep:
    FLOOR = "lfx>=1.10.0.dev0,<2.0.0"

    def test_rewrites_bare_floor(self):
        assert mod.rewrite_lfx_dep('    "lfx>=0.5.0",', self.FLOOR) == f'    "{self.FLOOR}",'

    def test_rewrites_existing_range(self):
        assert mod.rewrite_lfx_dep('    "lfx>=1.9.0,<2.0.0",', self.FLOOR) == f'    "{self.FLOOR}",'

    def test_rewrites_compatible_release_and_equality(self):
        assert mod.rewrite_lfx_dep('"lfx~=0.5.0"', self.FLOOR) == f'"{self.FLOOR}"'
        assert mod.rewrite_lfx_dep('"lfx==0.5.0"', self.FLOOR) == f'"{self.FLOOR}"'

    def test_idempotent(self):
        once = mod.rewrite_lfx_dep('"lfx>=0.5.0"', self.FLOOR)
        assert mod.rewrite_lfx_dep(once, self.FLOOR) == once

    def test_leaves_self_reference_untouched(self):
        # docling's optional-deps self-ref must NOT be treated as the lfx dep.
        for self_ref in ('"lfx-docling[local]"', '"lfx-docling[local,chunking,image-description]"'):
            assert mod.rewrite_lfx_dep(self_ref, self.FLOOR) == self_ref

    def test_leaves_nightly_form_untouched(self):
        # update_bundle_versions.py rewrites to this; sync must not clobber it.
        assert mod.rewrite_lfx_dep('"lfx-nightly==1.10.0.dev38"', self.FLOOR) == '"lfx-nightly==1.10.0.dev38"'

    def test_only_rewrites_runtime_dep_in_full_block(self):
        content = (
            "dependencies = [\n"
            '    "lfx>=0.5.0",\n'
            '    "langchain-community>=0.4.1,<1.0.0",\n'
            "]\n"
            "[project.optional-dependencies]\n"
            "all = [\n"
            '    "lfx-docling[local,chunking,image-description]",\n'
            "]\n"
        )
        out = mod.rewrite_lfx_dep(content, self.FLOOR)
        assert f'    "{self.FLOOR}",' in out
        assert '    "langchain-community>=0.4.1,<1.0.0",' in out  # untouched
        assert '    "lfx-docling[local,chunking,image-description]",' in out  # untouched


# ---------------------------------------------------------------------------
# sync_bundles (filesystem-level, on a temp tree)
# ---------------------------------------------------------------------------


class TestSyncBundles:
    def _make_bundle(self, bundles_dir: Path, name: str, lfx_line: str) -> Path:
        d = bundles_dir / name
        d.mkdir(parents=True)
        pyproject = d / "pyproject.toml"
        content = f'[project]\nname = "lfx-{name}"\ndependencies = [\n    "{lfx_line}",\n]\n'
        pyproject.write_text(content, encoding="utf-8")
        return pyproject

    def test_sync_updates_and_reports(self, tmp_path):
        bundles = tmp_path / "bundles"
        self._make_bundle(bundles, "arxiv", "lfx>=0.5.0")
        self._make_bundle(bundles, "ibm", "lfx>=1.10.0.dev0,<2.0.0")  # already correct

        results = dict(mod.sync_bundles("1.10.0", bundles))
        assert results == {"arxiv": True, "ibm": False}  # arxiv changed, ibm no-op
        assert '"lfx>=1.10.0.dev0,<2.0.0"' in (bundles / "arxiv" / "pyproject.toml").read_text()

    def test_sync_idempotent(self, tmp_path):
        bundles = tmp_path / "bundles"
        self._make_bundle(bundles, "arxiv", "lfx>=0.5.0")
        mod.sync_bundles("1.10.0", bundles)
        second = dict(mod.sync_bundles("1.10.0", bundles))
        assert second == {"arxiv": False}
