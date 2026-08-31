"""Shared flow validation helpers for custom component policy enforcement."""

from __future__ import annotations

import hashlib
from collections.abc import Container, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.utils.component_aliases import ComponentIdentityIndex, get_component_type_aliases

if TYPE_CHECKING:
    from lfx.services.catalog_policy import CatalogPolicySnapshot

INITIALIZING_COMPONENT_TEMPLATES_MESSAGE = (
    "Flow build blocked: component templates are still initializing. Please try again in a few seconds."
)
SETTINGS_SERVICE_REQUIRED_MESSAGE = "Settings service must be initialized before validating flows."
CATALOG_POLICY_IDENTITIES_UNAVAILABLE_MESSAGE = (
    "Catalog policy component identities are still initializing. Please try again in a few seconds."
)
PUBLIC_CATALOG_POLICY_UNAVAILABLE_MESSAGE = "This flow is temporarily unavailable. Please try again."

# Built-in components that execute user- or model-supplied Python from input fields or during
# runtime, rather than from the validated class ``code`` field. Their class-code hash is valid,
# so they pass the allow_custom_components policy, yet they are effectively code-authoring
# surfaces. Identifiers include class names plus their ``name``/``display_name`` aliases so the
# check matches whatever value the node carries in ``data.type``.
#
# This set is used by:
# - the opt-in ``block_code_interpreter_components`` authenticated-flow gate, and
# - the unauthenticated public-flow gate for ``/api/v1/build_public_tmp/{flow_id}/flow``, and
# - the shared component/tool runtime gate.
#
# Keeping these enforcement points on the same set prevents code-execution aliases from
# drifting between the multi-tenant hardening and public-build hardening paths.
CODE_EXECUTION_COMPONENT_TYPES: frozenset[str] = frozenset(
    {
        "CSVAgent",  # LangChain CSV agent can execute Python when allow_dangerous_code is enabled
        "CodeAct Agent (Smolagents)",
        "CodeActAgentSmolagents",  # smolagents CodeAgent executes model-generated code
        "Cuga",  # CUGA agent executes model-generated Python via its built-in executor
        "LambdaFilterComponent",
        "OpenDsStar Agent",
        "OpenDsStarAgent",  # OpenDsStar data-science agent executes model-generated Python
        "Python Code Structured",
        "PythonCodeStructuredTool",
        "Python Function",
        "PythonFunction",
        "PythonFunctionComponent",
        "Python Interpreter",
        "PythonREPLComponent",
        "Python REPL",
        "PythonREPLToolComponent",
        "PythonREPLTool",
        "Smart Transform",
    }
)


def is_code_execution_component(*identifiers: object) -> bool:
    """Return whether any component identifier is registered as code-executing."""
    return any(
        isinstance(identifier, str) and identifier in CODE_EXECUTION_COMPONENT_TYPES for identifier in identifiers
    )


class CustomComponentValidationError(ValueError):
    """Raised when a flow fails custom-component policy validation.

    Subclasses ValueError so existing ``except ValueError`` handlers
    still catch it, but callers can catch this specifically to
    distinguish policy errors from other ValueErrors.
    """


class CatalogPolicyValidationError(CustomComponentValidationError):
    """Raised when a flow contains a component blocked by catalog policy."""


class CatalogPolicyIdentityUnavailableError(RuntimeError):
    """Raised when an active catalog rule needs an identity index that is not ready."""


class PublicFlowValidationError(CustomComponentValidationError):
    """Raised when a public (unauthenticated) flow build is disallowed.

    Subclasses CustomComponentValidationError so the existing public-build
    handlers (which already map that error to a safe 400) catch it too.
    """


# Template field (input) names on CODE_EXECUTION_COMPONENT_TYPES nodes that carry
# executable code or define the code sandbox boundary. Most are plain-text inputs
# (StrInput / MultilineInput → template type "str"), so the field-type=="code" guard
# in apply_tweaks() does NOT catch them; function_code is also included by name as
# defense in depth for legacy or malformed templates. The Tweaks API must refuse to
# override these fields by name on a code-execution node. Kept beside
# CODE_EXECUTION_COMPONENT_TYPES so the two consumers stay in sync when a component
# has tweakable code/sandbox inputs. Components that execute runtime/model-generated
# code without such a template field still belong in CODE_EXECUTION_COMPONENT_TYPES,
# but do not need entries here. This sync is enforced by
# test_every_code_execution_type_has_registered_code_fields in test_process.py.
# The conventional "code" field name is blocked globally in apply_tweaks() and so
# is intentionally omitted here.
#   - python_code:        Python Interpreter (PythonREPLComponent) and Python REPL Tool exec input
#   - function_code:      Python Function (PythonFunctionComponent) exec input
#   - tool_code:          removed PythonCodeStructuredTool exec input (type retained)
#   - filter_instruction: Smart Transform instruction → LLM-generated, eval()'d lambda
#   - global_imports:     import allow-list that populates the exec() namespace; the
#                         documented sandbox boundary (powerful modules must be opted
#                         into here), so it must not be widened via tweaks
#   - allow_dangerous_code: CSVAgent switch that enables LangChain Python execution
CODE_EXECUTION_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "allow_dangerous_code",
        "function_code",
        "python_code",
        "tool_code",
        "filter_instruction",
        "global_imports",
    }
)

# Component inputs that cross a privileged sink boundary and therefore must retain
# the value stored by the flow author. SQLComponent uses these fields to select a
# database and execute SQL with the server's filesystem access and database
# credentials; allowing the Tweaks API to replace them would let a run caller
# repoint that authority without editing the flow. Other SQLComponent options
# remain tweakable.
PROTECTED_TWEAK_FIELDS_BY_COMPONENT: Mapping[str, frozenset[str]] = {
    "SQLComponent": frozenset({"database_url", "query"}),
}


def is_protected_tweak_field(component_type: str | None, field_name: str, field_type: str = "") -> bool:
    """Return whether a runtime tweak must preserve the flow author's value."""
    return (
        field_type == "code"
        or field_name == "code"
        or (component_type in CODE_EXECUTION_COMPONENT_TYPES and field_name in CODE_EXECUTION_FIELD_NAMES)
        or field_name in PROTECTED_TWEAK_FIELDS_BY_COMPONENT.get(component_type or "", ())
    )


# ---------------------------------------------------------------------------
# Deployment tweak policy
# ---------------------------------------------------------------------------
# Two lists with two owners. The deployment owns the floor above
# (``is_protected_tweak_field``), a denylist nothing can bypass. The flow author
# owns the allowlist below, the per-field ``api_editable`` flag. The policy
# setting only chooses which of the two is consulted; it never supplies list
# content itself, because an operator cannot anticipate every flow.

TWEAK_POLICY_PERMISSIVE = "permissive"
TWEAK_POLICY_DECLARED = "declared"
TWEAK_POLICY_OFF = "off"
TWEAK_POLICIES = frozenset({TWEAK_POLICY_PERMISSIVE, TWEAK_POLICY_DECLARED, TWEAK_POLICY_OFF})


def flow_declares_api_editable(nodes: list[dict[str, Any]]) -> bool:
    """Return whether any node in the flow marks a template field ``api_editable``.

    This is the derived form of the per-flow enforcement opt-in. A flow whose
    author has toggled at least one field has declared an allowlist, so the
    remaining fields are closed under ``declared``. A flow with no toggles has
    declared nothing and keeps permissive behavior, which is what stops a
    deployment-wide switch from breaking every flow nobody prepared.

    A later release replaces this derived value with a stored flag on the flow.
    """
    for node in nodes:
        template = node.get("data", {}).get("node", {}).get("template")
        if not isinstance(template, dict):
            continue
        for field in template.values():
            if isinstance(field, dict) and field.get("api_editable") is True:
                return True
    return False


def is_tweak_refused_by_policy(
    policy: str,
    *,
    flow_declares_allowlist: bool,
    field_is_api_editable: bool,
) -> bool:
    """Return whether the deployment policy refuses a tweak on this field.

    The caller checks ``is_protected_tweak_field`` separately. That floor refuses
    in every policy, including ``permissive``. This function only decides the
    policy layer above the floor.
    """
    if policy == TWEAK_POLICY_OFF:
        return True
    if policy == TWEAK_POLICY_DECLARED and flow_declares_allowlist:
        return not field_is_api_editable
    return False


# Component node ``type`` values that load and execute *another* saved flow by
# id or name at build/run time. On the unauthenticated public path these are an
# indirect code-execution primitive: a public wrapper flow with none of the
# blocked types above can invoke a private owner flow that itself contains a
# code-execution component. The referenced flow is read straight from the
# database and never re-validated, so blocking it via CODE_EXECUTION_COMPONENT_TYPES
# alone is bypassable (report H1-3754930, transitive case). The flow-invoking
# node types are blocked outright on the public path rather than recursively
# resolved, which is fail-closed. Authenticated builds are unaffected.
FLOW_REFERENCE_COMPONENT_TYPES: frozenset[str] = frozenset(
    {
        "RunFlow",  # "Run Flow" — runs a selected flow by id/name
        "SubFlow",  # "Sub Flow" (legacy) — runs a selected flow by name
        "FlowTool",  # "Flow as Tool" (legacy) — exposes a selected flow as a tool
    }
)

