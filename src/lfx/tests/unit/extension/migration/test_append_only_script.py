"""Smoke tests for scripts/migrate/check_migration_append_only.py.

We exercise the script as a black-box subprocess so the test catches
SystemExit / argparse drift the same way CI would.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPT = REPO_ROOT / "scripts" / "migrate" / "check_migration_append_only.py"


def _write_table(
    path: Path,
    entries: list[dict],
    *,
    ambiguous_bare_names: list[dict] | None = None,
) -> None:
    body: dict = {"schema_version": 1, "entries": entries}
    if ambiguous_bare_names is not None:
        body["ambiguous_bare_names"] = ambiguous_bare_names
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - test harness invoking our own script
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


@pytest.mark.unit
def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"missing CI guard script at {SCRIPT}"


@pytest.mark.unit
def test_no_baseline_passes(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    _write_table(current, [])
    missing = tmp_path / "does-not-exist.json"
    proc = _run("--baseline", str(missing), "--current", str(current))
    # Script exits 2 on missing baseline file; that's a CI usage error,
    # not an append-only violation.
    assert proc.returncode == 2


@pytest.mark.unit
def test_pure_addition_passes(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_table(
        baseline,
        [
            {
                "bare_class_name": "Foo",
                "target": "ext:a:Foo@official",
                "added_in": "1.10.0",
            }
        ],
    )
    _write_table(
        current,
        [
            {
                "bare_class_name": "Foo",
                "target": "ext:a:Foo@official",
                "added_in": "1.10.0",
            },
            {
                "bare_class_name": "Bar",
                "target": "ext:b:Bar@official",
                "added_in": "1.11.0",
            },
        ],
    )
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.unit
def test_removal_fails(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_table(
        baseline,
        [
            {
                "bare_class_name": "Foo",
                "target": "ext:a:Foo@official",
                "added_in": "1.10.0",
            }
        ],
    )
    _write_table(current, [])
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 1
    assert "entry removed" in proc.stderr


@pytest.mark.unit
def test_target_mutation_fails(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_table(
        baseline,
        [
            {
                "bare_class_name": "Foo",
                "target": "ext:a:Foo@official",
                "added_in": "1.10.0",
            }
        ],
    )
    _write_table(
        current,
        [
            {
                "bare_class_name": "Foo",
                "target": "ext:b:Foo@official",  # changed bundle
                "added_in": "1.10.0",
            }
        ],
    )
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 1
    assert "target changed" in proc.stderr


@pytest.mark.unit
def test_reordering_is_allowed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    a = {"bare_class_name": "A", "target": "ext:x:A@official", "added_in": "1.10.0"}
    b = {"bare_class_name": "B", "target": "ext:x:B@official", "added_in": "1.10.0"}
    _write_table(baseline, [a, b])
    _write_table(current, [b, a])  # reordered
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# ambiguous_bare_names append-only invariants
# ---------------------------------------------------------------------------

_AMBIG_MERGE = {
    "name": "MergeDataComponent",
    "candidates": [
        "ext:processing:MergeDataComponent@official",
        "ext:deactivated:MergeDataComponent@official",
    ],
    "added_in": "1.10.0",
}


@pytest.mark.unit
def test_ambiguous_marker_addition_passes(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_table(baseline, [], ambiguous_bare_names=[])
    _write_table(current, [], ambiguous_bare_names=[_AMBIG_MERGE])
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.unit
def test_ambiguous_marker_removal_fails(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_table(baseline, [], ambiguous_bare_names=[_AMBIG_MERGE])
    _write_table(current, [], ambiguous_bare_names=[])
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 1
    assert "ambiguous_bare_names marker removed" in proc.stderr
    assert "MergeDataComponent" in proc.stderr


@pytest.mark.unit
def test_ambiguous_marker_candidates_shrunk_fails(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    shrunk = {
        "name": "MergeDataComponent",
        "candidates": ["ext:processing:MergeDataComponent@official"],  # one candidate dropped
        "added_in": "1.10.0",
    }
    _write_table(baseline, [], ambiguous_bare_names=[_AMBIG_MERGE])
    _write_table(current, [], ambiguous_bare_names=[shrunk])
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 1
    assert "candidates shrunk" in proc.stderr
    assert "ext:deactivated:MergeDataComponent@official" in proc.stderr


@pytest.mark.unit
def test_ambiguous_marker_candidate_addition_passes(tmp_path: Path) -> None:
    """Adding a new candidate to an existing marker is allowed (set grows)."""
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    grown = {
        "name": "MergeDataComponent",
        "candidates": [
            "ext:processing:MergeDataComponent@official",
            "ext:deactivated:MergeDataComponent@official",
            "ext:newbundle:MergeDataComponent@official",
        ],
        "added_in": "1.10.0",
    }
    _write_table(baseline, [], ambiguous_bare_names=[_AMBIG_MERGE])
    _write_table(current, [], ambiguous_bare_names=[grown])
    proc = _run("--baseline", str(baseline), "--current", str(current))
    assert proc.returncode == 0, proc.stderr
