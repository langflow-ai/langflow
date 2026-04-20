"""One-shot baseline + thresholds.json writer.

Delegates to `driver.main` to run the full scenario set in docker mode, then reads the
freshly-written baseline sidecar and transforms it into `src/backend/tests/benchmarks/
thresholds.json`. Emits `measurement_mode: "bytecode_compile_delta"` and
`allowed_regression_pct: 15` (10-15%, 15% is the lenient end that tolerates
hyperfine's 7-sample variance).

Per CONTEXT.md Claude's Discretion, the thresholds.json write is NOT auto-committed;
a human reviewer commits it after confirming the run was on a Linux GHA runner
(Pitfall 11: macOS timings are not authoritative).

Atomic write via tmp + os.replace so a crashing midwrite cannot corrupt a committed
thresholds.json.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from src.backend.tests.benchmarks import driver

ALLOWED_REGRESSION_PCT = 15
MEASUREMENT_MODE = driver.MEASUREMENT_MODE

BENCHMARKS_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BENCHMARKS_DIR / "reports"
DEFAULT_THRESHOLDS_PATH = BENCHMARKS_DIR / "thresholds.json"
DEFAULT_BASELINE_DIR = Path(__file__).resolve().parents[4] / ".planning" / "benchmarks"


def _locate_latest_baseline_json(baseline_dir: Path) -> Path:
    """Return the most recent baseline-YYYY-MM-DD.json in baseline_dir. Raises if none."""
    candidates = sorted(baseline_dir.glob("baseline-*.json"))
    if not candidates:
        msg = f"no baseline-*.json found in {baseline_dir}; driver.main likely failed"
        raise SystemExit(msg)
    return candidates[-1]


def _write_thresholds_atomic(payload: dict, target: Path) -> None:
    """Write `payload` as pretty-printed JSON to `target` atomically (tmp + os.replace)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False, suffix=".tmp") as tmp:
        json.dump(payload, tmp, indent=2)
        tmp_name = tmp.name
    os.replace(tmp_name, target)  # noqa: PTH105 -- explicit os.replace preserves atomic-rename semantics across filesystems


def main() -> int:
    """Run driver end-to-end in docker mode, then write thresholds.json from the baseline sidecar.

    Returns 0 on success, non-zero on driver failure.
    """
    # 1. Run the driver. snapshot.py always runs in docker mode with the full scenario set.
    driver_rc = driver.main(
        [
            "--mode",
            "docker",
            "--output-dir",
            str(DEFAULT_OUTPUT_DIR),
            "--baseline-dir",
            str(DEFAULT_BASELINE_DIR),
        ]
    )
    if driver_rc != 0:
        sys.stderr.write(f"driver.main exited with {driver_rc}; thresholds.json NOT written.\n")
        return driver_rc

    # 2. Read the just-produced baseline sidecar.
    baseline_json_path = _locate_latest_baseline_json(DEFAULT_BASELINE_DIR)
    baseline = json.loads(baseline_json_path.read_text(encoding="utf-8"))

    # 3. Transform into thresholds.json shape. We carry over only the three scenario names
    #    that plan 06's CI gate tracks; the lfx_with_flow_prebaked entry is intentionally NOT
    #    tracked as a threshold (it is an input to the MEAS-07 delta, not a gate target).
    tracked = ("lfx_bare", "lfx_with_flow", "langflow_run_http_ready")
    scenarios_out: dict[str, dict] = {}
    for name in tracked:
        src_entry = (baseline.get("scenarios") or {}).get(name, {})
        scenarios_out[name] = {
            "mean_ms": src_entry.get("mean_ms", 0.0),
            "stddev_ms": src_entry.get("stddev_ms", 0.0),
            "runs": src_entry.get("runs", 0),
        }

    thresholds = {
        "schema_version": 1,
        "measurement_mode": MEASUREMENT_MODE,
        "captured_on": baseline.get("captured_on"),
        "captured_ref": baseline.get("captured_ref"),
        "captured_runner": baseline.get("captured_runner"),
        "python_version": baseline.get("python_version"),
        "allowed_regression_pct": ALLOWED_REGRESSION_PCT,
        "scenarios": scenarios_out,
    }

    # 4. Atomic write.
    _write_thresholds_atomic(thresholds, DEFAULT_THRESHOLDS_PATH)

    # 5. Print the Pitfall 11 warning string (no em-dashes; repo-shipped content).
    sys.stdout.write(
        "thresholds.json overwritten. Per Pitfall 11 in 01-RESEARCH.md, this file MUST be "
        "captured on a Linux GHA runner (not macOS) for authoritative numbers. If you ran "
        "this locally, DO NOT commit the result.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
