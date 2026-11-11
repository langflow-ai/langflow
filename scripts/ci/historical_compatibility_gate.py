"""Enforce historical pins while identifying two reviewed static-discovery limitations."""
# ruff: noqa: SLF001
# Reuse the existing fixture implementation rather than duplicate its comparisons.

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from component_compatibility import CompatibilityGateError, contract, digest


def check_pins(
    expected: dict[str, Any],
    actual: dict[str, Any],
    ledger: dict[str, Any],
    fixture_root: Path,
    lookup: dict[str, dict],
) -> list[str]:
    """Require exact fixture and target digests for every allowed historical delta."""
    if ledger.get("format_version") != 1 or not isinstance(ledger.get("limitations"), list):
        msg = "historical limitation ledger requires format_version1 and a limitations list"
        raise CompatibilityGateError(msg)
    allowed = {}
    for entry in ledger["limitations"]:
        key = (entry["release"], "hard_flows", f"{entry['fixture']}::{entry['node_id']}")
        if key in allowed:
            msg = "duplicate historical limitation"
            raise CompatibilityGateError(msg)
        path = (fixture_root / entry["release"] / entry["fixture"]).resolve()
        if not path.is_relative_to(fixture_root.resolve()):
            msg = "historical limitation fixture escapes its root"
            raise CompatibilityGateError(msg)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["fixture_sha256"]:
            msg = "historical limitation fixture changed and needs review"
            raise CompatibilityGateError(msg)
        target = lookup.get(entry["component"])
        if target is None or digest(contract(target)) != entry["target_contract_sha256"]:
            msg = "historical limitation target contract changed and needs review"
            raise CompatibilityGateError(msg)
        allowed[key] = entry
    observed = set()
    messages = []
    releases = set(expected) | set(actual)
    for release in sorted(releases):
        sources = set(expected.get(release, {})) | set(actual.get(release, {}))
        for source in sorted(sources):
            before = expected.get(release, {}).get(source, {})
            after = actual.get(release, {}).get(source, {})
            for node in sorted(set(before) | set(after)):
                if before.get(node) == after.get(node):
                    continue
                key = (release, source, node)
                entry = allowed.get(key)
                if entry is None or (before.get(node), after.get(node)) != (entry["expected"], entry["observed"]):
                    msg = (
                        f"unreviewed historical delta {release} {source} {node} {before.get(node)} -> {after.get(node)}"
                    )
                    raise CompatibilityGateError(msg)
                observed.add(key)
                messages.append(f"Reviewed limitation {release} {node}. {entry['reason']}")
    if observed != set(allowed):
        msg = "a historical limitation no longer applies and must be removed after review"
        raise CompatibilityGateError(msg)
    return messages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--ledger", type=Path, default=Path("scripts/ci/historical_compatibility_limitations.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixture_module = args.root / "src/lfx/tests/unit/upgrade/test_component_compat.py"
    spec = importlib.util.spec_from_file_location("historical_component_fixtures", fixture_module)
    if spec is None or spec.loader is None:
        msg = "historical fixture helpers are unavailable"
        raise CompatibilityGateError(msg)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    fixtures._require_tags()
    from importlib.resources import files

    from lfx.upgrade.checker import build_registry_lookup

    all_types = fixtures._all_types(json.loads(files("lfx").joinpath("_assets/component_index.json").read_text()))
    all_types.update(fixtures._retired_bundle_templates())
    lookup = build_registry_lookup(all_types)
    actual = {tag: fixtures._release_statuses(tag, all_types, lookup) for tag in fixtures.SOURCE_RELEASES}
    expected = json.loads(fixtures.EXPECTED_PATH.read_text())
    messages = check_pins(
        expected, actual, json.loads(args.ledger.read_text()), fixtures.DATA_DIR / "hard_flows", lookup
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"reviewed_limitations": messages, "actual": actual}, indent=2) + "\n")
    for message in messages:
        print(message)


if __name__ == "__main__":
    main()