# Component node ``type`` values whose only transport is an MCP **stdio** server, i.e. they
# always spawn an OS subprocess. Unlike ``MCPTools`` — which is legitimate on the public path
# when it points at a remote HTTP/SSE server — these carry no non-spawning configuration, so
# the type itself is refused for anonymous visitors.
MCP_STDIO_COMPONENT_TYPES: frozenset[str] = frozenset(
    {
        "MCPStdio",  # "MCP Tools (stdio) [DEPRECATED]" — packed command string input
        "MCP Tools (stdio) [DEPRECATED]",
    }
)

# Template field keys that carry an MCP server *selection* (``McpInput``). The stdio command
# lives in this field's VALUE, never in the validated ``code`` field, so trusted-code
# substitution does not touch it.
MCP_SERVER_FIELD_NAMES: frozenset[str] = frozenset({"mcp_server"})

# ``McpInput``'s serialized template ``type``.
MCP_SERVER_FIELD_TYPE = "mcp"


def _compute_code_hash(code: str) -> str:
    """Compute the 12-char SHA256 prefix used by the component index."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def _normalize_flow_data(flow_data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Normalize wrapped flow payloads to the raw graph data shape."""
    if flow_data is None:
        return None

    normalized: Mapping[str, Any] = flow_data
    if "data" in normalized and isinstance(normalized["data"], Mapping):
        normalized = normalized["data"]

    return normalized if isinstance(normalized, dict) else dict(normalized)


def _extract_graph_payload(graph: Any) -> Mapping[str, Any] | None:
    """Extract a graph payload from a Graph-like object for policy validation.

    Only uses ``raw_graph_data`` — the authoritative, unmodified graph
    payload stored at construction time.  We intentionally avoid falling
    back to ``graph.dump()`` because dump may omit nodes or return
    a reconstructed payload that doesn't reflect the original flow
    definition, which could silently bypass validation.
    """
    raw_graph_data = getattr(graph, "raw_graph_data", None)
    if isinstance(raw_graph_data, Mapping):
        return raw_graph_data

    return None


def _extract_flow_data(target: Mapping[str, Any] | Any | None) -> dict[str, Any] | None:
    """Normalize a flow payload or graph-like object to raw graph data."""
    if isinstance(target, Mapping) or target is None:
        return _normalize_flow_data(target)

    return _normalize_flow_data(_extract_graph_payload(target))


def _collect_catalog_component_keys(nodes: Any) -> set[str]:
    """Collect exact component keys from a graph and its inlined nested flows."""
    component_keys: set[str] = set()
    if not isinstance(nodes, list):
        return component_keys

    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, Mapping):
            continue

        component_type = node_data.get("type")
        if isinstance(component_type, str):
            component_keys.add(component_type)

        node_info = node_data.get("node")
        if not isinstance(node_info, Mapping):
            continue
        nested_flow = node_info.get("flow")
        if not isinstance(nested_flow, Mapping):
            continue
        nested_data = nested_flow.get("data")
        if not isinstance(nested_data, Mapping):
            continue
        component_keys.update(_collect_catalog_component_keys(nested_data.get("nodes")))

    return component_keys


def collect_catalog_component_keys(target: Mapping[str, Any] | Any | None) -> frozenset[str]:
    """Return the exact component keys stored in a flow payload or Graph-like object.

    Accepts the same targets as :func:`validate_catalog_policy_for_flow` —
    a raw graph payload, a wrapped ``{"data": {...}}`` flow payload, or a
    Graph-like object — and includes keys from inlined nested flows. A target
    without extractable graph data yields an empty set; callers that must
    fail closed on unparseable payloads should keep using
    :func:`validate_catalog_policy_for_flow`.
    """
    normalized_flow_data = _extract_flow_data(target)
    if not normalized_flow_data:
        return frozenset()
    return frozenset(_collect_catalog_component_keys(normalized_flow_data.get("nodes")))


def get_component_identity_index_for_validation() -> ComponentIdentityIndex | None:
    """Return the cached canonical identity index when the registry is ready."""
    from lfx.interface.components import get_component_identity_index

    return get_component_identity_index()


def _resolve_catalog_policy_matches(
    component_keys: set[str],
    blocked_component_keys: frozenset[str],
    identity_index: ComponentIdentityIndex,
) -> frozenset[str]:
    """Return canonical identities shared by observed and blocked keys."""
    blocked_identities = identity_index.resolve_many(blocked_component_keys)
    return frozenset(
        canonical_identity
        for component_key in component_keys
        for canonical_identity in identity_index.resolve(component_key)
        if canonical_identity in blocked_identities
    )


def validate_catalog_policy_for_flow(
    target: Mapping[str, Any] | Any | None,
    *,
    snapshot: CatalogPolicySnapshot | None = None,
) -> None:
    """Reject a flow containing component keys blocked by the current catalog snapshot.

    Exact, case-sensitive keys are enforced before the current registry's
    canonical alias index is consulted. The immutable policy snapshot is
    captured once when the caller does not provide one, so every node in a
    request is evaluated against the same policy view.
    """
    if snapshot is None:
        from lfx.services.deps import get_catalog_policy_service

        snapshot = get_catalog_policy_service().snapshot

    if not snapshot.blocked_component_keys:
        return

    normalized_flow_data = _extract_flow_data(target)
    if target is not None and normalized_flow_data is None:
        msg = (
            "Flow validation failed: could not extract graph data from the provided target. "
            "Ensure the flow payload or Graph object contains valid graph data."
        )
        raise CatalogPolicyValidationError(msg)
    if not normalized_flow_data:
        return

    component_keys = _collect_catalog_component_keys(normalized_flow_data.get("nodes"))
    if not component_keys:
        return

    # Preserve exact matching even when the registry cache is still loading.
    # This keeps synthetic/custom identities backward-compatible and lets an
    # exact policy denial fail closed without waiting for alias data.
    blocked = snapshot.blocked_components(component_keys)
    if not blocked:
        identity_index = get_component_identity_index_for_validation()
        if identity_index is None:
            raise CatalogPolicyIdentityUnavailableError(CATALOG_POLICY_IDENTITIES_UNAVAILABLE_MESSAGE)
        blocked = _resolve_catalog_policy_matches(
            component_keys,
            snapshot.blocked_component_keys,
            identity_index,
        )
    if not blocked:
        return

    blocked_names = ", ".join(sorted(blocked))
    logger.warning(f"Flow build blocked by catalog policy: {blocked_names}")
    message = f"Flow build blocked: catalog policy blocks components: {blocked_names}"
    raise CatalogPolicyValidationError(message)


def collect_component_hash_lookups(
    all_types_dict: Mapping[str, Any],
) -> tuple[dict[str, set[str]], set[str]]:
    """Build code-hash lookups for components and their aliases.

    Each component type maps to a *set* of valid hashes so that
    custom components loaded from ``components_path`` can coexist
    with built-in components of the same name.
    """
    type_to_hash: dict[str, set[str]] = {}
    all_hashes: set[str] = set()

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue

        for component_name, component_data in category_components.items():
            if not isinstance(component_data, Mapping):
                continue

            metadata = component_data.get("metadata")
            if not isinstance(metadata, Mapping):
                continue

            code_hash = metadata.get("code_hash")
            if not isinstance(code_hash, str) or not code_hash:
                continue

            all_hashes.add(code_hash)
            for alias in get_component_type_aliases(component_name, component_data):
                type_to_hash.setdefault(alias, set()).add(code_hash)

    return type_to_hash, all_hashes


def collect_code_by_hash(
    all_types_dict: Mapping[str, Any],
) -> dict[str, str]:
    """Map each known component code-hash to its trusted server-side source.

    The hash gate (``code_hash_matches_any_template``) only proves that a
    submitted blob *hashes* to a known value. Because the hash is a truncated
    digest, a collision could let attacker-controlled code clear the gate. By
    exec'ing the trusted source returned here — keyed by the same hash — a
    collision merely re-runs the server's own known-good component instead of
    the client bytes. See ``get_trusted_code_for_validation``.

    Only source whose recomputed hash actually equals its key is trusted, so a
    malformed index entry can never widen what gets executed.
    """
    code_by_hash: dict[str, str] = {}

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue

        for component_data in category_components.values():
            if not isinstance(component_data, Mapping):
                continue

            metadata = component_data.get("metadata")
            if not isinstance(metadata, Mapping):
                continue

            code_hash = metadata.get("code_hash")
            if not isinstance(code_hash, str) or not code_hash:
                continue

            template = component_data.get("template")
            if not isinstance(template, Mapping):
                continue

            code_field = template.get("code")
            if not isinstance(code_field, Mapping):
                continue

            source = code_field.get("value")
            if not isinstance(source, str) or not source:
                continue

            # Defensive: only trust source whose hash matches its key, so a
            # bad index entry can't smuggle in code under a known hash.
            if _compute_code_hash(source) != code_hash:
                continue

            code_by_hash.setdefault(code_hash, source)

    return code_by_hash


