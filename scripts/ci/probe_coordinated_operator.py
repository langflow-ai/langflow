"""Run the offline OSS-to-operator release contract probe."""

# Keep the CLI report-bearing boundary resilient to import/runtime failures.
# ruff: noqa: BLE001

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Direct-file execution (the documented invocation) starts with ``scripts/ci``
# on sys.path. Add the repository root before importing the namespace package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.coordinated_release_probe.runner import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = run(args.operator_root.resolve())
    except Exception as error:  # Keep the executable's output machine-readable.
        report = {"status": "failed", "error": str(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
