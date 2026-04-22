"""Unit tests for driver --verify mode (compare_against_thresholds).

Cases:
  A. FAIL: current mean 50% above baseline -> non-zero exit + regression_comment.md.
  B. PASS: current mean 10% above baseline (below 15% allowed) -> exit 0 + no comment.
  C. Sentinel: baseline mean_ms=0 with prior runs (intentionally zeroed) -> non-zero
     + regression_comment.md.
  D. Mode mismatch: thresholds.measurement_mode != driver.MEASUREMENT_MODE -> stderr warning
     but NOT a failure by itself (still exits 0 when within threshold).
  E. Unanchored: baseline mean_ms=0 AND runs=0 (placeholder for a scenario that has
     never been snapshotted) -> exit 0 + no comment; the current number is recorded
     for visibility but does not gate the PR.

No mocks (user global rule). The verify helper is directly callable with dict inputs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.backend.tests.benchmarks import driver

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write_thresholds(
    path: Path,
    *,
    mean_ms: float,
    measurement_mode: str = "bytecode_compile_delta",
    allowed_pct: int = 15,
    runs: int = 10,
) -> None:
    """Helper: write a minimal thresholds.json at `path` with one lfx_bare entry."""
    payload = {
        "schema_version": 1,
        "measurement_mode": measurement_mode,
        "captured_on": "2026-01-01",
        "captured_ref": "deadbeef",
        "captured_runner": "Linux-test",
        "python_version": "3.13.0",
        "allowed_regression_pct": allowed_pct,
        "scenarios": {
            "lfx_bare": {"mean_ms": mean_ms, "stddev_ms": 50.0, "runs": runs},
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_verify_fail_case_trips_gate(tmp_path: Path) -> None:
    """A: 50% regression produces non-zero exit AND regression_comment.md."""
    thresholds_path = tmp_path / "thresholds.json"
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    _write_thresholds(thresholds_path, mean_ms=1000.0)

    current = {"lfx_bare": {"mean_ms": 1500.0, "stddev_ms": 60.0, "runs": 10}}
    rc = driver.compare_against_thresholds(current, thresholds_path, output_dir)

    assert rc != 0, "50% regression must exit non-zero"
    comment = output_dir / "regression_comment.md"
    assert comment.exists(), "regression_comment.md must be written on FAIL"
    body = comment.read_text(encoding="utf-8")
    assert "lfx_bare" in body
    assert "FAIL" in body
    assert "+50.0%" in body, f"expected +50.0% delta in body, got: {body!r}"
    assert "bytecode_compile_delta" in body, "measurement_mode surface must appear in comment"


def test_verify_pass_case_does_not_trip(tmp_path: Path) -> None:
    """B: 10% regression (below 15% allowed) passes and writes no comment."""
    thresholds_path = tmp_path / "thresholds.json"
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    _write_thresholds(thresholds_path, mean_ms=1000.0)

    current = {"lfx_bare": {"mean_ms": 1100.0, "stddev_ms": 60.0, "runs": 10}}
    rc = driver.compare_against_thresholds(current, thresholds_path, output_dir)

    assert rc == 0, "10% regression is under the 15% threshold; must exit 0"
    comment = output_dir / "regression_comment.md"
    assert not comment.exists(), "PASS path must NOT write regression_comment.md"


def test_verify_sentinel_baseline_always_trips(tmp_path: Path) -> None:
    """C: baseline mean_ms=0 sentinel trips for any finite current mean."""
    thresholds_path = tmp_path / "thresholds.json"
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    _write_thresholds(thresholds_path, mean_ms=0.0)

    current = {"lfx_bare": {"mean_ms": 1200.0, "stddev_ms": 60.0, "runs": 10}}
    rc = driver.compare_against_thresholds(current, thresholds_path, output_dir)

    assert rc != 0, "sentinel baseline (mean_ms=0) must trip the gate"
    comment = output_dir / "regression_comment.md"
    assert comment.exists(), "sentinel trip must write regression_comment.md"


def test_verify_unanchored_baseline_skips(tmp_path: Path) -> None:
    """E: baseline mean_ms=0 AND runs=0 (unanchored placeholder) does NOT trip the gate."""
    thresholds_path = tmp_path / "thresholds.json"
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    _write_thresholds(thresholds_path, mean_ms=0.0, runs=0)

    current = {"lfx_bare": {"mean_ms": 22183.74, "stddev_ms": 246.06, "runs": 5}}
    rc = driver.compare_against_thresholds(current, thresholds_path, output_dir)

    assert rc == 0, "unanchored baseline (runs=0) must NOT trip the gate"
    comment = output_dir / "regression_comment.md"
    assert not comment.exists(), "unanchored skip must NOT write regression_comment.md"


def test_verify_measurement_mode_mismatch_warns_not_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """D: measurement_mode mismatch is a warning, not a failure."""
    thresholds_path = tmp_path / "thresholds.json"
    output_dir = tmp_path / "reports"
    output_dir.mkdir()
    _write_thresholds(thresholds_path, mean_ms=1000.0, measurement_mode="dep_install_delta")

    # 10% regression -> within allowed threshold; the mode mismatch should not fail on its own.
    current = {"lfx_bare": {"mean_ms": 1100.0, "stddev_ms": 60.0, "runs": 10}}
    rc = driver.compare_against_thresholds(current, thresholds_path, output_dir)

    assert rc == 0, "measurement_mode mismatch must NOT fail when within threshold"
    captured = capsys.readouterr()
    assert "measurement_mode" in captured.err
    assert "dep_install_delta" in captured.err
