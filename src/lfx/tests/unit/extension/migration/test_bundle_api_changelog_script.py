"""Smoke tests for scripts/migrate/check_bundle_api_changelog.py.

Exercise the script as a black-box subprocess.  Each test sets up a
synthetic git repo so we don't depend on the real working tree's diff
state (which changes from PR to PR).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPT = REPO_ROOT / "scripts" / "migrate" / "check_bundle_api_changelog.py"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - test harness invoking git on a tmp repo
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # The script resolves REPO_ROOT relative to its own location; copy it into
    # the synthetic repo so its CWD heuristic matches.
    repo_script_dir = cwd / "scripts" / "migrate"
    repo_script_dir.mkdir(parents=True, exist_ok=True)
    target = repo_script_dir / SCRIPT.name
    target.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    return subprocess.run(  # noqa: S603 - test harness
        [sys.executable, str(target), *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _init_repo(cwd: Path) -> None:
    _git(cwd, "init", "-q", "-b", "main")
    _git(cwd, "config", "user.email", "test@example.com")
    _git(cwd, "config", "user.name", "Test")


def _commit(cwd: Path, message: str) -> None:
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", message)


@pytest.mark.unit
def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"missing CI guard script at {SCRIPT}"


@pytest.mark.unit
def test_no_in_scope_changes_passes(tmp_path: Path) -> None:
    """A PR that only touches unrelated files passes without touching BUNDLE_API.md."""
    _init_repo(tmp_path)
    (tmp_path / "BUNDLE_API.md").write_text("# Bundle API\n\n## Changelog\n\n### v0\n\n- initial\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    _commit(tmp_path, "initial")
    _git(tmp_path, "checkout", "-q", "-b", "feat/x")

    (tmp_path / "README.md").write_text("hello world\n", encoding="utf-8")
    _commit(tmp_path, "tweak readme")

    proc = _run_script(tmp_path, "--base", "main")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no in-scope" in proc.stdout.lower()


@pytest.mark.unit
def test_in_scope_change_without_changelog_fails(tmp_path: Path) -> None:
    """Editing manifest.py without updating BUNDLE_API.md is rejected."""
    _init_repo(tmp_path)
    (tmp_path / "BUNDLE_API.md").write_text("# Bundle API\n\n## Changelog\n\n### v0\n\n- initial\n", encoding="utf-8")
    manifest = tmp_path / "src" / "lfx" / "src" / "lfx" / "extension" / "manifest.py"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("# manifest v0\n", encoding="utf-8")
    _commit(tmp_path, "initial")
    _git(tmp_path, "checkout", "-q", "-b", "feat/x")

    manifest.write_text("# manifest v0\n# extra\n", encoding="utf-8")
    _commit(tmp_path, "tweak manifest")

    proc = _run_script(tmp_path, "--base", "main")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BUNDLE_API.md" in proc.stderr


@pytest.mark.unit
def test_in_scope_change_with_changelog_passes(tmp_path: Path) -> None:
    """Editing manifest.py and adding a new ## Changelog line is accepted."""
    _init_repo(tmp_path)
    (tmp_path / "BUNDLE_API.md").write_text("# Bundle API\n\n## Changelog\n\n### v0\n\n- initial\n", encoding="utf-8")
    manifest = tmp_path / "src" / "lfx" / "src" / "lfx" / "extension" / "manifest.py"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("# manifest v0\n", encoding="utf-8")
    _commit(tmp_path, "initial")
    _git(tmp_path, "checkout", "-q", "-b", "feat/x")

    manifest.write_text("# manifest v0\n# extra\n", encoding="utf-8")
    (tmp_path / "BUNDLE_API.md").write_text(
        "# Bundle API\n\n## Changelog\n\n### v0\n\n- initial\n- added a new field\n",
        encoding="utf-8",
    )
    _commit(tmp_path, "tweak manifest + changelog")

    proc = _run_script(tmp_path, "--base", "main")
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.unit
def test_in_scope_change_with_unrelated_bundle_api_edit_fails(tmp_path: Path) -> None:
    """Editing manifest.py and BUNDLE_API.md but NOT under ## Changelog is rejected."""
    _init_repo(tmp_path)
    (tmp_path / "BUNDLE_API.md").write_text(
        "# Bundle API\n\nIntro paragraph.\n\n## Changelog\n\n### v0\n\n- initial\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "src" / "lfx" / "src" / "lfx" / "extension" / "manifest.py"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("# manifest v0\n", encoding="utf-8")
    _commit(tmp_path, "initial")
    _git(tmp_path, "checkout", "-q", "-b", "feat/x")

    manifest.write_text("# manifest v0\n# extra\n", encoding="utf-8")
    # Edit BUNDLE_API.md but only the intro paragraph, not the changelog.
    (tmp_path / "BUNDLE_API.md").write_text(
        "# Bundle API\n\nIntro paragraph.  Now reworded.\n\n## Changelog\n\n### v0\n\n- initial\n",
        encoding="utf-8",
    )
    _commit(tmp_path, "tweak manifest + intro")

    proc = _run_script(tmp_path, "--base", "main")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "## Changelog" in proc.stderr or "Changelog" in proc.stderr
