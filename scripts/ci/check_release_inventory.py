"""Validate an installed Langflow release tier against a checked-in contract."""

from __future__ import annotations

import argparse
import fnmatch
import json
import platform
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

BUNDLE_INIT_PATH_PARTS = 3


def normalize_name(value: str) -> str:
    """Return the PEP 503-normalized form of a distribution name."""
    return re.sub(r"[-_.]+", "-", value).lower()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def resolve_profile(contract: dict[str, Any], profile_name: str, seen: set[str] | None = None) -> dict[str, Any]:
    """Resolve one profile, including additive/removal changes from its parent."""
    profiles = contract.get("profiles", {})
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles))
        msg = f"Unknown inventory profile {profile_name!r}; available profiles: {available}"
        raise ValueError(msg)

    seen = set() if seen is None else set(seen)
    if profile_name in seen:
        msg = f"Inventory profile inheritance cycle at {profile_name!r}"
        raise ValueError(msg)
    seen.add(profile_name)

    raw_profile = profiles[profile_name]
    parent_name = raw_profile.get("extends")
    resolved = resolve_profile(contract, parent_name, seen) if parent_name else {}

    for key, value in raw_profile.items():
        if key == "extends":
            continue
        if key.endswith("_add"):
            target = key.removesuffix("_add")
            resolved[target] = _unique([*resolved.get(target, []), *value])
        elif key.endswith("_remove"):
            target = key.removesuffix("_remove")
            removals = set(value)
            resolved[target] = [item for item in resolved.get(target, []) if item not in removals]
        else:
            resolved[key] = value
    return resolved


def collect_inventory(entry_point_groups: list[str]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Collect installed Langflow distributions, files, and extension entry points."""
    distributions: dict[str, str] = {}
    distribution_files: dict[str, list[str]] = {}
    for distribution in metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = normalize_name(raw_name)
        distributions[name] = distribution.version
        distribution_files[name] = sorted(str(path) for path in (distribution.files or []))

    all_entry_points = metadata.entry_points()
    entry_points: dict[str, list[str]] = {}
    for group in entry_point_groups:
        if hasattr(all_entry_points, "select"):
            selected = all_entry_points.select(group=group)
        else:  # pragma: no cover - Python 3.10 compatibility
            selected = all_entry_points.get(group, [])
        entry_points[group] = sorted(entry_point.name for entry_point in selected)

    managed_distributions = {
        name: version
        for name, version in sorted(distributions.items())
        if name == "lfx" or name.startswith(("lfx-", "langflow"))
    }
    bundle_files = distribution_files.get("lfx-bundles", [])
    bundle_names = sorted(
        {
            parts[1]
            for file_name in bundle_files
            if len(parts := Path(file_name).parts) == BUNDLE_INIT_PATH_PARTS
            and parts[0] == "lfx_bundles"
            and parts[2] == "__init__.py"
            and not parts[1].startswith("_")
        }
    )

    actual = {
        "managed_distributions": managed_distributions,
        "entry_points": entry_points,
        "bundle_names": bundle_names,
    }
    return actual, distribution_files


def run_module_checks(checks: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Exercise compatibility shims in subprocesses so failed imports stay isolated."""
    results: list[dict[str, Any]] = []
    for check in checks:
        module = check["module"]
        attribute = check.get("attribute")
        expression = f"module = importlib.import_module({module!r})"
        if attribute:
            expression += f"; getattr(module, {attribute!r})"
        command = [sys.executable, "-c", f"import importlib; {expression}"]
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=60)  # noqa: S603
        output = (completed.stdout + completed.stderr).strip()
        result = {
            "module": module,
            "attribute": attribute,
            "expected": check["expect"],
            "returncode": completed.returncode,
        }
        if check.get("contains"):
            result["contains"] = check["contains"]
            result["contains_matched"] = check["contains"] in output
        if completed.returncode != 0:
            result["error_tail"] = output[-500:]
        results.append(result)
    return results


def validate_inventory(
    profile: dict[str, Any],
    actual: dict[str, Any],
    distribution_files: dict[str, list[str]],
    module_results: list[dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, bool]]]:
    """Return validation errors and required-file match details."""
    errors: list[str] = []
    installed = set(actual["managed_distributions"])

    required = {normalize_name(name) for name in profile.get("required_distributions", [])}
    missing = sorted(required - installed)
    if missing:
        errors.append(f"missing required distributions: {missing}")

    if profile.get("exact_distributions"):
        unexpected = sorted(installed - required)
        if unexpected:
            errors.append(f"unexpected managed distributions: {unexpected}")

    forbidden = {normalize_name(name) for name in profile.get("forbidden_distributions", [])}
    present_forbidden = sorted(forbidden & installed)
    if present_forbidden:
        errors.append(f"forbidden distributions installed: {present_forbidden}")

    for prefix in profile.get("forbidden_distribution_prefixes", []):
        matches = sorted(name for name in installed if name.startswith(normalize_name(prefix)))
        if matches:
            errors.append(f"distributions matching forbidden prefix {prefix!r}: {matches}")

    for group, expected in profile.get("entry_points", {}).items():
        expected_names = sorted(expected)
        actual_names = actual["entry_points"].get(group, [])
        if actual_names != expected_names:
            errors.append(f"entry-point group {group!r}: expected {expected_names}, got {actual_names}")

    expected_bundles = profile.get("bundle_names")
    if expected_bundles is not None and actual["bundle_names"] != sorted(expected_bundles):
        errors.append(f"bundle inventory: expected {sorted(expected_bundles)}, got {actual['bundle_names']}")

    file_matches: dict[str, dict[str, bool]] = {}
    for raw_distribution, patterns in profile.get("required_files", {}).items():
        distribution = normalize_name(raw_distribution)
        files = distribution_files.get(distribution, [])
        file_matches[distribution] = {}
        for pattern in patterns:
            matched = any(fnmatch.fnmatch(file_name, pattern) for file_name in files)
            file_matches[distribution][pattern] = matched
            if not matched:
                errors.append(f"{distribution} is missing required file matching {pattern!r}")

    for result in module_results:
        expected = result["expected"]
        if expected == "success" and result["returncode"] != 0:
            errors.append(f"module check {result['module']!r} did not import successfully")
        elif expected == "error" and result["returncode"] == 0:
            errors.append(f"module check {result['module']!r} unexpectedly imported successfully")
        if result.get("contains") and not result.get("contains_matched"):
            errors.append(f"module check {result['module']!r} did not include {result['contains']!r}")

    return errors, file_matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    profile = resolve_profile(contract, args.profile)
    entry_point_groups = sorted(profile.get("entry_points", {}))
    actual, distribution_files = collect_inventory(entry_point_groups)
    module_results = run_module_checks(profile.get("module_checks", []))
    errors, file_matches = validate_inventory(profile, actual, distribution_files, module_results)

    actual["required_files"] = file_matches
    actual["module_checks"] = module_results
    report = {
        "schema_version": contract["schema_version"],
        "profile": args.profile,
        "passed": not errors,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "expected": profile,
        "actual": actual,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if errors:
        print(f"Release inventory profile {args.profile!r} failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Release inventory profile {args.profile!r} passed; report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
