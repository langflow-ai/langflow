"""Tests for ``scripts/ci/check_components_frozen.py``.

The bundle metapackage split (1.11) froze the top-level provider directories
under ``src/lfx/src/lfx/components/``: no NEW in-tree provider directory may be
added -- new providers go to ``lfx-bundles`` or a graduated ``lfx-<provider>``
package. The CI gate is an additions-only check that fails when the live tree
holds a top-level directory (one shipping ``__init__.py``) absent from the
committed baseline, while allowing removals and ignoring package machinery.

These tests load the real script module and drive ``main()`` against synthetic
component trees and baselines, so a regression in the gate's logic (e.g. the
``__init__.py`` requirement, the skip set, or baseline parsing) is caught
without running the CI job.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = REPO_ROOT / "scripts" / "ci" / "check_components_frozen.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_components_frozen", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_components_frozen"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _make_provider(components_dir: Path, name: str) -> None:
    """Create a top-level provider dir that ships an ``__init__.py``."""
    provider = components_dir / name
    provider.mkdir(parents=True)
    (provider / "__init__.py").write_text("", encoding="utf-8")


def _write_baseline(baseline_file: Path, names: list[str]) -> None:
    baseline_file.write_text("\n".join(names) + "\n", encoding="utf-8")


@pytest.fixture
def gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point the gate's module-level paths at a synthetic tree."""
    components_dir = tmp_path / "components"
    components_dir.mkdir()
    baseline_file = tmp_path / "frozen_component_dirs.txt"
    monkeypatch.setattr(mod, "COMPONENTS_DIR", components_dir)
    monkeypatch.setattr(mod, "BASELINE_FILE", baseline_file)
    return components_dir, baseline_file


def test_pass_when_all_dirs_in_baseline(gate):
    """Every live provider dir is baselined -> gate passes (0)."""
    components_dir, baseline_file = gate
    _make_provider(components_dir, "openai")
    _make_provider(components_dir, "anthropic")
    _write_baseline(baseline_file, ["openai", "anthropic"])

    assert mod.main() == 0


def test_fail_when_new_dir_not_in_baseline(gate):
    """A NEW provider dir with ``__init__.py`` absent from the baseline fails (1)."""
    components_dir, baseline_file = gate
    _make_provider(components_dir, "openai")
    _make_provider(components_dir, "brandnew")
    _write_baseline(baseline_file, ["openai"])

    assert mod.main() == 1


def test_pass_when_baseline_dir_removed(gate):
    """A baselined dir absent on disk (removed) is allowed -> gate passes (0)."""
    components_dir, baseline_file = gate
    _make_provider(components_dir, "openai")
    _write_baseline(baseline_file, ["openai", "removed_provider"])

    assert mod.main() == 0


def test_ignores_dirs_without_init(gate):
    """A new top-level dir lacking ``__init__.py`` does not trip the gate (0)."""
    components_dir, baseline_file = gate
    _make_provider(components_dir, "openai")
    # Stray directory with content but no __init__.py -> not a provider.
    stray = components_dir / "stray_no_init"
    stray.mkdir()
    (stray / "notes.txt").write_text("not a package", encoding="utf-8")
    _write_baseline(baseline_file, ["openai"])

    assert mod.main() == 0


def test_ignores_pycache_and_dotdirs(gate):
    """``__pycache__`` and dotdirs are ignored even when not in the baseline (0)."""
    components_dir, baseline_file = gate
    _make_provider(components_dir, "openai")
    # __pycache__ even with an __init__.py present must be skipped by name.
    _make_provider(components_dir, "__pycache__")
    # A dotdir shipping an __init__.py must be skipped by the leading-dot rule.
    _make_provider(components_dir, ".hidden")
    _write_baseline(baseline_file, ["openai"])

    assert mod.main() == 0


def test_baseline_ignores_blank_lines_and_comments(gate):
    """Blank lines and ``#`` comments in the baseline are ignored when parsed."""
    components_dir, baseline_file = gate
    _make_provider(components_dir, "openai")
    _make_provider(components_dir, "anthropic")
    baseline_file.write_text(
        "# top-level provider directories (frozen)\n\nopenai\n   \n  # indented comment\nanthropic\n",
        encoding="utf-8",
    )

    # Both live dirs are covered once comments/blanks are stripped.
    assert mod.main() == 0


def test_real_tree_is_clean():
    """The real component tree must be clean against the committed baseline (0).

    Runs the unmonkeypatched script against the actual repo paths -- the gate's
    current state must be green, otherwise CI would already be red.
    """
    assert mod.main() == 0
