#!/usr/bin/env python3
"""Validate the Dedicated Integrations wave-1 capability matrices.

The matrices under ``design/dedicated-integrations/matrices/`` are the INT-1
discovery-gate contract: at most eight included actions per provider, every
scope classified and sourced, every restricted scope decided, and every
substrate choice recorded in a decision record. ``--require-accepted`` is the
gate-close mode: every referenced decision record must carry
``Status: accepted`` and every declared owner must have a completed signature.

Every matrix is first validated against ``schema/capability_matrix.schema.json``
(Draft 2020-12, via ``jsonschema``), then the gate rules that a schema cannot
express are applied. Every scope on an included action carries a ``role``
(``required``, ``optional``, or ``alternative``) so the manifest's
``required_scopes`` and conditional scope requirements can be lifted
mechanically, and at least one scope is required. ``--require-accepted`` walks every record under
``decisions/`` (``TEMPLATE.md`` aside), not only the ones a matrix references.

Sign-off coverage is checked alongside the matrices: every record under the
design directory that declares ``Owners (sign-off roles):`` must be listed in
the README sign-off table under each of those roles, and its own ``## Sign-off``
table must carry a row per declared role.

``--design-root`` points the same decision-record and sign-off validation at
another discovery gate. A design root that publishes
``schema/event_transport.schema.json`` is a triggers gate
(``design/dedicated-integrations-triggers``): its ``matrices/`` hold
event-transport matrices rather than capability matrices, and
``event_transport_matrix`` supplies their rules. Without the flag the checker
behaves exactly as it did for INT-1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# scripts/ci is a package-less directory of scripts, so the sibling module is imported by
# name. That works when the file is run directly (sys.path[0] is scripts/ci) but not under
# ``python -m scripts.ci.check_capability_matrices``, so put the directory on the path first.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from event_transport_matrix import SCHEMA_NAME as EVENT_TRANSPORT_SCHEMA_NAME
from event_transport_matrix import validate_event_transport_matrices

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    Draft202012Validator = None  # type: ignore[assignment,misc]

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_ROOT = REPO_ROOT / "design" / "dedicated-integrations"
TRIGGERS_DESIGN_ROOT = REPO_ROOT / "design" / "dedicated-integrations-triggers"
DEFAULT_MATRIX_DIR = DESIGN_ROOT / "matrices"
SCHEMA_PATH = DESIGN_ROOT / "schema" / "capability_matrix.schema.json"

REQUIRED_PROVIDERS = frozenset({"google", "microsoft", "slack"})
DEFAULT_MAX_INCLUDED = 8
DEPLOYMENT_CONTEXTS = frozenset({"hosted", "self_managed", "desktop", "headless"})

ACTION_ID_RE = re.compile(r"^(google|microsoft|slack)\.[a-z0-9_]+\.[a-z0-9_]+$")
COMPONENT_CLASS_RE = re.compile(r"^[A-Z][A-Za-z0-9]+Component$")
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STATUS_RE = re.compile(r"^Status:\s*(draft|proposed|accepted|superseded)\b", re.MULTILINE)
DECISION_HEADING_RE = re.compile(r"^## Decision\s*$", re.MULTILINE)
OWNERS_RE = re.compile(r"^Owners \(sign-off roles\):\s*(.+?)\s*$", re.MULTILINE)
SIGN_OFF_HEADING = "## Sign-off"
ROLE_RE = re.compile(r"^[A-Za-z][A-Za-z-]* owner$")
SIGNATURE_FIELD_COUNT = 3
MIN_SIGN_OFF_ROW_CELLS = 4
# The release owner's acceptance is the Status line itself; the README row for that role says "every record".
ROLES_COVERING_EVERY_RECORD = frozenset({"release owner"})
# Files that carry an Owners line but are not sign-off records themselves.
SIGN_OFF_EXEMPT_FILES = frozenset({"README.md", "TEMPLATE.md"})

VALID_VALUES: dict[str, frozenset[str]] = {
    "provider": REQUIRED_PROVIDERS,
    "decision": frozenset({"include", "exclude", "defer"}),
    "confidence": frozenset({"high", "medium", "low"}),
    "substrate": frozenset({"sdk", "rest", "mcp"}),
    "substrate_ga_status": frozenset({"ga", "preview", "developer_preview", "beta", "deprecated"}),
    "identity": frozenset({"user_delegated", "bot", "service"}),
    "auth_mode": frozenset(
        {
            "oauth2_authorization_code",
            "oauth2_client_credentials",
            "oauth2_device_code",
            "service_account",
            "service_account_domain_wide_delegation",
            "bot_token_install",
            "api_key",
        }
    ),
    "classification": frozenset({"non_sensitive", "sensitive", "restricted"}),
    "scope_role": frozenset({"required", "optional", "alternative"}),
    "consent": frozenset({"user", "admin", "both"}),
    "callback": frozenset(
        {"server_redirect", "loopback_redirect", "device_code", "app_install_redirect", "manual_token", "none"}
    ),
    "restricted_scope_decision": frozenset({"avoid", "accept_with_casa", "accept_exempt", "defer"}),
    "oauth_app_owner": frozenset({"langflow", "customer", "either"}),
    "oauth_client_type": frozenset({"confidential", "public", "external"}),
    "scope_condition_kind": frozenset({"input_present", "input_truthy"}),
    "source_kind": frozenset({"provider_docs", "provider_changelog", "provider_console", "mcp_tools_list"}),
}

REQUIRED_TOP_LEVEL = frozenset(
    {
        "schema_version",
        "provider",
        "display_name",
        "bundle",
        "wave",
        "max_included_actions",
        "verified_on",
        "oauth_app_owner_by_context",
        "oauth_client_type_by_context",
        "substrate_decision",
        "restricted_scope_decisions",
        "sources",
        "verification_programs",
        "actions",
    }
)
REQUIRED_ACTION_FIELDS = frozenset(
    {
        "action_id",
        "display_name",
        "component_class",
        "decision",
        "rationale",
        "confidence",
        "identity",
        "auth_mode",
        "substrate",
        "substrate_ga_status",
        "deployment_contexts",
        "scopes",
    }
)
# An included action must be fully documented; excluded and deferred candidates only need the identity fields.
REQUIRED_INCLUDE_FIELDS = frozenset(
    {
        "schema",
        "consent",
        "consent_source",
        "reach",
        "refresh",
        "revocation",
        "substrate_source",
        "rate_limit",
        "verification_dependencies",
    }
)
CONDITIONAL_SCOPE_ROLES = frozenset({"optional", "alternative"})
SOURCED_BLOCKS = ("schema", "reach", "refresh", "revocation", "rate_limit")
SOURCED_SCALARS = ("consent_source", "substrate_source")


def _parse_date(raw: Any) -> date | None:
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _check_date(raw: Any, label: str, errors: list[str]) -> None:
    parsed = _parse_date(raw)
    if parsed is None:
        errors.append(f"{label} must be an ISO date (YYYY-MM-DD), got {raw!r}")
    elif parsed > datetime.now(tz=UTC).date():
        errors.append(f"{label} {raw!r} is in the future")


def _check_enum(value: Any, dimension: str, label: str, errors: list[str]) -> None:
    if value not in VALID_VALUES[dimension]:
        errors.append(f"{label} has unknown {dimension} {value!r}")


def _check_source_ref(source_id: Any, sources: dict[str, Any], label: str, errors: list[str]) -> None:
    if not isinstance(source_id, str) or source_id not in sources:
        errors.append(f"{label} references unknown source {source_id!r}")


def _schema_errors(matrix: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> list[str]:
    """Validate the matrix against the published JSON Schema; a missing validator is an error, not a skip."""
    if Draft202012Validator is None:
        return ["jsonschema is not installed; install it (the CI Scripts Tests workflow does) to validate matrices"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"could not load schema {schema_path}: {exc}"]
    found = sorted(Draft202012Validator(schema).iter_errors(matrix), key=lambda error: list(map(str, error.path)))
    return [f"schema: {'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}" for error in found]


def _validate_sources(matrix: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    sources = matrix.get("sources")
    if not isinstance(sources, dict) or not sources:
        errors.append("sources must be a non-empty object keyed by source id")
        return {}
    for source_id, source in sources.items():
        label = f"source {source_id!r}"
        if not SOURCE_ID_RE.match(source_id):
            errors.append(f"{label} id must be kebab-case")
        if not isinstance(source, dict):
            errors.append(f"{label} must be an object")
            continue
        errors.extend(
            f"{label} is missing {key!r}" for key in ("url", "title", "kind", "verified_on") if key not in source
        )
        url = source.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            errors.append(f"{label} url must start with https://")
        if "kind" in source:
            _check_enum(source["kind"], "source_kind", label, errors)
        if "verified_on" in source:
            _check_date(source["verified_on"], f"{label} verified_on", errors)
    return sources


def _validate_verification_programs(matrix: dict[str, Any], sources: dict[str, Any], errors: list[str]) -> set[str]:
    programs = matrix.get("verification_programs")
    if not isinstance(programs, dict):
        errors.append("verification_programs must be an object keyed by program id")
        return set()
    for program_id, program in programs.items():
        label = f"verification program {program_id!r}"
        if not isinstance(program, dict):
            errors.append(f"{label} must be an object")
            continue
        if not str(program.get("description", "")).strip():
            errors.append(f"{label} needs a description")
        _check_source_ref(program.get("source"), sources, label, errors)
        contexts = program.get("blocking_for_contexts", [])
        if not isinstance(contexts, list) or not set(contexts) <= DEPLOYMENT_CONTEXTS:
            errors.append(f"{label} blocking_for_contexts must be a list drawn from {sorted(DEPLOYMENT_CONTEXTS)}")
    return set(programs)


def _decision_record_errors(record: Any, design_root: Path, label: str, *, require_accepted: bool) -> list[str]:
    if not isinstance(record, str) or not record:
        return [f"{label} must name a decision record path relative to design/dedicated-integrations"]
    path = design_root / record
    if not path.is_file():
        return [f"{label} decision record {record!r} does not exist"]
    text = path.read_text(encoding="utf-8")
    status = STATUS_RE.search(text)
    errors: list[str] = []
    if status is None:
        errors.append(f"{label} decision record {record!r} lacks a 'Status: draft|proposed|accepted|superseded' line")
    elif require_accepted and status.group(1) != "accepted":
        errors.append(f"{label} decision record {record!r} is {status.group(1)}, not accepted")
    if DECISION_HEADING_RE.search(text) is None:
        errors.append(f"{label} decision record {record!r} lacks a '## Decision' heading")
    return errors


def _validate_top_level(matrix: dict[str, Any], stem: str, errors: list[str]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(matrix)
    if missing:
        errors.append(f"matrix is missing top-level fields {sorted(missing)}")
    if matrix.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    provider = matrix.get("provider")
    _check_enum(provider, "provider", "matrix", errors)
    if provider != stem:
        errors.append(f"provider {provider!r} does not match file name {stem!r}")
    bundle = matrix.get("bundle", {})
    if not isinstance(bundle, dict) or not {"extension_id", "bundle_name", "distribution"} <= set(bundle):
        errors.append("bundle must declare extension_id, bundle_name, and distribution")
    if matrix.get("wave") != 1:
        errors.append("wave must be 1 for this gate")
    max_included = matrix.get("max_included_actions")
    if not isinstance(max_included, int) or not 0 < max_included <= DEFAULT_MAX_INCLUDED:
        errors.append(f"max_included_actions must be an integer between 1 and {DEFAULT_MAX_INCLUDED}")
    _check_date(matrix.get("verified_on"), "verified_on", errors)
    owners = matrix.get("oauth_app_owner_by_context")
    if not isinstance(owners, dict) or set(owners) != DEPLOYMENT_CONTEXTS:
        errors.append(f"oauth_app_owner_by_context must cover exactly {sorted(DEPLOYMENT_CONTEXTS)}")
    else:
        for context, owner in owners.items():
            _check_enum(owner, "oauth_app_owner", f"oauth_app_owner_by_context.{context}", errors)
    client_types = matrix.get("oauth_client_type_by_context")
    if not isinstance(client_types, dict) or set(client_types) != DEPLOYMENT_CONTEXTS:
        errors.append(f"oauth_client_type_by_context must cover exactly {sorted(DEPLOYMENT_CONTEXTS)}")
    else:
        for context, client_type in client_types.items():
            _check_enum(
                client_type,
                "oauth_client_type",
                f"oauth_client_type_by_context.{context}",
                errors,
            )


def _validate_substrate_decision(
    matrix: dict[str, Any], design_root: Path, errors: list[str], *, require_accepted: bool
) -> set[str]:
    decision = matrix.get("substrate_decision")
    if not isinstance(decision, dict):
        errors.append("substrate_decision must be an object with chosen[] and decision_record")
        return set()
    chosen = decision.get("chosen")
    if not isinstance(chosen, list) or not chosen:
        errors.append("substrate_decision.chosen must be a non-empty list")
        chosen = []
    for substrate in chosen:
        _check_enum(substrate, "substrate", "substrate_decision.chosen", errors)
    errors.extend(
        _decision_record_errors(
            decision.get("decision_record"), design_root, "substrate_decision", require_accepted=require_accepted
        )
    )
    return set(chosen)


def _validate_restricted_decisions(
    matrix: dict[str, Any], design_root: Path, errors: list[str], *, require_accepted: bool
) -> dict[str, str]:
    entries = matrix.get("restricted_scope_decisions")
    if not isinstance(entries, list):
        errors.append("restricted_scope_decisions must be a list")
        return {}
    decisions: dict[str, str] = {}
    for entry in entries:
        scope = entry.get("scope") if isinstance(entry, dict) else None
        label = f"restricted scope decision for {scope!r}"
        if not isinstance(entry, dict) or not isinstance(scope, str) or not scope:
            errors.append("every restricted_scope_decisions entry needs a scope")
            continue
        if scope in decisions:
            errors.append(f"{label} is declared more than once")
        _check_enum(entry.get("decision"), "restricted_scope_decision", label, errors)
        if not str(entry.get("rationale", "")).strip():
            errors.append(f"{label} needs a written rationale")
        errors.extend(
            _decision_record_errors(entry.get("decision_record"), design_root, label, require_accepted=require_accepted)
        )
        decisions[scope] = str(entry.get("decision"))
    return decisions


def _check_scope_role(
    scope: dict[str, Any],
    scope_label: str,
    *,
    included: bool,
    input_names: set[str],
    errors: list[str],
) -> str | None:
    """Enforce the role grammar: included actions tag every scope; conditional roles say when they apply."""
    role = scope.get("role")
    if role is None:
        if included:
            errors.append(
                f"{scope_label} must declare a role (required, optional, or alternative) on an included action"
            )
        return None
    _check_enum(role, "scope_role", scope_label, errors)
    condition = scope.get("condition")
    if role in CONDITIONAL_SCOPE_ROLES and not isinstance(condition, dict):
        errors.append(f"{scope_label} is {role} and must state the condition under which it is requested")
    elif role == "required" and condition is not None:
        errors.append(f"{scope_label} is required and must not carry a condition; make it optional or alternative")
    elif isinstance(condition, dict):
        kind = condition.get("kind")
        if kind in {"input_present", "input_truthy"} and condition.get("input") not in input_names:
            errors.append(f"{scope_label} condition references unknown action input {condition.get('input')!r}")
    return str(role)


def _validate_scopes(
    action: dict[str, Any], sources: dict[str, Any], label: str, errors: list[str], *, included: bool
) -> list[str]:
    scopes = action.get("scopes")
    if not isinstance(scopes, list):
        errors.append(f"{label} scopes must be a list")
        return []
    restricted: list[str] = []
    roles: list[str | None] = []
    schema = action.get("schema")
    inputs = schema.get("inputs", []) if isinstance(schema, dict) else []
    input_names = {field["name"] for field in inputs if isinstance(field, dict) and isinstance(field.get("name"), str)}
    for scope in scopes:
        if not isinstance(scope, dict) or not isinstance(scope.get("scope"), str) or not scope["scope"]:
            errors.append(f"{label} has a scope entry without a scope string")
            continue
        scope_label = f"{label} scope {scope['scope']!r}"
        if "classification" not in scope:
            errors.append(f"{scope_label} is not classified")
        else:
            _check_enum(scope["classification"], "classification", scope_label, errors)
            if scope["classification"] == "restricted":
                restricted.append(scope["scope"])
        if not str(scope.get("provider_classification", "")).strip():
            errors.append(f"{scope_label} must record the provider's own classification term")
        _check_source_ref(scope.get("source"), sources, scope_label, errors)
        roles.append(
            _check_scope_role(
                scope,
                scope_label,
                included=included,
                input_names=input_names,
                errors=errors,
            )
        )
    if included and "required" not in roles:
        errors.append(f"{label} is included but declares no required scope")
    return restricted


def _validate_sourced_claims(
    action: dict[str, Any], sources: dict[str, Any], programs: set[str], label: str, errors: list[str]
) -> None:
    for block in SOURCED_BLOCKS:
        if block not in action:
            continue
        value = action[block]
        if not isinstance(value, dict):
            errors.append(f"{label} {block} must be an object carrying a source")
            continue
        _check_source_ref(value.get("source"), sources, f"{label} {block}", errors)
        if block == "rate_limit" and "confidence" in value:
            _check_enum(value["confidence"], "confidence", f"{label} rate_limit", errors)
    for scalar in SOURCED_SCALARS:
        if scalar in action:
            _check_source_ref(action[scalar], sources, f"{label} {scalar}", errors)
    errors.extend(
        f"{label} references unknown verification program {program_id!r}"
        for program_id in action.get("verification_dependencies", [])
        if program_id not in programs
    )


def _validate_action(
    action: dict[str, Any],
    *,
    provider: str,
    sources: dict[str, Any],
    programs: set[str],
    chosen_substrates: set[str],
    restricted_decisions: dict[str, str],
    errors: list[str],
) -> None:
    action_id = action.get("action_id", "<unnamed>")
    label = f"{provider}:{action_id}"
    missing = REQUIRED_ACTION_FIELDS - set(action)
    if missing:
        errors.append(f"{label} is missing {sorted(missing)}")
        return
    if not ACTION_ID_RE.match(str(action_id)) or not str(action_id).startswith(f"{provider}."):
        errors.append(f"{label} action_id must look like '{provider}.<product>.<verb>'")
    if not COMPONENT_CLASS_RE.match(str(action["component_class"])):
        errors.append(f"{label} component_class must be a *Component class name")
    for dimension in ("decision", "confidence", "identity", "auth_mode", "substrate", "substrate_ga_status"):
        _check_enum(action[dimension], dimension, label, errors)
    if not str(action["rationale"]).strip():
        errors.append(f"{label} needs a rationale")

    contexts = action["deployment_contexts"]
    if not isinstance(contexts, dict) or not contexts or not set(contexts) <= DEPLOYMENT_CONTEXTS:
        errors.append(f"{label} deployment_contexts must be a non-empty map drawn from {sorted(DEPLOYMENT_CONTEXTS)}")
    else:
        for context, callback in contexts.items():
            _check_enum(callback, "callback", f"{label} deployment_contexts.{context}", errors)

    decision = action["decision"]
    if decision == "include":
        missing_include = REQUIRED_INCLUDE_FIELDS - set(action)
        if missing_include:
            errors.append(f"{label} is included but missing {sorted(missing_include)}")
        if action["substrate"] not in chosen_substrates:
            errors.append(f"{label} uses substrate {action['substrate']!r} outside substrate_decision.chosen")
    if "consent" in action:
        _check_enum(action["consent"], "consent", label, errors)
    if action["substrate"] == "mcp" and action["substrate_ga_status"] != "ga" and action["confidence"] == "high":
        errors.append(f"{label} cannot be high confidence on a non-GA MCP substrate")
    if action["confidence"] == "low" and not action.get("open_questions"):
        errors.append(f"{label} is low confidence and must list open_questions")

    restricted = _validate_scopes(action, sources, label, errors, included=decision == "include")
    if decision in {"include", "defer"}:
        for scope in restricted:
            if scope not in restricted_decisions:
                errors.append(f"{label} carries restricted scope {scope!r} with no restricted_scope_decisions entry")
            elif decision == "include" and restricted_decisions[scope] in {"avoid", "defer"}:
                errors.append(
                    f"{label} is included but its restricted scope {scope!r} is decided "
                    f"{restricted_decisions[scope]!r}; that is a contradiction"
                )
    _validate_sourced_claims(action, sources, programs, label, errors)


def validate_matrix(matrix_path: Path, *, require_accepted: bool = False) -> list[str]:
    """Return reader-friendly contract errors for one provider matrix; an empty list means complete."""
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"could not read capability matrix {matrix_path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"capability matrix {matrix_path} is not valid JSON: {exc}"]
    if not isinstance(matrix, dict):
        return [f"capability matrix {matrix_path} must be a JSON object"]

    design_root = matrix_path.resolve().parent.parent
    errors: list[str] = _schema_errors(matrix)
    _validate_top_level(matrix, matrix_path.stem, errors)
    sources = _validate_sources(matrix, errors)
    programs = _validate_verification_programs(matrix, sources, errors)
    chosen = _validate_substrate_decision(matrix, design_root, errors, require_accepted=require_accepted)
    restricted_decisions = _validate_restricted_decisions(
        matrix, design_root, errors, require_accepted=require_accepted
    )

    actions = matrix.get("actions")
    if not isinstance(actions, list) or not actions:
        errors.append("actions must be a non-empty list")
        return errors
    provider = str(matrix.get("provider"))
    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            errors.append(f"{provider}: every action must be an object")
            continue
        action_id = action.get("action_id")
        if action_id in seen:
            errors.append(f"{provider}:{action_id} is declared more than once")
        seen.add(action_id)
        _validate_action(
            action,
            provider=provider,
            sources=sources,
            programs=programs,
            chosen_substrates=chosen,
            restricted_decisions=restricted_decisions,
            errors=errors,
        )

    included = sum(1 for action in actions if isinstance(action, dict) and action.get("decision") == "include")
    max_included = matrix.get("max_included_actions")
    if isinstance(max_included, int) and included > max_included:
        errors.append(f"{provider} includes {included} actions, exceeding max_included_actions={max_included}")
    return errors


def validate_decision_records(design_root: Path = DESIGN_ROOT, *, require_accepted: bool = False) -> list[str]:
    """Walk every record under decisions/ (TEMPLATE.md aside); gate close requires each one to be accepted."""
    decisions_dir = design_root / "decisions"
    if not decisions_dir.is_dir():
        return [f"decision records directory {decisions_dir} does not exist"]
    errors: list[str] = []
    for record in sorted(decisions_dir.glob("*.md")):
        if record.name in SIGN_OFF_EXEMPT_FILES:
            continue
        relative = record.relative_to(design_root).as_posix()
        errors.extend(_decision_record_errors(relative, design_root, "gate", require_accepted=require_accepted))
    return errors


def _table_rows(section: str) -> list[list[str]]:
    """Return the cells of every pipe-table body row in a Markdown section (header and rule rows dropped)."""
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or re.match(r"^\|\s*-", stripped):
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows[1:]


def _sign_off_section(text: str) -> str | None:
    if SIGN_OFF_HEADING not in text:
        return None
    return text.split(SIGN_OFF_HEADING, 1)[1].split("\n## ", 1)[0]


def _readme_sign_off_rows(design_root: Path, errors: list[str]) -> dict[str, list[str]]:
    readme = design_root / "README.md"
    if not readme.is_file():
        errors.append(f"sign-off: {readme} does not exist")
        return {}
    section = _sign_off_section(readme.read_text(encoding="utf-8"))
    if section is None:
        errors.append("sign-off: README.md lacks a '## Sign-off' table")
        return {}
    return {row[0]: row for row in _table_rows(section) if len(row) > 1}


def _declared_roles(text: str, label: str, errors: list[str]) -> list[str]:
    match = OWNERS_RE.search(text)
    if match is None:
        errors.append(f"sign-off: {label} lacks an 'Owners (sign-off roles):' line")
        return []
    roles = [role.strip() for role in match.group(1).split(",") if role.strip()]
    errors.extend(f"sign-off: {label} declares malformed role {role!r}" for role in roles if not ROLE_RE.match(role))
    return roles


def _validate_completed_signature(row: list[str], label: str, errors: list[str]) -> None:
    """Require non-empty Name, Date, and PR cells after the role or record-list columns."""
    signature = row[-SIGNATURE_FIELD_COUNT:] if len(row) >= MIN_SIGN_OFF_ROW_CELLS else []
    if len(signature) != SIGNATURE_FIELD_COUNT or any(not cell.strip() for cell in signature):
        errors.append(f"sign-off: {label} must complete Name, Date, and PR")
        return
    _check_date(signature[1], f"sign-off: {label} Date", errors)


def validate_sign_offs(design_root: Path = DESIGN_ROOT, *, require_complete: bool = False) -> list[str]:
    """Require every owner role to be tracked; gate close also requires completed signatures."""
    errors: list[str] = []
    readme_rows = _readme_sign_off_rows(design_root, errors)
    if errors:
        # Without the README table every declared role would fail; one error says what is actually missing.
        return errors
    records = sorted(path for path in design_root.rglob("*.md") if path.name not in SIGN_OFF_EXEMPT_FILES)
    for record in records:
        label = record.relative_to(design_root).as_posix()
        text = record.read_text(encoding="utf-8")
        roles = _declared_roles(text, label, errors)
        for role in roles:
            if role in ROLES_COVERING_EVERY_RECORD:
                if role not in readme_rows:
                    errors.append(f"sign-off: README.md table has no row for {role!r}")
                continue
            row = readme_rows.get(role)
            if row is None:
                errors.append(f"sign-off: README.md table has no row for {role!r}, declared by {label}")
            elif f"`{label}`" not in row[1]:
                errors.append(f"sign-off: README.md row for {role!r} does not list `{label}`")
        section = _sign_off_section(text)
        if section is None:
            if set(roles) - ROLES_COVERING_EVERY_RECORD:
                errors.append(f"sign-off: {label} declares {sorted(roles)} but has no '{SIGN_OFF_HEADING}' table")
            continue
        table_rows = {row[0]: row for row in _table_rows(section) if row}
        table_roles = set(table_rows)
        errors.extend(f"sign-off: {label} table lacks a row for {role!r}" for role in roles if role not in table_roles)
        errors.extend(
            f"sign-off: {label} table row {role!r} is not a declared owner" for role in sorted(table_roles - set(roles))
        )
        if require_complete:
            for role in roles:
                row = table_rows.get(role)
                if row is not None:
                    _validate_completed_signature(row, f"{label} row {role!r}", errors)
    if require_complete:
        for role, row in readme_rows.items():
            _validate_completed_signature(row, f"README.md row {role!r}", errors)
    return errors


def is_event_transport_root(design_root: Path) -> bool:
    """A design root that publishes an event-transport schema is a triggers gate, not a capability gate."""
    return (design_root / "schema" / EVENT_TRANSPORT_SCHEMA_NAME).is_file()


def validate_all(
    matrix_dir: Path = DEFAULT_MATRIX_DIR,
    *,
    require_accepted: bool = False,
    design_root: Path | None = None,
) -> list[str]:
    """Validate every provider matrix and require one file per wave-1 provider."""
    root = design_root if design_root is not None else matrix_dir.resolve().parent
    if is_event_transport_root(root):
        errors = validate_event_transport_matrices(
            matrix_dir,
            design_root=root,
            record_errors=_decision_record_errors,
            require_accepted=require_accepted,
        )
        errors.extend(validate_decision_records(root, require_accepted=require_accepted))
        return errors

    errors: list[str] = []
    present = {path.stem for path in matrix_dir.glob("*.json")} if matrix_dir.is_dir() else set()
    missing = REQUIRED_PROVIDERS - present
    if missing:
        errors.append(f"missing capability matrices for {sorted(missing)} under {matrix_dir}")
    unexpected = present - REQUIRED_PROVIDERS
    if unexpected:
        errors.append(
            f"unexpected capability matrices {sorted(unexpected)}; wave 1 covers {sorted(REQUIRED_PROVIDERS)}"
        )
    for stem in sorted(present & REQUIRED_PROVIDERS):
        errors.extend(validate_matrix(matrix_dir / f"{stem}.json", require_accepted=require_accepted))
    errors.extend(validate_decision_records(matrix_dir.resolve().parent, require_accepted=require_accepted))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--design-root",
        type=Path,
        default=None,
        help=(
            "discovery-gate directory to validate (default design/dedicated-integrations); "
            "a root publishing schema/event_transport.schema.json is validated as a triggers gate"
        ),
    )
    parser.add_argument(
        "--matrix-dir",
        type=Path,
        default=None,
        help="matrix directory (default <design-root>/matrices)",
    )
    parser.add_argument(
        "--require-accepted",
        action="store_true",
        help="gate-close mode: every decision must be accepted and every declared owner signature complete",
    )
    args = parser.parse_args()
    if args.design_root is not None:
        design_root = args.design_root.resolve()
    elif args.matrix_dir is not None:
        design_root = args.matrix_dir.resolve().parent
    else:
        design_root = DESIGN_ROOT
    matrix_dir = args.matrix_dir if args.matrix_dir is not None else design_root / "matrices"

    label = "Event-transport" if is_event_transport_root(design_root) else "Capability"
    errors = validate_all(matrix_dir, require_accepted=args.require_accepted, design_root=design_root)
    errors.extend(validate_sign_offs(design_root, require_complete=args.require_accepted))
    if errors:
        print(f"{label} matrix validation failed for {design_root}:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"{label} matrices are complete for {design_root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
