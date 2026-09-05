"""Validate the triggers discovery-gate event-transport matrices.

The matrices under ``design/dedicated-integrations-triggers/matrices/`` are TRG-1
exit criterion 2: for every provider, every push and pull mechanism with its
ingress requirement, inbound authentication, subscription TTL and renewal,
payload shape, delivery guarantee, replay availability, rate limits, dedupe key,
and the deployment contexts it supports.

Every matrix is validated against ``schema/event_transport.schema.json``
(Draft 2020-12, via ``jsonschema``) and then against the three rules a schema
cannot express:

* **sourced claims** - every claim block on a wave-1 mechanism names a source id
  that resolves in ``sources``, and every source carries an https URL, a kind,
  and a non-future ``verified_on`` date;
* **the no-ingress rule per context** - a mechanism that needs public HTTPS may
  not claim a deployment context whose ``public_ingress_by_context`` entry is
  ``unavailable``, and a context marked ``conditional`` is only allowed when the
  mechanism names an ``outbound_only`` ``fallback_mechanism`` that also supports
  that context;
* **an outbound-only answer per provider** - every provider ships at least one
  wave-1 mechanism that needs no public ingress, so a self-managed instance
  behind a firewall has a documented answer (exit criterion 4).

This module is deliberately standalone: ``check_capability_matrices`` imports it
for the ``--design-root`` gate profile, so it must not import back.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    Draft202012Validator = None  # type: ignore[assignment,misc]

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIGGERS_DESIGN_ROOT = REPO_ROOT / "design" / "dedicated-integrations-triggers"
SCHEMA_NAME = "event_transport.schema.json"
MATRIX_SUFFIX = "-events"

REQUIRED_PROVIDERS = frozenset({"google", "microsoft", "slack"})
DEPLOYMENT_CONTEXTS = frozenset({"hosted", "self_managed", "desktop", "headless"})

MECHANISM_ID_RE = re.compile(r"^(google|microsoft|slack)\.[a-z0-9_]+$")
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DECISION_RECORD_RE = re.compile(r"^decisions/[a-z0-9-]+\.md$")

VALID_VALUES: dict[str, frozenset[str]] = {
    "provider": REQUIRED_PROVIDERS,
    "ingress_availability": frozenset({"available", "conditional", "unavailable"}),
    "source_kind": frozenset({"provider_docs", "provider_changelog", "provider_console"}),
    "track": frozenset({"a", "b"}),
    "transport": frozenset({"http_push", "persistent_socket", "pull_subscription", "poll"}),
    "ingress_requirement": frozenset({"public_https", "outbound_only"}),
    "inbound_auth_method": frozenset(
        {
            "hmac_signature",
            "validation_token",
            "channel_token",
            "oidc_token",
            "app_level_token",
            "oauth_access_token",
            "none",
        }
    ),
    "payload_shape": frozenset({"thin", "full"}),
    "delivery_guarantee": frozenset({"at_least_once", "at_most_once", "best_effort"}),
    "dedupe_stability": frozenset({"stable_across_retries", "per_delivery", "derived"}),
    "confidence": frozenset({"high", "medium", "low"}),
    "mechanism_status": frozenset({"wave_1", "deferred", "excluded"}),
    "deployment_context": DEPLOYMENT_CONTEXTS,
}

REQUIRED_TOP_LEVEL = frozenset(
    {
        "schema_version",
        "provider",
        "display_name",
        "wave",
        "verified_on",
        "public_ingress_by_context",
        "decision_records",
        "sources",
        "mechanisms",
    }
)
# A wave-1 mechanism is the contract TRG-3 through TRG-6 build against; deferred and excluded rows
# only need enough to say what was ruled out and why.
REQUIRED_WAVE_1_BLOCKS = ("inbound_auth", "subscription", "payload", "delivery", "replay", "rate_limit", "dedupe_key")
SOURCED_BLOCKS = (*REQUIRED_WAVE_1_BLOCKS, "session_key")


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


def _schema_errors(matrix: dict[str, Any], schema_path: Path) -> list[str]:
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


def _validate_top_level(matrix: dict[str, Any], stem: str, errors: list[str]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(matrix)
    if missing:
        errors.append(f"matrix is missing top-level fields {sorted(missing)}")
    if matrix.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if matrix.get("wave") != 1:
        errors.append("wave must be 1 for this gate")
    provider = matrix.get("provider")
    _check_enum(provider, "provider", "matrix", errors)
    expected_stem = f"{provider}{MATRIX_SUFFIX}"
    if expected_stem != stem:
        errors.append(f"provider {provider!r} does not match file name {stem!r}; expected {expected_stem!r}")
    _check_date(matrix.get("verified_on"), "verified_on", errors)
    ingress = matrix.get("public_ingress_by_context")
    if not isinstance(ingress, dict) or set(ingress) != DEPLOYMENT_CONTEXTS:
        errors.append(f"public_ingress_by_context must cover exactly {sorted(DEPLOYMENT_CONTEXTS)}")
    else:
        for context, availability in ingress.items():
            _check_enum(availability, "ingress_availability", f"public_ingress_by_context.{context}", errors)


def _validate_decision_records(
    matrix: dict[str, Any],
    design_root: Path,
    record_errors: Any,
    errors: list[str],
    *,
    require_accepted: bool,
) -> None:
    """Every matrix names the decision records that govern it; ``record_errors`` parses one record."""
    records = matrix.get("decision_records")
    if not isinstance(records, list) or not records:
        errors.append("decision_records must be a non-empty list of paths under the design root")
        return
    for record in records:
        if not isinstance(record, str) or not DECISION_RECORD_RE.match(record):
            errors.append(f"decision_records entry {record!r} must look like 'decisions/<name>.md'")
            continue
        errors.extend(record_errors(record, design_root, "matrix", require_accepted=require_accepted))


def _validate_sourced_claims(mechanism: dict[str, Any], sources: dict[str, Any], label: str, errors: list[str]) -> None:
    for block_name in SOURCED_BLOCKS:
        block = mechanism.get(block_name)
        if block is None:
            continue
        if not isinstance(block, dict):
            errors.append(f"{label} {block_name} must be an object")
            continue
        _check_source_ref(block.get("source"), sources, f"{label} {block_name}", errors)


def _validate_mechanism(
    mechanism: dict[str, Any],
    *,
    provider: str,
    sources: dict[str, Any],
    errors: list[str],
) -> None:
    mechanism_id = mechanism.get("mechanism_id")
    label = f"{provider}:{mechanism_id}"
    if not isinstance(mechanism_id, str) or not MECHANISM_ID_RE.match(mechanism_id):
        errors.append(f"{label} mechanism_id must look like '{provider}.<mechanism>'")
    elif not mechanism_id.startswith(f"{provider}."):
        errors.append(f"{label} mechanism_id must start with {provider!r}")

    for dimension in ("track", "transport", "ingress_requirement", "confidence"):
        if dimension in mechanism:
            _check_enum(mechanism[dimension], dimension, label, errors)
    if "status" in mechanism:
        _check_enum(mechanism["status"], "mechanism_status", label, errors)
    if not str(mechanism.get("rationale", "")).strip():
        errors.append(f"{label} needs a rationale")

    contexts = mechanism.get("deployment_contexts")
    if not isinstance(contexts, list) or not set(contexts) <= DEPLOYMENT_CONTEXTS:
        errors.append(f"{label} deployment_contexts must be a list drawn from {sorted(DEPLOYMENT_CONTEXTS)}")

    status = mechanism.get("status")
    if status == "wave_1":
        missing = [block for block in REQUIRED_WAVE_1_BLOCKS if block not in mechanism]
        if missing:
            errors.append(f"{label} is a wave-1 mechanism and is missing {missing}")
        if not contexts:
            errors.append(f"{label} is a wave-1 mechanism and must support at least one deployment context")
    elif status in {"deferred", "excluded"} and contexts:
        errors.append(f"{label} is {status} and must not claim deployment contexts")

    if mechanism.get("confidence") == "low" and not mechanism.get("open_questions"):
        errors.append(f"{label} is low confidence and must list open_questions")
    # The schema already rejects a non-object block; these rules still run on a matrix that
    # failed the schema, so read every nested block defensively - a malformed file must produce
    # gate errors, never a traceback out of the checker.
    for block_name, key, enum_name in (
        ("inbound_auth", "method", "inbound_auth_method"),
        ("payload", "shape", "payload_shape"),
        ("delivery", "guarantee", "delivery_guarantee"),
        ("dedupe_key", "stability", "dedupe_stability"),
    ):
        block = mechanism.get(block_name)
        # A non-object block is reported once, by _validate_sourced_claims; skip the enum
        # check rather than raising or reporting the same defect twice.
        if not isinstance(block, dict):
            continue
        _check_enum(block.get(key), enum_name, f"{label} {block_name}", errors)
    _validate_sourced_claims(mechanism, sources, label, errors)


def _validate_no_ingress_rule(matrix: dict[str, Any], errors: list[str]) -> None:
    """A push mechanism may not claim a context that cannot expose a public HTTPS URL.

    ``conditional`` contexts (self-managed instances, which may or may not have an ingress) are allowed
    only when the mechanism names an ``outbound_only`` fallback that covers the same context; that pair
    is the answer TRG-1 exit criterion 4 owes an Enterprise customer without public ingress.
    """
    ingress = matrix.get("public_ingress_by_context")
    mechanisms = matrix.get("mechanisms")
    if not isinstance(ingress, dict) or not isinstance(mechanisms, list):
        return
    # str() keys: a matrix that failed the schema can carry an unhashable mechanism_id, and this
    # rule must still report gate errors rather than raise out of the checker.
    by_id = {str(mechanism.get("mechanism_id")): mechanism for mechanism in mechanisms if isinstance(mechanism, dict)}
    outbound_wave_1 = [
        mechanism
        for mechanism in by_id.values()
        if mechanism.get("status") == "wave_1" and mechanism.get("ingress_requirement") == "outbound_only"
    ]
    if not outbound_wave_1:
        errors.append(
            "no wave-1 mechanism runs outbound-only; a self-managed instance without public ingress has no answer"
        )
    for mechanism in by_id.values():
        label = f"{matrix.get('provider')}:{mechanism.get('mechanism_id')}"
        if mechanism.get("ingress_requirement") != "public_https":
            continue
        contexts = mechanism.get("deployment_contexts")
        if not isinstance(contexts, list):
            continue
        fallback_id = mechanism.get("fallback_mechanism")
        fallback = by_id.get(fallback_id) if fallback_id is not None else None
        for context in contexts:
            availability = ingress.get(context)
            if availability == "unavailable":
                errors.append(
                    f"{label} needs public HTTPS but claims context {context!r}, "
                    f"where public_ingress_by_context says ingress is unavailable"
                )
            elif availability == "conditional":
                if fallback is None:
                    errors.append(
                        f"{label} needs public HTTPS and claims the conditional context {context!r} "
                        f"without naming a fallback_mechanism"
                    )
                elif fallback.get("ingress_requirement") != "outbound_only":
                    errors.append(
                        f"{label} fallback_mechanism {fallback_id!r} is not outbound-only, "
                        f"so it does not answer context {context!r}"
                    )
                elif context not in (fallback.get("deployment_contexts") or []):
                    errors.append(f"{label} fallback_mechanism {fallback_id!r} does not support context {context!r}")
        if fallback_id is not None and fallback is None:
            errors.append(f"{label} names unknown fallback_mechanism {fallback_id!r}")


def validate_event_transport_matrix(
    matrix_path: Path,
    *,
    schema_path: Path | None = None,
    design_root: Path | None = None,
    record_errors: Any = None,
    require_accepted: bool = False,
) -> list[str]:
    """Return reader-friendly gate errors for one provider's event-transport matrix."""
    try:
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return [f"could not read event-transport matrix {matrix_path}: {exc}"]
    except json.JSONDecodeError as exc:
        return [f"event-transport matrix {matrix_path} is not valid JSON: {exc}"]
    if not isinstance(matrix, dict):
        return [f"event-transport matrix {matrix_path} must be a JSON object"]

    root = design_root if design_root is not None else matrix_path.resolve().parent.parent
    schema = schema_path if schema_path is not None else root / "schema" / SCHEMA_NAME
    errors: list[str] = _schema_errors(matrix, schema)
    _validate_top_level(matrix, matrix_path.stem, errors)
    sources = _validate_sources(matrix, errors)
    if record_errors is not None:
        _validate_decision_records(matrix, root, record_errors, errors, require_accepted=require_accepted)

    mechanisms = matrix.get("mechanisms")
    if not isinstance(mechanisms, list) or not mechanisms:
        errors.append("mechanisms must be a non-empty list")
        return errors
    provider = str(matrix.get("provider"))
    seen: set[str] = set()
    for mechanism in mechanisms:
        if not isinstance(mechanism, dict):
            errors.append(f"{provider}: every mechanism must be an object")
            continue
        # str() rather than the raw value: a matrix that failed the schema can carry an
        # unhashable mechanism_id, and the duplicate check must not raise on it.
        mechanism_id = str(mechanism.get("mechanism_id"))
        if mechanism_id in seen:
            errors.append(f"{provider}:{mechanism_id} is declared more than once")
        seen.add(mechanism_id)
        _validate_mechanism(mechanism, provider=provider, sources=sources, errors=errors)
    _validate_no_ingress_rule(matrix, errors)
    return errors


