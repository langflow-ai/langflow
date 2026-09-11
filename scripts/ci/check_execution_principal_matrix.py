#!/usr/bin/env python3
"""Validate the endpoint-family execution-principal contract."""

from __future__ import annotations

import argparse
import ast
import json
from functools import cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX = REPO_ROOT / "scripts" / "ci" / "execution_principal_matrix.json"
AUTHZ_MATRIX = REPO_ROOT / "scripts" / "ci" / "authz_endpoint_matrix.json"
# The database connection resolver keeps its own copy of the share-permitting
# families, because scripts/ci is not shipped with langflow-base. Drift is
# asymmetric: a family the matrix tightens but the resolver keeps fails open.
SHARE_RESOLVER_SOURCE = REPO_ROOT / "src" / "backend" / "base" / "langflow" / "services" / "connection" / "service.py"
SHARE_FAMILIES_CONSTANT = "_SHARE_PERMITTING_FAMILIES"
SHARE_DEPENDENCY_PRINCIPAL = "actor_or_explicit_share"

REQUIRED_DIMENSIONS = frozenset(
    {
        "family",
        "authz_family",
        "source",
        "actor",
        "execution_principal",
        "dependency_principal",
        "tweaks",
        "revoke",
        "error_policy",
        "exception",
        "test_references",
    }
)
REQUIRED_FAMILIES = frozenset(
    {
        "interactive_chat",
        "legacy_public_chat",
        "v1_run",
        "webhook",
        "openai_responses",
        "legacy_mcp",
        "mcp_projects",
        "a2a",
        "voice",
        "deployments",
        "workflow_v2",
        "workflow_hitl_v2",
        "workflow_public_v2",
    }
)

VALID_DIMENSION_VALUES = {
    "actor": {
        "authenticated_user",
        "webhook_user",
        "project_auth_user",
        "flow_owner",
        "deployment_actor",
        "job_owner",
        "public_visitor",
    },
    "execution_principal": {"actor", "anonymous_public", "flow_owner", "deployment_owner", "job_owner"},
    "dependency_principal": {
        "actor",
        "actor_or_explicit_share",
        "anonymous_public",
        "flow_owner",
        "deployment_owner",
        "job_owner",
    },
    "tweaks": {"owner_only", "owner_or_writer", "forbidden", "server_generated"},
    "revoke": {"new_and_resume", "new_only", "resume_rechecks_actor", "provider_controlled"},
    "error_policy": {"owner_debug_delegated_sanitized", "sanitized", "provider_sanitized"},
}

BEHAVIOR_SPECIFIC_REFERENCE_TERMS = {
    "v1_run": ("v1_run",),
    "webhook": ("webhook", "tweak"),
}


@cache
def _test_functions(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return frozenset(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name.startswith("test_")
    )


def _validate_test_reference(raw: str) -> str | None:
    try:
        relative_path, function_name = raw.split("::", 1)
    except ValueError:
        return f"invalid test reference {raw!r}; expected repo/path.py::test_function"
    path = REPO_ROOT / relative_path
    if not path.is_file():
        return f"stale test reference {raw!r}: file does not exist"
    if function_name not in _test_functions(path):
        return f"stale test reference {raw!r}: function does not exist"
    return None


def _authz_families() -> set[str]:
    matrix = json.loads(AUTHZ_MATRIX.read_text(encoding="utf-8"))
    return {contract["family"] for contract in matrix.get("contracts", []) if "family" in contract}


def _display_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)


