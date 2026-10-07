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


def validate_matrix(matrix_path: Path = DEFAULT_MATRIX) -> list[str]:
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