def validate_event_transport_matrices(
    matrix_dir: Path,
    *,
    design_root: Path | None = None,
    record_errors: Any = None,
    require_accepted: bool = False,
) -> list[str]:
    """Validate every provider matrix and require one file per wave-1 provider."""
    errors: list[str] = []
    root = design_root if design_root is not None else matrix_dir.resolve().parent
    present = {path.stem for path in matrix_dir.glob(f"*{MATRIX_SUFFIX}.json")} if matrix_dir.is_dir() else set()
    providers = {stem.removesuffix(MATRIX_SUFFIX) for stem in present}
    missing = REQUIRED_PROVIDERS - providers
    if missing:
        errors.append(f"missing event-transport matrices for {sorted(missing)} under {matrix_dir}")
    unexpected = providers - REQUIRED_PROVIDERS
    if unexpected:
        errors.append(
            f"unexpected event-transport matrices {sorted(unexpected)}; wave 1 covers {sorted(REQUIRED_PROVIDERS)}"
        )
    stray = {path.name for path in matrix_dir.glob("*.json")} - {f"{stem}.json" for stem in present}
    if stray:
        errors.append(f"matrices must be named '<provider>{MATRIX_SUFFIX}.json'; found {sorted(stray)}")
    for provider in sorted(providers & REQUIRED_PROVIDERS):
        errors.extend(
            validate_event_transport_matrix(
                matrix_dir / f"{provider}{MATRIX_SUFFIX}.json",
                design_root=root,
                record_errors=record_errors,
                require_accepted=require_accepted,
            )
        )
    return errors