def resolver_share_families(source: Path = SHARE_RESOLVER_SOURCE) -> frozenset[str]:
    """Read the resolver's literal share-family set without importing langflow."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    value = next(
        (
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == SHARE_FAMILIES_CONSTANT for target in node.targets)
        ),
        None,
    )
    # frozenset({...}) is the only call accepted; anything computed cannot be checked.
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "frozenset":
        value = value.args[0] if len(value.args) == 1 and not value.keywords else None
    try:
        families = ast.literal_eval(value) if value is not None else None
    except (TypeError, ValueError):
        families = None
    if not isinstance(families, set) or not all(isinstance(item, str) for item in families):
        msg = f"{SHARE_FAMILIES_CONSTANT} must be a module-level frozenset literal of family names"
        raise ValueError(msg)
    return frozenset(families)


def _validate_share_families(entrypoints: list[dict], resolver_source: Path) -> list[str]:
    try:
        resolver = resolver_share_families(resolver_source)
    except (OSError, SyntaxError, ValueError) as exc:
        return [f"could not read {SHARE_FAMILIES_CONSTANT} from {_display_path(resolver_source)}: {exc}"]
    matrix = {
        entrypoint["family"]
        for entrypoint in entrypoints
        if entrypoint.get("dependency_principal") == SHARE_DEPENDENCY_PRINCIPAL and "family" in entrypoint
    }
    errors: list[str] = []
    if fails_open := sorted(resolver - matrix):
        errors.append(
            f"{_display_path(resolver_source)} {SHARE_FAMILIES_CONSTANT} resolves shared connections for "
            f"{fails_open}, which the matrix does not mark {SHARE_DEPENDENCY_PRINCIPAL}; this fails open"
        )
    if fails_closed := sorted(matrix - resolver):
        errors.append(
            f"matrix marks {fails_closed} {SHARE_DEPENDENCY_PRINCIPAL}, but {_display_path(resolver_source)} "
            f"{SHARE_FAMILIES_CONSTANT} omits them, so their shared connections never resolve"
        )
    return errors


def validate_matrix(matrix_path: Path = DEFAULT_MATRIX, resolver_source: Path = SHARE_RESOLVER_SOURCE) -> list[str]:
    """Return reader-friendly contract errors; an empty list means complete."""
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"could not read execution-principal matrix {matrix_path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"execution-principal matrix {matrix_path} is not valid JSON: {exc}"]
    errors: list[str] = []
    if matrix.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    try:
        authz_families = _authz_families()
    except OSError as exc:
        return [f"could not read authorization matrix {AUTHZ_MATRIX}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"authorization matrix {AUTHZ_MATRIX} is not valid JSON: {exc}"]
    seen: set[str] = set()
    for entrypoint in matrix.get("entrypoints", []):
        family = entrypoint.get("family", "<unnamed>")
        missing = REQUIRED_DIMENSIONS - set(entrypoint)
        if missing:
            errors.append(f"entrypoint {family!r} is missing {sorted(missing)}")
            continue
        if family in seen:
            errors.append(f"duplicate entrypoint family {family!r}")
        seen.add(family)

        authz_family = entrypoint["authz_family"]
        if authz_family not in authz_families:
            errors.append(f"entrypoint {family!r} references unknown authz_family {authz_family!r}")

        source = REPO_ROOT / entrypoint["source"]
        if not source.is_file():
            errors.append(f"entrypoint {family!r} has stale source {entrypoint['source']!r}")

        for dimension, valid_values in VALID_DIMENSION_VALUES.items():
            value = entrypoint[dimension]
            if value not in valid_values:
                errors.append(f"entrypoint {family!r} has unknown {dimension} {value!r}")

        if not isinstance(entrypoint["exception"], str) or not entrypoint["exception"].strip():
            errors.append(f"entrypoint {family!r} must document its exception status")
        if not entrypoint["test_references"]:
            errors.append(f"entrypoint {family!r} test_references must not be empty")
        errors.extend(
            f"entrypoint {family!r}: {error}"
            for reference in entrypoint["test_references"]
            if (error := _validate_test_reference(reference))
        )
        required_terms = BEHAVIOR_SPECIFIC_REFERENCE_TERMS.get(family)
        if required_terms and not any(
            all(term in reference.rsplit("::", 1)[-1].lower() for term in required_terms)
            for reference in entrypoint["test_references"]
        ):
            errors.append(
                f"entrypoint {family!r} needs a behavior-specific test reference containing {required_terms!r}"
            )

    missing_families = REQUIRED_FAMILIES - seen
    unexpected_families = seen - REQUIRED_FAMILIES
    if missing_families:
        errors.append(f"matrix is missing required families {sorted(missing_families)}")
    if unexpected_families:
        errors.append(f"matrix has unclassified families {sorted(unexpected_families)}")
    errors.extend(_validate_share_families(matrix.get("entrypoints", []), resolver_source))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()
    errors = validate_matrix(args.matrix)
    if errors:
        print("Execution-principal endpoint matrix validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Execution-principal endpoint matrix is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
