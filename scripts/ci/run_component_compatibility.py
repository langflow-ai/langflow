"""Run prior-release checks using independently installed published package baselines."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from component_compatibility import (
    CompatibilityGateError,
    compare_registries,
    review_acknowledgments,
    validate_snapshot,
)
from component_release_plan import declared_distributions
from packaging.utils import InvalidName, canonicalize_name
from packaging.version import Version


def run(command: list[str], *, environment: dict[str, str] | None = None, timeout: int = 1200) -> None:
    subprocess.run(command, env=environment, check=True, timeout=timeout)  # noqa: S603


def snapshot(python: Path, exporter: Path, output: Path, home: Path) -> dict[str, Any]:
    home.mkdir(parents=True, exist_ok=True)
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "LANGFLOW_CONFIG_DIR": str(home / "config"),
        "DO_NOT_TRACK": "true",
    }
    run([str(python), str(exporter), "--output", str(output)], environment=environment, timeout=600)
    return json.loads(output.read_text())


def validate_plan(plan: dict[str, Any], current: dict[str, Any], root: Path) -> None:
    if plan.get("format_version") != 1 or not isinstance(plan.get("comparisons"), list):
        msg = "the release plan must contain format1 package comparisons"
        raise CompatibilityGateError(msg)
    target = declared_distributions(root)
    base = declared_distributions(root, plan["base_sha"])
    seen = set()
    validate_snapshot(current)
    for row in plan["comparisons"]:
        package = row["distribution"]
        try:
            normalized = canonicalize_name(package, validate=True) if isinstance(package, str) else None
        except InvalidName:
            normalized = None
        if normalized != package or package not in target or package in seen:
            msg = "the release plan contains an invalid, duplicate, or unknown distribution"
            raise CompatibilityGateError(msg)
        seen.add(package)
        ceiling = base.get(package, target[package])["version"]
        if row["baseline_ceiling"] != ceiling or row["target_version"] != target[package]["version"]:
            msg = "the release plan does not match the checked-out package versions"
            raise CompatibilityGateError(msg)
        if current["distributions"].get(package) != row["target_version"]:
            msg = f"{package} is missing or has the wrong version in the target registry environment"
            raise CompatibilityGateError(msg)
        if row["whole_registry"] is not (package == "langflow"):
            msg = "the release plan has the wrong registry comparison scope"
            raise CompatibilityGateError(msg)
        previous = row["previous_version"]
        if previous is not None:
            version = Version(previous)
            if (
                version.is_prerelease
                or version.is_devrelease
                or version.local is not None
                or version > Version(ceiling)
            ):
                msg = "the release baseline is outside the declared stable version line"
                raise CompatibilityGateError(msg)
    if seen != set(target):
        msg = "the release plan omitted one or more workspace distributions"
        raise CompatibilityGateError(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--acknowledgments", type=Path, default=Path("scripts/ci/component_breaks.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    exporter = Path(__file__).with_name("component_registry_snapshot.py")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan = json.loads(args.plan.read_text())
    changes = []
    failures = []
    with tempfile.TemporaryDirectory(prefix="component-compatibility-") as temporary:
        work = Path(temporary)
        current = snapshot(args.python.absolute(), exporter, args.output_dir / "current.json", work / "current-home")
        validate_plan(plan, current, root)
        for comparison in plan["comparisons"]:
            package = comparison["distribution"]
            previous = comparison["previous_version"]
            if previous is None:
                continue
            environment = work / package
            try:
                run(["uv", "venv", str(environment), "--python", str(args.python.absolute())])
                python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                requirement = (
                    f"{package}[bundles]=={previous}" if comparison["whole_registry"] else f"{package}=={previous}"
                )
                if package == "lfx-bundles":
                    requirement = f"{package}[all-no-torch]=={previous}"
                run(["uv", "pip", "install", "--python", str(python), requirement])
                baseline = snapshot(
                    python, exporter, args.output_dir / f"{package}-previous.json", work / f"{package}-home"
                )
                if baseline["distributions"].get(package) != previous:
                    msg = f"{package} did not export its requested published baseline version {previous}"
                    raise CompatibilityGateError(msg)
                changes.extend(
                    compare_registries(baseline, current, package, whole_registry=comparison["whole_registry"])
                )
            except (CompatibilityGateError, subprocess.SubprocessError) as exc:
                failures.append({"distribution": package, "previous_version": previous, "error": str(exc)})
            finally:
                # This run owns only these newly created temporary environments.
                if environment.exists():
                    shutil.rmtree(environment)
            report = {
                "format_version": 1,
                "plan": plan,
                "changes": [change.to_dict() for change in changes],
                "could_not_verify": failures,
            }
            (args.output_dir / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
        report = {
            "format_version": 1,
            "plan": plan,
            "changes": [change.to_dict() for change in changes],
            "could_not_verify": failures,
        }
        (args.output_dir / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
        candidate_notes = ["# Candidate component breaks", ""]
        for change in changes:
            candidate_notes.extend(
                [
                    f"## {change.distribution} / {change.component}",
                    f"Break identity `{change.id}`.",
                    f"Prior contract `{change.before_sha256}` from {change.source_version}.",
                    f"Target contract `{change.after_sha256}` from {change.target_version}.",
                    f"Snapshots [prior]({change.distribution}-previous.json) and [current](current.json).",
                    "Reasons " + ", ".join(reason["message"] for reason in change.reasons) + ".",
                    (
                        "If approved, add migration guidance at "
                        f"`docs/release_notes/compatibility/{change.distribution}-{change.id[:12]}.md`."
                    ),
                    "",
                ]
            )
        candidate_notes.append("These candidates are not acknowledgments or approved release decisions.")
        (args.output_dir / "candidate-breaks.md").write_text("\n".join(candidate_notes) + "\n")
        if failures:
            msg = "could not verify published baselines " + ", ".join(failure["distribution"] for failure in failures)
            raise CompatibilityGateError(msg)
        selected_comparisons = {
            (row["distribution"], row["previous_version"], row["target_version"])
            for row in plan["comparisons"]
            if row["previous_version"] is not None
        }
        notes = review_acknowledgments(
            changes, json.loads(args.acknowledgments.read_text()), root, comparisons=selected_comparisons
        )
        (args.output_dir / "release-notes.md").write_text(notes)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompatibilityGateError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
