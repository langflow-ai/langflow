#!/usr/bin/env python3
"""Prove every shipped capability manifest still matches its discovery-gate matrix.

``design/dedicated-integrations/matrices/<provider>.json`` is the frozen INT-1
record: which actions ship, which identity executes each one, which scopes they
need, which deployment contexts they appear in, and which component class
implements them. A bundle repeats that contract at runtime in
``capabilities.v1.json``, which is what discovery, the connection picker, and
the policy layer actually read.

Nothing but this checker keeps the two from drifting: a scope added to the
manifest but not the matrix escapes the gate's review, and a scope added to the
matrix but not the manifest is silently never requested at consent time.

The checker is generic over bundles. It discovers every
``src/bundles/*/src/*/extension.json`` that declares ``integrations`` and
compares each capability against the matrix row with the same action id.

Extra capabilities and extra auth profiles are allowed: later tickets add
trigger-side capabilities and an app-token profile that the wave-1 action
matrix does not describe. Every *matrix* row marked ``include`` must be
present, and every capability whose id matches a matrix row must agree with it.

Usage:
    python scripts/ci/check_capability_manifests.py
    python scripts/ci/check_capability_manifests.py --design-root design/dedicated-integrations
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESIGN_ROOT = REPO_ROOT / "design" / "dedicated-integrations"
DEFAULT_BUNDLES_ROOT = REPO_ROOT / "src" / "bundles"

CONTEXT_ORDER = ("hosted", "self_managed", "desktop", "headless")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
    """Repo-relative path when possible; absolute otherwise (tests use tmp dirs)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def discover_manifests(bundles_root: Path) -> list[tuple[str, Path, Path]]:
    """Return ``(provider_id, extension_manifest, capability_manifest)`` triples."""
    found: list[tuple[str, Path, Path]] = []
    for extension_path in sorted(bundles_root.glob("*/src/*/extension.json")):
        manifest = _load_json(extension_path)
        bundle_paths = {bundle["name"]: bundle["path"] for bundle in manifest.get("bundles", [])}
        for integration in manifest.get("integrations", []):
            bundle_dir = extension_path.parent / bundle_paths[integration["bundle"]]
            found.append((integration["provider_id"], extension_path, bundle_dir / integration["path"]))
    return found


def _matrix_rows(matrix: dict) -> dict[str, dict]:
    return {action["action_id"]: action for action in matrix["actions"] if action["decision"] == "include"}


def _expected_contexts(action: dict) -> list[str]:
    return [context for context in CONTEXT_ORDER if context in action["deployment_contexts"]]


def _expected_scopes(action: dict) -> tuple[list[str], list[tuple[str, str, str, str]]]:
    required = [scope["scope"] for scope in action["scopes"] if scope["role"] == "required"]
    conditional = [
        (scope["scope"], scope["role"], scope["condition"]["kind"], scope["condition"]["input"])
        for scope in action["scopes"]
        if scope["role"] != "required"
    ]
    return required, conditional


def _actual_conditional(capability: dict) -> list[tuple[str, str, str, str]]:
    return [
        (
            requirement["scope"],
            requirement["role"],
            requirement["condition"]["kind"],
            requirement["condition"]["input"],
        )
        for requirement in capability.get("conditional_scopes", [])
    ]


def compare(provider_id: str, manifest_path: Path, matrix_path: Path) -> list[str]:
    """Return one message per disagreement between a manifest and its matrix."""
    errors: list[str] = []
    where = _display(manifest_path)

    if not matrix_path.is_file():
        return [f"{where}: no capability matrix at {_display(matrix_path)} for provider {provider_id!r}"]

    manifest = _load_json(manifest_path)
    matrix = _load_json(matrix_path)

    if manifest.get("provider_id") != provider_id:
        errors.append(f"{where}: provider_id {manifest.get('provider_id')!r} does not match the extension manifest")
    if manifest.get("display_name") != matrix.get("display_name"):
        errors.append(
            f"{where}: display_name {manifest.get('display_name')!r} "
            f"does not match the matrix ({matrix.get('display_name')!r})"
        )

    rows = _matrix_rows(matrix)
    capabilities = {capability["id"]: capability for capability in manifest.get("capabilities", [])}
    profiles = {profile["id"] for profile in manifest.get("auth_profiles", [])}

    errors.extend(
        f"{where}: matrix action {action_id!r} has no capability" for action_id in sorted(set(rows) - set(capabilities))
    )

    for action_id in sorted(set(rows) & set(capabilities)):
        action = rows[action_id]
        capability = capabilities[action_id]
        required, conditional = _expected_scopes(action)
        checks = (
            ("display_name", capability.get("display_name"), action["display_name"]),
            ("identity", capability.get("identity"), action["identity"]),
            ("substrate", capability.get("substrate"), action["substrate"]),
            ("maturity", capability.get("maturity"), action["substrate_ga_status"]),
            ("component_ref", capability.get("component_ref"), action["component_class"]),
            ("required_scopes", sorted(capability.get("required_scopes", [])), sorted(required)),
            ("conditional_scopes", sorted(_actual_conditional(capability)), sorted(conditional)),
            ("deployment_contexts", list(capability.get("deployment_contexts", [])), _expected_contexts(action)),
        )
        for field, actual, expected in checks:
            if actual != expected:
                errors.append(f"{where}: {action_id} {field} is {actual!r}; the matrix says {expected!r}")

        if capability.get("auth_profile_id") not in profiles:
            errors.append(f"{where}: {action_id} references unknown auth profile {capability.get('auth_profile_id')!r}")

        policy_keys = capability.get("policy_keys") or []
        if not policy_keys:
            errors.append(f"{where}: {action_id} declares no policy_keys")
        errors.extend(
            f"{where}: {action_id} policy key {key!r} is outside integrations.{provider_id}."
            for key in policy_keys
            if not key.startswith(f"integrations.{provider_id}.")
        )

    return errors


def validate_all(*, design_root: Path = DEFAULT_DESIGN_ROOT, bundles_root: Path = DEFAULT_BUNDLES_ROOT) -> list[str]:
    """Validate every bundle-owned capability manifest against its matrix."""
    errors: list[str] = []
    for provider_id, _extension_path, manifest_path in discover_manifests(bundles_root):
        errors.extend(compare(provider_id, manifest_path, design_root / "matrices" / f"{provider_id}.json"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-root", type=Path, default=DEFAULT_DESIGN_ROOT)
    parser.add_argument("--bundles-root", type=Path, default=DEFAULT_BUNDLES_ROOT)
    args = parser.parse_args()

    manifests = discover_manifests(args.bundles_root)
    errors = validate_all(design_root=args.design_root, bundles_root=args.bundles_root)
    if errors:
        print("Capability manifest validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Capability manifests agree with their matrices ({len(manifests)} checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