def _get_invalid_components(
    nodes: list[dict],
    type_to_current_hash: Mapping[str, set[str]],
    substitutable_types: Container[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Walk nodes and classify invalid components.

    ``substitutable_types`` names the component types whose drifted code this server will
    replace with its own copy at build time (see
    :func:`substitute_outdated_component_code_in_place`). A hash mismatch on one of those
    types is not reported as outdated, because the stored code is never what runs. It only
    ever suppresses the *outdated* classification — an unrecognized type is still blocked.
    """
    blocked: list[str] = []
    outdated: list[str] = []

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            blocked.append(f"malformed component (index {index})")
            continue

        node_data = node.get("data")
        node_id = node.get("id", f"index {index}")
        if not isinstance(node_data, dict):
            blocked.append(f"malformed component ({node_id})")
            continue

        node_info = node_data.get("node")
        if not isinstance(node_info, dict):
            blocked.append(f"malformed component ({node_id})")
            continue

        component_type = node_data.get("type")

        node_template = node_info.get("template", {})
        if not isinstance(node_template, dict):
            blocked.append(f"malformed component ({node_id})")
            continue
        node_code_field = node_template.get("code", {})
        node_code = node_code_field.get("value") if isinstance(node_code_field, dict) else None

        if node_code:
            display_name = node_info.get("display_name") or component_type or "unknown"
            node_id = node_data.get("id") or node_id
            label = f"{display_name} ({node_id})"

            if not isinstance(node_code, str):
                blocked.append(label)
                continue

            # A node carrying executable code must resolve to a known component
            # type so its code hash can be checked against the trusted set. If the
            # type is missing/empty (or otherwise unknown), it can never match a
            # known hash, so block it instead of silently skipping it.
            #
            # Security (GHSA-mfp9-86w4-493f): this previously did
            # `if not component_type: continue`, so a crafted node with an empty
            # `type` but a populated `template.code.value` bypassed the
            # allow_custom_components gate while its stored code still executed at
            # build time (instantiate_class runs the node's stored code, which
            # does not consult the type).
            expected_hashes = type_to_current_hash.get(component_type) if isinstance(component_type, str) else None
            if expected_hashes is None:
                blocked.append(label)
            else:
                node_hash = _compute_code_hash(node_code)
                is_substitutable = substitutable_types is not None and component_type in substitutable_types
                if node_hash not in expected_hashes and not is_substitutable:
                    outdated.append(label)

        flow_data = node_info.get("flow", {})
        if isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            if not isinstance(nested_data, dict):
                blocked.append(f"malformed nested flow ({node_id})")
                continue
            nested_nodes = nested_data.get("nodes", [])
            if not isinstance(nested_nodes, list):
                blocked.append(f"malformed nested flow ({node_id})")
                continue
            if nested_nodes:
                nested_blocked, nested_outdated = _get_invalid_components(
                    nested_nodes,
                    type_to_current_hash,
                    substitutable_types,
                )
                blocked.extend(nested_blocked)
                outdated.extend(nested_outdated)
        elif flow_data is not None:
            blocked.append(f"malformed nested flow ({node_id})")

    return blocked, outdated


def _find_code_execution_components(nodes: list[dict]) -> list[str]:
    """Return labels for every node whose type is a built-in code-execution component.

    Recurses into nested/sub-flow node payloads so a code-execution component cannot be
    hidden inside an embedded flow definition.
    """
    found: list[str] = []

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            msg = f"Flow validation failed: malformed component at index {index}."
            raise CustomComponentValidationError(msg)

        node_data = node.get("data")
        node_id = node.get("id", f"index {index}")
        if not isinstance(node_data, dict):
            msg = f"Flow validation failed: malformed component ({node_id})."
            raise CustomComponentValidationError(msg)

        node_info = node_data.get("node")
        if not isinstance(node_info, dict):
            msg = f"Flow validation failed: malformed component ({node_id})."
            raise CustomComponentValidationError(msg)

        display_name = node_info.get("display_name")

        component_type = node_data.get("type")
        if is_code_execution_component(component_type, display_name):
            display_name = display_name or component_type
            node_id = node_data.get("id") or node_id
            found.append(f"{display_name} ({node_id})")

        flow_data = node_info.get("flow", {})
        if isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            if not isinstance(nested_data, dict):
                msg = f"Flow validation failed: malformed nested flow ({node_id})."
                raise CustomComponentValidationError(msg)
            nested_nodes = nested_data.get("nodes", [])
            if not isinstance(nested_nodes, list):
                msg = f"Flow validation failed: malformed nested flow ({node_id})."
                raise CustomComponentValidationError(msg)
            if nested_nodes:
                found.extend(_find_code_execution_components(nested_nodes))
        elif flow_data is not None:
            msg = f"Flow validation failed: malformed nested flow ({node_id})."
            raise CustomComponentValidationError(msg)

    return found


def check_code_execution_components_and_raise(flow_data: dict | None) -> None:
    """Block flows containing built-in arbitrary-code-execution components.

    Called when ``block_code_interpreter_components`` is enabled. Raises
    :class:`CustomComponentValidationError` if any code-execution component is present.
    """
    if not flow_data:
        return

    nodes = flow_data.get("nodes", [])
    if not isinstance(nodes, list):
        msg = "Flow validation failed: nodes must be a list."
        raise CustomComponentValidationError(msg)
    if not nodes:
        return

    found = _find_code_execution_components(nodes)
    if found:
        names = ", ".join(found)
        logger.warning(f"Flow build blocked: code-execution components are disabled: {names}")
        message = f"Flow build blocked: code-execution components are not allowed: {names}"
        raise CustomComponentValidationError(message)


def code_hash_matches_any_template(code: str, all_known_hashes: set[str]) -> bool:
    """Check whether code matches any known component template hash."""
    return _compute_code_hash(code) in all_known_hashes


def get_trusted_code_for_validation(code: str) -> str | None:
    """Return the server-trusted source whose hash matches ``code``, if any.

    When a request clears the hash gate in a restricted deployment
    (``allow_custom_components=False`` or admin-only mode), callers must exec
    the value returned here instead of the client-submitted bytes. Because the
    gate is a truncated-hash check, a second-preimage collision could otherwise
    run attacker code; substituting the trusted source keyed by the same hash
    closes that gap — a collision just re-runs the server's own component.

    Returns ``None`` when no trusted source is known for the code's hash, in
    which case callers must fail closed rather than fall back to client bytes.
    """
    from lfx.interface.components import component_cache

    code_hash = _compute_code_hash(code)
    with component_cache.state_lock:
        # Self-heal lazily when eager warm-up did not run. Building and
        # publishing under the same lock as reload prevents an old registry
        # snapshot from being published after reload invalidates it.
        if (
            component_cache.code_by_hash is None
            and component_cache.all_types_ready
            and component_cache.all_types_dict is not None
        ):
            component_cache.code_by_hash = collect_code_by_hash(component_cache.all_types_dict)

        code_by_hash = component_cache.code_by_hash
        if not code_by_hash:
            return None

        return code_by_hash.get(code_hash)


def get_trusted_code_and_hashes_for_validation(code: str) -> tuple[str | None, dict[str, set[str]] | None]:
    """Return trusted source and type hashes from one component-registry generation."""
    from lfx.interface.components import _build_code_hash_lookups, component_cache

    code_hash = _compute_code_hash(code)
    with component_cache.state_lock:
        if component_cache.all_types_ready and component_cache.all_types_dict is not None:
            if component_cache.code_by_hash is None:
                component_cache.code_by_hash = collect_code_by_hash(component_cache.all_types_dict)
            if component_cache.type_to_current_hash is None:
                _build_code_hash_lookups(component_cache)
        code_by_hash = component_cache.code_by_hash
        return (code_by_hash.get(code_hash) if code_by_hash else None, component_cache.type_to_current_hash)


def _substitute_trusted_code_by_hash(nodes: list[dict]) -> list[str]:
    """Replace code-bearing nodes with the matching server-trusted source.

    The caller must first validate each node's declared type and code hash with
    :func:`check_flow_and_raise`. This second pass ensures the build executes
    the server's copy for that exact hash instead of request bytes, and fails
    closed if the trusted-source lookup is incomplete. Nested flow payloads are
    handled recursively.
    """
    blocked: list[str] = []

    for node in nodes:
        if not isinstance(node, dict):
            continue

        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue

        node_info = node_data.get("node")
        if not isinstance(node_info, dict):
            continue

        template = node_info.get("template")
        code_field = template.get("code") if isinstance(template, dict) else None
        code = code_field.get("value") if isinstance(code_field, dict) else None
        if isinstance(code, str) and code:
            trusted = get_trusted_code_for_validation(code)
            if trusted is None:
                display_name = node_info.get("display_name") or node_data.get("type") or "unknown"
                node_id = node_data.get("id") or node.get("id", "unknown")
                blocked.append(f"{display_name} ({node_id})")
            else:
                code_field["value"] = trusted

        nested_flow = node_info.get("flow")
        if isinstance(nested_flow, dict):
            nested_data = nested_flow.get("data")
            nested_nodes = nested_data.get("nodes") if isinstance(nested_data, dict) else None
            if isinstance(nested_nodes, list) and nested_nodes:
                blocked.extend(_substitute_trusted_code_by_hash(nested_nodes))

    return blocked


def resolve_trusted_code_for_build(code: str, *, public_execution: bool = False) -> str:
    """Return the component code to ``exec`` for a build, enforcing restricted-mode substitution.

    In permissive mode (``allow_custom_components=True``, the default) the node's own ``code`` is
    returned unchanged — no behavior change.

    In restricted mode (``allow_custom_components=False``) the node only reached the build because
    it cleared the truncated-hash gate. Because that gate is a 48-bit prefix, a second-preimage
    collision could carry attacker bytes whose hash matches a built-in. Substitute the server's
    trusted source keyed by the same hash so a collision merely re-runs the server's own
    component. Fail closed (raise) when no trusted source is known for the hash, rather than fall
    back to the client bytes.
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    # Missing settings cannot prove permissive mode, but every consumer of allow_custom_components
    # in this module treats a missing attribute as the True default, so mirror that here.
    allow_custom_components = True
    if settings_service is not None:
        allow_custom_components = getattr(settings_service.settings, "allow_custom_components", True)

    if allow_custom_components:
        return code

    if public_execution:
        trusted, type_to_current_hash = get_trusted_code_and_hashes_for_validation(code)
    else:
        trusted = get_trusted_code_for_validation(code)
        type_to_current_hash = None
    if trusted is None:
        msg = "Flow build blocked: no trusted server component matches this component's code."
        raise CustomComponentValidationError(msg)
    if public_execution:
        # This is the last lookup before eval_custom_component_code. A hot extension reload may
        # have replaced the trusted source since Graph.from_payload's public check, so validate
        # the exact source returned from the current registry generation before executing it.
        validate_public_flow_no_code_execution(
            {"nodes": [_validation_node_for_code(trusted)]},
            type_to_current_hash=type_to_current_hash,
        )
    return trusted


def _validation_node_for_code(code: str) -> dict[str, Any]:
    """Build the minimal node shape used by code-hash policy checks."""
    return {
        "data": {
            "id": "runtime-component",
            "type": "",
            "node": {
                "display_name": "Runtime Component",
                "template": {"code": {"value": code}},
            },
        }
    }


def check_flow_and_raise(
    flow_data: dict | None,
    *,
    allow_custom_components: bool,
    type_to_current_hash: Mapping[str, set[str]] | None = None,
    substitutable_types: Container[str] | None = None,
) -> None:
    """Validate flow component code against known server templates.

    ``substitutable_types`` (normally :class:`SubstitutableComponentTypes` from
    :func:`get_outdated_code_substitution_lookups`) exempts drifted built-ins from the outdated
    check because the build substitutes this server's code for them. Unrecognized component
    types are still blocked.
    """
    if allow_custom_components or not flow_data:
        return

    nodes = flow_data.get("nodes", [])
    if not isinstance(nodes, list):
        msg = "Flow validation failed: nodes must be a list."
        raise CustomComponentValidationError(msg)
    if not nodes:
        return
    if type_to_current_hash is None:
        logger.error(
            "Flow validation requested but component hash lookups are not yet loaded. "
            "Blocking execution as a safety measure."
        )
        raise CustomComponentValidationError(INITIALIZING_COMPONENT_TEMPLATES_MESSAGE)

    blocked, outdated = _get_invalid_components(nodes, type_to_current_hash, substitutable_types)

    if blocked:
        blocked_names = ", ".join(blocked)
        logger.warning(f"Flow build blocked: unrecognized component code: {blocked_names}")
        message = f"Flow build blocked: custom components are not allowed: {blocked_names}"
        raise CustomComponentValidationError(message)

    if outdated:
        outdated_names = ", ".join(outdated)
        logger.warning(f"Flow build blocked: outdated components must be updated: {outdated_names}")
        message = f"Flow build blocked: outdated components must be updated before running: {outdated_names}"
        raise CustomComponentValidationError(message)


def get_component_hash_lookups_for_validation() -> dict[str, set[str]] | None:
    """Return the cached component hashes, building them synchronously if possible."""
    from lfx.interface.components import _build_code_hash_lookups, component_cache

    with component_cache.state_lock:
        if (
            component_cache.type_to_current_hash is None
            and component_cache.all_types_ready
            and component_cache.all_types_dict is not None
        ):
            _build_code_hash_lookups(component_cache)

        return component_cache.type_to_current_hash


def validate_catalog_policy_for_component_code(
    code: str,
    *,
    snapshot: CatalogPolicySnapshot | None = None,
) -> None:
    """Reject source that matches a blocked server component template.

    The code hash is checked against every exact catalog key's existing alias
    lookup before custom-component source is parsed or executed. An active
    policy fails closed while those trusted template identities are unavailable;
    an empty snapshot remains the documented default-allow behavior.
    """
    if snapshot is None:
        from lfx.services.deps import get_catalog_policy_service

        snapshot = get_catalog_policy_service().snapshot

    if not snapshot.blocked_component_keys:
        return

    type_to_current_hash = get_component_hash_lookups_for_validation()
    if type_to_current_hash is None:
        raise CatalogPolicyIdentityUnavailableError(CATALOG_POLICY_IDENTITIES_UNAVAILABLE_MESSAGE)

    code_hash = _compute_code_hash(code)
    # Preserve exact lookup behavior for synthetic/custom identities and
    # callers that provide a focused hash map in tests.
    blocked = frozenset(
        component_type
        for component_type in snapshot.blocked_component_keys
        if code_hash in type_to_current_hash.get(component_type, set())
    )
    if not blocked:
        identity_index = get_component_identity_index_for_validation()
        if identity_index is None:
            raise CatalogPolicyIdentityUnavailableError(CATALOG_POLICY_IDENTITIES_UNAVAILABLE_MESSAGE)
        blocked = frozenset(
            component_type
            for component_type in identity_index.resolve_many(snapshot.blocked_component_keys)
            if code_hash in type_to_current_hash.get(component_type, set())
        )
    if not blocked:
        return

    blocked_names = ", ".join(sorted(blocked))
    logger.warning(f"Component action blocked by catalog policy: {blocked_names}")
    message = f"Catalog policy blocks components: {blocked_names}"
    raise CatalogPolicyValidationError(message)


def validate_catalog_policy_for_component_type(
    component_type: str,
    *,
    snapshot: CatalogPolicySnapshot | None = None,
) -> None:
    """Reject a materialized component whose canonical identity is blocked."""
    if snapshot is None:
        from lfx.services.deps import get_catalog_policy_service

        snapshot = get_catalog_policy_service().snapshot

    if not snapshot.blocked_component_keys:
        return

    # Exact identities remain independently enforceable even before component
    # template initialization completes.
    if snapshot.is_component_blocked(component_type):
        blocked = frozenset({component_type})
    else:
        identity_index = get_component_identity_index_for_validation()
        if identity_index is None:
            raise CatalogPolicyIdentityUnavailableError(CATALOG_POLICY_IDENTITIES_UNAVAILABLE_MESSAGE)
        blocked = identity_index.resolve(component_type).intersection(
            identity_index.resolve_many(snapshot.blocked_component_keys)
        )

    if not blocked:
        return

    blocked_names = ", ".join(sorted(blocked))
    logger.warning(f"Component action blocked by catalog policy: {blocked_names}")
    message = f"Catalog policy blocks components: {blocked_names}"
    raise CatalogPolicyValidationError(message)


def validate_flow_for_current_settings(
    target: Mapping[str, Any] | Any | None,
    *,
    catalog_policy_snapshot: CatalogPolicySnapshot | None = None,
) -> None:
    """Enforce catalog and custom-component policy for a payload or graph-like object."""
    from lfx.services.deps import get_catalog_policy_service, get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    if catalog_policy_snapshot is None:
        catalog_policy_snapshot = get_catalog_policy_service().snapshot
    settings = settings_service.settings
    allow_custom_components = getattr(settings, "allow_custom_components", True)
    block_code_interpreter_components = getattr(settings, "block_code_interpreter_components", False)
    normalized_flow_data = _extract_flow_data(target)

    # If a blocking policy is active and we received a target but couldn't extract any flow
    # data from it, fail fast rather than silently skipping validation — the caller passed
    # something we can't verify.
    if (
        not allow_custom_components
        or block_code_interpreter_components
        or bool(catalog_policy_snapshot.blocked_component_keys)
    ) and (target is not None and normalized_flow_data is None):
        msg = (
            "Flow validation failed: could not extract graph data from the provided target. "
            "Ensure the flow payload or Graph object contains valid graph data."
        )
        raise CustomComponentValidationError(msg)

    validate_catalog_policy_for_flow(normalized_flow_data, snapshot=catalog_policy_snapshot)

    if block_code_interpreter_components:
        check_code_execution_components_and_raise(normalized_flow_data)

    # Pre-check call sites (API endpoints, warm-graph reuse) validate a payload they do not own,
    # so the substitution itself happens later, in Graph.from_payload, on the payload that is
    # actually built. Here we only need to agree with it about which drifted built-ins are going
    # to be rebuilt with this server's code, so the pre-check does not refuse a build that will
    # then succeed. Both sides read the same SubstitutableComponentTypes rule, so an ambiguous
    # type is neither substituted nor exempted here and stays blocked as outdated.
    substitution_lookups = None
    type_to_current_hash = None
    if not allow_custom_components:
        substitution_lookups = get_outdated_code_substitution_lookups()
        type_to_current_hash = (
            substitution_lookups[1].type_to_current_hash
            if substitution_lookups
            else get_component_hash_lookups_for_validation()
        )

    check_flow_and_raise(
        normalized_flow_data,
        allow_custom_components=allow_custom_components,
        type_to_current_hash=type_to_current_hash,
        substitutable_types=substitution_lookups[1] if substitution_lookups else None,
    )


def collect_component_code_lookups(all_types_dict: Mapping[str, Any]) -> dict[str, str]:
    """Map each known component type (and its aliases) to the server's trusted code.

    The value is the component's source as served by this instance
    (``template.code.value``). Used to substitute trusted code into public-flow nodes so the
    build runs server code, not the node's stored bytes. First alias wins on collision.
    """
    type_to_code: dict[str, str] = {}

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue

        for component_name, component_data in category_components.items():
            if not isinstance(component_data, Mapping):
                continue

            template = component_data.get("template")
            if not isinstance(template, Mapping):
                continue

            code_field = template.get("code")
            code = code_field.get("value") if isinstance(code_field, Mapping) else None
            if not isinstance(code, str) or not code:
                continue

            for alias in get_component_type_aliases(component_name, component_data):
                type_to_code.setdefault(alias, code)

    return type_to_code


def _substitute_trusted_node_code(nodes: list, type_to_code: dict[str, str]) -> list[str]:
    """Replace each code-bearing node's code with the server's trusted copy for its type.

    Mutates the given node dicts in place (callers pass a copy). A node carries an execution
    vector only through a non-empty ``template.code.value`` — for those nodes:
    * known component type → its stored code is overwritten with the server's trusted code, so
      version drift cannot break the build and a relabelled node cannot smuggle in its own bytes;
    * unknown component type → recorded as blocked (no trusted code exists to run).

    Nodes without executable code (group/note/container nodes) are left untouched. Recurses into
    inlined sub-flow definitions. Returns ``display_name (id)`` labels for blocked nodes.
    """
    blocked: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue

        node_info = node_data.get("node")
        node_info = node_info if isinstance(node_info, dict) else None

        code_field = None
        if node_info is not None:
            template = node_info.get("template")
            if isinstance(template, dict) and isinstance(template.get("code"), dict):
                code_field = template["code"]

        component_type = node_data.get("type")
        if code_field is not None and code_field.get("value"):
            if isinstance(component_type, str) and component_type in type_to_code:
                code_field["value"] = type_to_code[component_type]
            else:
                display_name = (node_info.get("display_name") if node_info else None) or component_type
                node_id = node_data.get("id") or node.get("id", "unknown")
                blocked.append(f"{display_name} ({node_id})")

        # Recurse into inlined sub-flows (group / sub-flow nodes).
        if node_info is not None:
            nested_flow = node_info.get("flow")
            if isinstance(nested_flow, dict):
                nested_data = nested_flow.get("data")
                nested_nodes = nested_data.get("nodes") if isinstance(nested_data, dict) else None
                if isinstance(nested_nodes, list) and nested_nodes:
                    blocked.extend(_substitute_trusted_node_code(nested_nodes, type_to_code))

    return blocked


def get_component_code_lookups_for_validation() -> dict[str, str] | None:
    """Return the cached component type→trusted-code map, building it synchronously if possible.

    ``None`` means the registry is not ready yet, which callers must treat as "no substitution
    is possible" and fall back to the strict hash check.
    """
    from lfx.interface.components import component_cache

    with component_cache.state_lock:
        # Self-heal lazily when eager warm-up did not run, mirroring
        # get_trusted_code_for_validation. Only this lookup is (re)built, so a
        # caller holding another derived index keeps its own consistent view.
        if (
            component_cache.type_to_code is None
            and component_cache.all_types_ready
            and component_cache.all_types_dict is not None
        ):
            component_cache.type_to_code = collect_component_code_lookups(component_cache.all_types_dict)

        return component_cache.type_to_code


@dataclass(frozen=True, slots=True)
class SubstitutableComponentTypes(Container[str]):
    """The component types whose drifted code this server will rebuild with its own copy.

    A type qualifies only when the registry resolves it to *exactly one* current code hash and
    this server has trusted code that hashes to that value. Two components can contribute the
    same type alias — a built-in and a ``components_path`` component of the same name, or an
    ``XComponent``/``X`` pair across bundles. ``collect_component_hash_lookups`` keeps every such
    hash, but ``collect_component_code_lookups`` is first-wins by registry iteration order, so for
    an ambiguous type the trusted code is not necessarily the source the node meant. Stored code
    that matches neither hash is indistinguishable from "this node is the other component", so
    those types are excluded and :func:`check_flow_and_raise` blocks them as outdated, exactly as
    it did before the substitution pass existed.

    Membership is decided on demand rather than materialized, so the substitution pass and the
    pre-check that must agree with it share one rule without copying the registry per build.
    """

    type_to_current_hash: Mapping[str, set[str]]
    type_to_code: Mapping[str, str]

    def __contains__(self, component_type: object) -> bool:
        if not isinstance(component_type, str):
            return False
        current_hashes = self.type_to_current_hash.get(component_type)
        if current_hashes is None or len(current_hashes) != 1:
            return False
        trusted_code = self.type_to_code.get(component_type)
        return isinstance(trusted_code, str) and _compute_code_hash(trusted_code) == next(iter(current_hashes))

    def current_hash(self, component_type: str) -> str:
        """Return the single current code hash for a substitutable ``component_type``."""
        return next(iter(self.type_to_current_hash[component_type]))


def get_outdated_code_substitution_lookups() -> tuple[dict[str, str], SubstitutableComponentTypes] | None:
    """Return ``(type_to_code, substitutable_types)`` when drifted built-ins are substitutable.

    ``None`` — meaning "keep the strict hash check" — is returned when custom components are
    allowed (nothing is gated, so the node's own code runs as authored), when the operator has
    turned ``substitute_outdated_component_code`` off, or when the component registry is not
    loaded yet (fail closed rather than let unverified code through).
    """
    from lfx.interface.components import component_cache
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        return None

    settings = settings_service.settings
    if getattr(settings, "allow_custom_components", True):
        return None
    if not getattr(settings, "substitute_outdated_component_code", True):
        return None

    # The cache publishes and invalidates all derived indexes under this lock. Keep it across
    # both reads so a hot reload cannot pair hashes from one registry snapshot with source from
    # another. The individual helpers also take this RLock while lazily self-healing an index.
    with component_cache.state_lock:
        type_to_current_hash = get_component_hash_lookups_for_validation()
        type_to_code = get_component_code_lookups_for_validation()
    if not type_to_current_hash or not type_to_code:
        return None

    return type_to_code, SubstitutableComponentTypes(type_to_current_hash, type_to_code)


def _substitute_outdated_node_code(
    nodes: list,
    type_to_code: Mapping[str, str],
    substitutable_types: SubstitutableComponentTypes,
) -> list[str]:
    """Replace drifted built-in code with this server's copy for the node's component type.

    Mutates the given node dicts in place. Only nodes whose ``data.type`` is substitutable (see
    :class:`SubstitutableComponentTypes`) and whose stored code hash no longer matches that type
    are touched; every other node — one whose type is unknown, and one whose type is ambiguous
    across the registry — is left exactly as it was for :func:`check_flow_and_raise` to
    classify. Recurses into inlined sub-flow definitions. Returns ``display_name (id)`` labels
    for swapped nodes.
    """
    swapped: list[str] = []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data")
        if not isinstance(node_data, dict):
            continue
        node_info = node_data.get("node")
        if not isinstance(node_info, dict):
            continue

        template = node_info.get("template")
        code_field = template.get("code") if isinstance(template, dict) else None
        code = code_field.get("value") if isinstance(code_field, dict) else None
        component_type = node_data.get("type")

        if (
            isinstance(code, str)
            and code
            and component_type in substitutable_types
            and _compute_code_hash(code) != substitutable_types.current_hash(component_type)
        ):
            trusted = type_to_code[component_type]
            if trusted != code:
                code_field["value"] = trusted
                display_name = node_info.get("display_name") or component_type
                node_id = node_data.get("id") or node.get("id", "unknown")
                swapped.append(f"{display_name} ({node_id})")

        nested_flow = node_info.get("flow")
        if isinstance(nested_flow, dict):
            nested_data = nested_flow.get("data")
            nested_nodes = nested_data.get("nodes") if isinstance(nested_data, dict) else None
            if isinstance(nested_nodes, list) and nested_nodes:
                swapped.extend(_substitute_outdated_node_code(nested_nodes, type_to_code, substitutable_types))

    return swapped


def substitute_outdated_component_code_in_place(
    flow_data: dict | None,
    *,
    validate_public_execution: bool = False,
) -> list[str]:
    """Rebuild drifted built-in nodes with this server's code before the flow is validated.

    Only active in restricted mode (``allow_custom_components=False``) with
    ``substitute_outdated_component_code`` enabled — the default. There, the node's stored code
    is never what executes: :func:`resolve_trusted_code_for_build` already substitutes the
    server's copy keyed by code hash. Without this pass, a built-in whose code merely drifted
    across an upgrade fails the hash check and the whole flow is refused over code that was
    never going to run.

    Swapping by component *type* is the same rule the unauthenticated public build path applies
    by default (:func:`prepare_public_flow_build`), and it does not widen what can execute: the
    code that runs is this server's own, and a node whose type is not a known server component
    is left untouched for :func:`check_flow_and_raise` to block. A type that two components
    claim is likewise left untouched, so drift is never resolved into the *wrong* component —
    see :class:`SubstitutableComponentTypes`.

    Mutates ``flow_data`` in place, matching ``Graph.from_payload``'s existing contract with
    ``migrate_flow_payload``; callers that must preserve the stored flow (so the editor keeps
    flagging the node as outdated) pass a copy. Returns ``display_name (id)`` labels for the
    nodes that were swapped.

    When ``validate_public_execution`` is true, the exact post-substitution bytes are checked
    against the public code-execution policy using the same registry snapshot that supplied
    trusted source. This closes the prepare-to-graph hot-reload window on unauthenticated
    execution paths: a later registry generation cannot replace already-checked source without
    that replacement being checked before component instantiation.
    """
    if not flow_data:
        return []

    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return []

    lookups = get_outdated_code_substitution_lookups()
    if lookups is None:
        if validate_public_execution:
            validate_public_flow_no_code_execution(flow_data)
        return []

    swapped = _substitute_outdated_node_code(nodes, *lookups)
    _log_outdated_component_code_substitution(swapped)
    if validate_public_execution:
        validate_public_flow_no_code_execution(
            flow_data,
            type_to_current_hash=lookups[1].type_to_current_hash,
        )
    return swapped


def _log_outdated_component_code_substitution(swapped: list[str]) -> None:
    """Warn when a build uses current server code for drifted stored components."""
    if not swapped:
        return

    # Substitution is safe but not neutral: a component can behave differently after an
    # upgrade (e.g. #14236 removed a default value), so never do it silently.
    logger.warning(
        f"Flow build: ran this server's component code for {len(swapped)} outdated "
        f"component(s) instead of the code stored in the flow: {', '.join(swapped)}. "
        "The stored flow is unchanged and these components remain flagged as outdated. "
        "Apply the pending component upgrade in the editor to pin the flow to this version, "
        "or configure LANGFLOW_SUBSTITUTE_OUTDATED_COMPONENT_CODE=false to refuse these builds."
    )


async def _ensure_public_component_lookup_snapshot(
    settings_service: Any,
) -> tuple[dict[str, str], Mapping[str, set[str]]]:
    """Return code and hash indexes from one component-registry snapshot (fail closed)."""
    from lfx.interface.components import component_cache, get_and_cache_all_types_dict

    with component_cache.state_lock:
        registry_unavailable = component_cache.all_types_dict is None or not component_cache.all_types_ready
    if registry_unavailable:
        try:
            await get_and_cache_all_types_dict(settings_service)
        except Exception as exc:
            logger.warning("Failed to load component templates for public flow sanitization", exc_info=exc)
            raise

    # Publication and invalidation replace all derived indexes under this RLock. Keep it across
    # both reads so trusted source selected for substitution and hashes used by the public
    # code-execution gate always describe the same registry generation.
    with component_cache.state_lock:
        type_to_code = get_component_code_lookups_for_validation()
        type_to_current_hash = get_component_hash_lookups_for_validation()
    return type_to_code or {}, type_to_current_hash or {}


async def prepare_public_flow_build(target: Mapping[str, Any] | Any | None) -> dict | None:
    """Return server-trusted, build-ready flow data for the unauthenticated public build path.

    ``POST /api/v1/build_public_tmp/{flow_id}/flow`` builds a public flow **as its owner**
    without authentication, executing the flow's components — each node's stored ``code`` is run
    via ``eval_custom_component_code``. The global ``allow_custom_components`` flag is an
    operator's decision to let *authenticated* users run custom (non-template) code; it must not
    silently extend that trust to anonymous visitors.

    Default (``allow_public_custom_components`` is False): every code-bearing node's code is
    replaced with the server's trusted code for its component type, and nodes whose type is not a
    known server component are rejected. Running the server's code (rather than gating on a code
    hash) means legitimate flows whose stored built-in code has merely drifted across versions
    still build, while arbitrary / relabelled custom code never executes. Returns the sanitized
    graph dict for the caller to build from.

    Opt-in (``allow_public_custom_components`` is True): preserves stored custom code only when
    the global custom-component policy is also permissive; that combination validates public
    code-execution surfaces and returns ``None`` so the caller builds from the database. When the
    global policy is restricted, this helper mirrors its trusted-code substitution on a copy,
    validates the effective graph, and returns it for the caller to build.

    The code-execution check is intentionally repeated after default-mode substitution. A
    namespaced extension identity may not itself appear in the public blocklist, while its
    trusted server source resolves to a blocked component. Validating only the stored bytes would
    let stale code evade the hash check and become blocked code during trusted substitution.

    Returns:
        The sanitized graph dict to build from, or ``None`` to fall back to the default
        database-loaded build (fully permissive opt-in, or no flow data to sanitize).

    Raises:
        CustomComponentValidationError: if the flow contains an unrecognized custom component, or
            the component templates cannot be loaded (fail closed).
        PublicFlowValidationError: if the executable graph contains a code-execution or
            flow-invoking component.
    """
    import copy

    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    settings = settings_service.settings

    # Fully permissive opt-in: honor the global custom-component policy and build from the
    # database as before. No later trusted-code substitution can change what is checked here.
    if settings.allow_public_custom_components and settings.allow_custom_components:
        validate_flow_for_current_settings(target)
        validate_public_flow_no_code_execution(target)
        return None

    normalized_flow_data = _extract_flow_data(target)
    if normalized_flow_data is None:
        # A target we cannot verify must fail closed rather than skip sanitization.
        if target is not None:
            msg = (
                "Flow validation failed: could not extract graph data from the provided target. "
                "Ensure the flow payload or Graph object contains valid graph data."
            )
            raise CustomComponentValidationError(msg)
        return None

    nodes = normalized_flow_data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return None

    type_to_code, type_to_current_hash = await _ensure_public_component_lookup_snapshot(settings_service)
    if not type_to_code or not type_to_current_hash:
        # Templates unavailable — do not let unverified code through.
        raise CustomComponentValidationError(INITIALIZING_COMPONENT_TEMPLATES_MESSAGE)

    sanitized = copy.deepcopy(normalized_flow_data)
    if settings.allow_public_custom_components:
        # Public custom-code opt-in does not override the global restricted-mode policy. Mirror
        # the substitution Graph.from_payload would otherwise perform later, then return this
        # effective graph so the public code-execution check covers the bytes that will run.
        validate_flow_for_current_settings(target)
        if getattr(settings, "substitute_outdated_component_code", True):
            substitutable_types = SubstitutableComponentTypes(type_to_current_hash, type_to_code)
            swapped = _substitute_outdated_node_code(sanitized.get("nodes", []), type_to_code, substitutable_types)
            _log_outdated_component_code_substitution(swapped)
        check_flow_and_raise(
            sanitized,
            allow_custom_components=False,
            type_to_current_hash=type_to_current_hash,
        )
    else:
        blocked = _substitute_trusted_node_code(sanitized.get("nodes", []), type_to_code)
        if blocked:
            blocked_names = ", ".join(blocked)
            logger.warning(
                f"Public flow build blocked: unrecognized custom components are not allowed: {blocked_names}"
            )
            message = (
                "Public flows cannot be built without authentication when they contain custom components: "
                f"{blocked_names}"
            )
            raise CustomComponentValidationError(message)

    # Validate what the executor will actually receive, not only the stale stored bytes checked
    # by route-level defense in depth. This central guarantee covers v1, v2, A2A start, and A2A
    # resume callers alike.
    validate_public_flow_no_code_execution(sanitized, type_to_current_hash=type_to_current_hash)
    return sanitized


def _node_code_hash(node_info: Any) -> str | None:
    """Return the code-hash of a node's ``code`` field, mirroring the hash gate.

    The build executes ``eval_custom_component_code(node.code)`` regardless of the
    node's declared ``type``, so the code-hash is the authoritative identity of
    what will actually run.
    """
    if not isinstance(node_info, Mapping):
        return None
    template = node_info.get("template", {})
    if not isinstance(template, Mapping):
        return None
    code_field = template.get("code", {})
    code = code_field.get("value") if isinstance(code_field, Mapping) else None
    if isinstance(code, str) and code:
        return _compute_code_hash(code)
    return None


def _blocked_code_hashes(
    canonical_types: frozenset[str],
    *,
    type_to_current_hash: Mapping[str, set[str]] | None = None,
) -> frozenset[str]:
    """Best-effort set of server template code-hashes for ``canonical_types``.

    A component's canonical name is always one of its own alias keys in the
    hash lookup, so ``type_to_current_hash[name]`` yields that component's known
    code-hash(es). Returns an empty set when the lookup is unavailable (e.g.
    custom components are allowed and the hash gate is inactive) — type-name
    matching still applies in that case.
    """
    if type_to_current_hash is None:
        type_to_current_hash = get_component_hash_lookups_for_validation()
    if not type_to_current_hash:
        return frozenset()
    hashes: set[str] = set()
    for component_type in canonical_types:
        hashes |= type_to_current_hash.get(component_type, set())
    return frozenset(hashes)


def _collect_blocked_components(
    nodes: list[dict],
    *,
    blocked_types: frozenset[str],
    blocked_hashes: frozenset[str],
) -> list[str]:
    """Return ``display_name (id)`` labels for nodes matching a blocked component.

    A node matches if its declared ``type`` is in ``blocked_types`` OR its
    ``code`` field hashes to a blocked component's known template hash. The
    code-hash check closes an aliasing bypass: in the hardened
    ``allow_custom_components=false`` mode a node can declare an alias ``type``
    (e.g. a display name) that still passes the custom-component hash gate and
    builds, yet whose executed code is a blocked component's.

    Recurses into *inlined* nested flow definitions (group / sub-flow nodes) so a
    blocked component cannot be hidden inside one. This follows only inlined
    nested flow data, not flows referenced by id/name from the database — those
    referencing components are themselves blocked via ``FLOW_REFERENCE_COMPONENT_TYPES``.
    """
    found: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data", {})
        if not isinstance(node_data, dict):
            continue

        node_info = node_data.get("node", {})
        display_name = node_info.get("display_name") if isinstance(node_info, dict) else None
        matched_by_type = node_data.get("type") in blocked_types or display_name in blocked_types
        matched_by_hash = bool(blocked_hashes) and _node_code_hash(node_info) in blocked_hashes
        if matched_by_type or matched_by_hash:
            display_name = display_name or node_data.get("type", "unknown")
            node_id = node_data.get("id") or node.get("id", "unknown")
            found.append(f"{display_name} ({node_id})")

        # Recurse into nested flows (group / sub-flow nodes).
        if isinstance(node_info, dict):
            nested_flow = node_info.get("flow", {})
            nested_nodes = nested_flow.get("data", {}).get("nodes", []) if isinstance(nested_flow, dict) else []
            if isinstance(nested_nodes, list) and nested_nodes:
                found.extend(
                    _collect_blocked_components(
                        nested_nodes, blocked_types=blocked_types, blocked_hashes=blocked_hashes
                    )
                )
    return found


def _selects_mcp_stdio_transport(config: Any) -> bool:
    """Return whether an MCP server configuration resolves to the subprocess-spawning transport.

    Mirrors the transport selection in ``lfx.base.mcp.util.update_tools``: an explicit
    ``mode`` of ``Stdio`` wins, otherwise the presence of ``command`` selects stdio. Keeping
    the two in step means a config this helper passes cannot become a spawn at the sink.
    """
    if not isinstance(config, Mapping):
        return False
    mode = config.get("mode")
    if isinstance(mode, str) and mode.strip():
        return mode.strip().casefold() == "stdio"
    return bool(config.get("command"))


def _mcp_configs_in_field_value(value: Any) -> list[Any]:
    """Return the MCP server configurations reachable from one template field value."""
    if not isinstance(value, Mapping):
        return []
    # ``McpInput`` stores ``{"name": ..., "config": {...}}``; a raw config may also be stored
    # directly, and an imported ``mcpServers`` map carries one config per server name.
    configs: list[Any] = [value, value.get("config")]
    servers = value.get("mcpServers")
    if isinstance(servers, Mapping):
        configs.extend(servers.values())
    return configs


def _is_mcp_server_field(field_name: Any, field: Mapping[str, Any]) -> bool:
    """Return whether a template entry holds an MCP server selection.

    Matched by the ``McpInput`` field type or name, and by the ``{"name", "config"}`` value
    shape, so relabelling the field key cannot hide a stdio configuration.
    """
    if field.get("type") == MCP_SERVER_FIELD_TYPE:
        return True
    if field_name in MCP_SERVER_FIELD_NAMES or field.get("name") in MCP_SERVER_FIELD_NAMES:
        return True
    value = field.get("value")
    return isinstance(value, Mapping) and ("config" in value or "mcpServers" in value)


def _collect_mcp_stdio_components(nodes: list[dict]) -> list[str]:
    """Return ``display_name (id)`` labels for nodes configuring an MCP stdio server.

    Recurses into inlined nested flow definitions for the same reason as
    ``_collect_blocked_components``.
    """
    found: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data", {})
        if not isinstance(node_data, dict):
            continue
        node_info = node_data.get("node", {})
        if not isinstance(node_info, dict):
            continue

        template = node_info.get("template", {})
        if isinstance(template, Mapping):
            for field_name, field in template.items():
                if not isinstance(field, Mapping) or not _is_mcp_server_field(field_name, field):
                    continue
                if any(
                    _selects_mcp_stdio_transport(config) for config in _mcp_configs_in_field_value(field.get("value"))
                ):
                    display_name = node_info.get("display_name") or node_data.get("type", "unknown")
                    node_id = node_data.get("id") or node.get("id", "unknown")
                    found.append(f"{display_name} ({node_id})")
                    break

        nested_flow = node_info.get("flow", {})
        nested_nodes = nested_flow.get("data", {}).get("nodes", []) if isinstance(nested_flow, dict) else []
        if isinstance(nested_nodes, list) and nested_nodes:
            found.extend(_collect_mcp_stdio_components(nested_nodes))
    return found


def validate_public_flow_no_code_execution(
    target: Mapping[str, Any] | Any | None,
    *,
    type_to_current_hash: Mapping[str, set[str]] | None = None,
) -> None:
    """Reject unauthenticated public-flow builds that would run arbitrary code.

    Public flows are reachable without authentication through
    ``/api/v1/build_public_tmp/{flow_id}/flow`` and build as the flow owner.
    Two classes of component are rejected on that path:

    * Direct code execution (``CODE_EXECUTION_COMPONENT_TYPES``) — the Python
      interpreter/REPL components, the legacy Python Code Structured tool,
      Smart Transform lambda and code-capable agent components — which run
      user- or model-supplied code (reports H1-3754930 and H1-3813558).
    * Flow invocation (``FLOW_REFERENCE_COMPONENT_TYPES``) — Run Flow, Sub Flow
      and Flow as Tool — which load and execute *another* saved owner flow by
      id/name at runtime. That referenced flow is read straight from the
      database and never re-validated, so a public wrapper flow with no blocked
      nodes could otherwise invoke a private flow containing a code-execution
      component, bypassing the check above (the transitive case).
    * MCP **stdio** server configuration — a node that launches an operating-system
      process to speak MCP over stdin/stdout. The command and arguments live in an
      ``McpInput`` field's VALUE (``mcp_server``), not in the ``code`` field, so
      neither the two blocklists above nor ``prepare_public_flow_build``'s
      trusted-code substitution touches them: the server would run the flow author's
      chosen command for an anonymous visitor. Remote MCP transports (HTTP/SSE) spawn
      nothing and remain allowed, so only the stdio selection is refused.

    The first two classes are matched both by the node's declared ``type`` and by its
    ``code``-hash, so relabelling a node's ``type`` to an alias cannot smuggle a
    blocked component past the check (the build runs the stored ``code``, not the
    ``type`` label). The MCP check matches the stored configuration's shape rather
    than the node type, because the same component type is safe over HTTP.

    This is enforced only on the unauthenticated public build path; authenticated
    builds (``/api/v1/build/{flow_id}/flow``) are unaffected and may still use
    these components.

    Raises:
        PublicFlowValidationError: if the flow contains a code-execution component,
            a flow-invoking component, or an MCP stdio server configuration.
    """
    normalized_flow_data = _extract_flow_data(target)
    if not normalized_flow_data:
        return

    nodes = normalized_flow_data.get("nodes", [])
    if not isinstance(nodes, list) or not nodes:
        return

    code_execution = _collect_blocked_components(
        nodes,
        blocked_types=CODE_EXECUTION_COMPONENT_TYPES,
        blocked_hashes=_blocked_code_hashes(
            CODE_EXECUTION_COMPONENT_TYPES,
            type_to_current_hash=type_to_current_hash,
        ),
    )
    if code_execution:
        blocked_names = ", ".join(code_execution)
        logger.warning(f"Public flow build blocked: code-execution components are not allowed: {blocked_names}")
        message = (
            "Public flows cannot be built without authentication when they contain "
            f"code-execution components: {blocked_names}"
        )
        raise PublicFlowValidationError(message)

    flow_references = _collect_blocked_components(
        nodes,
        blocked_types=FLOW_REFERENCE_COMPONENT_TYPES,
        blocked_hashes=_blocked_code_hashes(
            FLOW_REFERENCE_COMPONENT_TYPES,
            type_to_current_hash=type_to_current_hash,
        ),
    )
    if flow_references:
        blocked_names = ", ".join(flow_references)
        logger.warning(f"Public flow build blocked: flow-invoking components are not allowed: {blocked_names}")
        message = (
            "Public flows cannot be built without authentication when they contain "
            f"components that can execute other flows: {blocked_names}"
        )
        raise PublicFlowValidationError(message)

    mcp_stdio = _collect_mcp_stdio_components(nodes)
    mcp_stdio += _collect_blocked_components(
        nodes,
        blocked_types=MCP_STDIO_COMPONENT_TYPES,
        blocked_hashes=_blocked_code_hashes(
            MCP_STDIO_COMPONENT_TYPES,
            type_to_current_hash=type_to_current_hash,
        ),
    )
    if mcp_stdio:
        blocked_names = ", ".join(dict.fromkeys(mcp_stdio))
        logger.warning(f"Public flow build blocked: MCP stdio servers are not allowed: {blocked_names}")
        message = (
            "Public flows cannot be built without authentication when they launch a local "
            f"MCP server process (stdio transport): {blocked_names}"
        )
        raise PublicFlowValidationError(message)


async def ensure_component_hash_lookups_loaded(*, force: bool = False) -> dict[str, set[str]] | None:
    """Ensure component lookups required by active runtime policies are available.

    ``force=True`` also loads them for caller-specific policy, such as the
    admin-only gate for a non-superuser build request.
    """
    from lfx.interface.components import (
        component_cache,
        get_and_cache_all_types_dict,
        get_component_identity_index,
    )
    from lfx.services.deps import get_catalog_policy_service, get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    catalog_policy_active = bool(get_catalog_policy_service().snapshot.blocked_component_keys)
    policy_lookups_required = force or not settings_service.settings.allow_custom_components or catalog_policy_active
    with component_cache.state_lock:
        registry_unavailable = component_cache.all_types_dict is None or not component_cache.all_types_ready

    if policy_lookups_required and registry_unavailable:
        try:
            await get_and_cache_all_types_dict(settings_service)
        except Exception as exc:
            logger.warning("Failed to populate component template hash lookups", exc_info=exc)
            raise

    type_to_current_hash = get_component_hash_lookups_for_validation()
    if catalog_policy_active and get_component_identity_index() is None:
        raise CatalogPolicyIdentityUnavailableError(CATALOG_POLICY_IDENTITIES_UNAVAILABLE_MESSAGE)

    return type_to_current_hash


def _sanitize_admin_only_flow_build(
    target: Mapping[str, Any] | Any | None,
    *,
    type_to_current_hash: Mapping[str, set[str]] | None,
) -> dict[str, Any] | None:
    """Return trusted build data after component hashes have been loaded.

    Admin-only mode permits regular users to refresh and run known server
    component templates, but not to submit new or modified component code.
    When the global restricted-mode policy permits trusted substitution for a
    drifted built-in, apply it to the detached copy first. Then validate every
    code-bearing node against the server registry and replace the request bytes
    with the trusted source for the matching hash before the graph is handed to
    the build worker.
    """
    import copy

    normalized_flow_data = _extract_flow_data(target)
    if normalized_flow_data is None:
        if target is not None:
            msg = (
                "Flow validation failed: could not extract graph data from the provided target. "
                "Ensure the flow payload or Graph object contains valid graph data."
            )
            raise CustomComponentValidationError(msg)
        return None

    sanitized = copy.deepcopy(normalized_flow_data)
    # ``validate_flow_for_current_settings`` may have admitted known drift because restricted
    # mode will rebuild it with server code. Preserve that decision when admin-only mode adds its
    # own sanitizer; otherwise this second, strict hash check restores the very rejection the
    # substitution policy was designed to avoid. The helper no-ops in permissive mode, so
    # admin-only remains strict when it is the only active custom-component restriction.
    substitution_lookups = get_outdated_code_substitution_lookups()
    validation_hashes = type_to_current_hash
    if substitution_lookups:
        nodes = sanitized.get("nodes", [])
        swapped = _substitute_outdated_node_code(nodes, *substitution_lookups) if isinstance(nodes, list) else []
        _log_outdated_component_code_substitution(swapped)
        validation_hashes = substitution_lookups[1].type_to_current_hash
    check_flow_and_raise(
        sanitized,
        allow_custom_components=False,
        type_to_current_hash=validation_hashes,
    )

    nodes = sanitized.get("nodes", [])
    blocked = _substitute_trusted_code_by_hash(nodes) if isinstance(nodes, list) else []
    if blocked:
        blocked_names = ", ".join(blocked)
        logger.warning(f"Flow build blocked: trusted component source unavailable: {blocked_names}")
        message = f"Flow build blocked: no trusted server component matches: {blocked_names}"
        raise CustomComponentValidationError(message)

    return sanitized


def _admin_only_build_required(settings: Any, *, is_superuser: bool) -> bool:
    return getattr(settings, "custom_component_admin_only", False) is True and not is_superuser


def admin_only_build_required(*, is_superuser: bool) -> bool:
    """Whether the admin-only component policy currently applies to this caller.

    Exposed so execution seams that hold an already-compiled graph can decide whether that
    compilation may still be trusted, without paying for the full sanitizer. A graph compiled
    while the policy was off embeds the caller's own component source; if the policy applies
    now, that compilation predates it and must not be reused.
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        # Fail closed: without settings we cannot prove the policy is off.
        return True
    return _admin_only_build_required(settings_service.settings, is_superuser=is_superuser)


async def prepare_admin_only_flow_build(target: Mapping[str, Any] | Any | None) -> dict[str, Any] | None:
    """Backward-compatible admin-only sanitizer for callers that already selected this policy."""
    return _sanitize_admin_only_flow_build(
        target,
        type_to_current_hash=await ensure_component_hash_lookups_loaded(force=True),
    )


async def prepare_flow_build_for_user(
    target: Mapping[str, Any] | Any | None,
    *,
    is_superuser: bool,
) -> dict[str, Any] | None:
    """Apply cumulative build policies and sanitize inline data when required.

    This async form can populate a cold component registry and is used by V1
    endpoints before caller-supplied graph data reaches a graph constructor or
    worker. ``None`` means the original payload is safe to preserve unchanged.
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    admin_only = _admin_only_build_required(settings_service.settings, is_superuser=is_superuser)
    type_to_current_hash = await ensure_component_hash_lookups_loaded(force=True) if admin_only else None

    # Policies are cumulative: the admin-only hash gate must not disable the
    # code-interpreter or global custom-component restrictions.
    validate_flow_for_current_settings(target)
    if not admin_only:
        return None

    return _sanitize_admin_only_flow_build(target, type_to_current_hash=type_to_current_hash)


def prepare_flow_build_for_user_from_cache(
    target: Mapping[str, Any] | Any | None,
    *,
    is_superuser: bool,
) -> dict[str, Any] | None:
    """Synchronous policy gate for execution seams that construct responses.

    The V2 streaming host must validate before returning ``StreamingResponse``
    and cannot await registry loading at that seam. Startup normally warms the
    registry; if it is unavailable, the hash gate fails closed.
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    validate_flow_for_current_settings(target)
    if not _admin_only_build_required(settings_service.settings, is_superuser=is_superuser):
        return None

    return _sanitize_admin_only_flow_build(
        target,
        type_to_current_hash=get_component_hash_lookups_for_validation(),
    )
