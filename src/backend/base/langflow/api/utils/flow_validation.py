"""Flow validation utilities for custom component blocking.

When `allow_custom_components` is False, each node's code is hashed and checked
against the precomputed ``type_to_current_hash`` dict (built once at startup from
each component's ``metadata.code_hash``).

- If the node's type is unknown (not in the hash dict) it is **blocked** (truly custom).
- If the node's type is known but the hash doesn't match, it is **outdated** (needs update).
- If the hash matches, the component is current and allowed.

The client-side ``edited`` flag is NOT trusted for security decisions.

When the hash dict is unavailable (server still starting), execution is blocked
entirely (fail-closed).
"""

from __future__ import annotations

import hashlib

from lfx.log.logger import logger


def _compute_code_hash(code: str) -> str:
    """Compute the same 12-char SHA256 prefix used by the component index."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def _get_invalid_components(
    nodes: list[dict],
    type_to_current_hash: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Walk nodes and classify invalid components.

    Returns:
        (blocked, outdated) — two lists of ``"display_name (node_id)"`` strings.
        - blocked: node type not found in hash dict (truly custom component, no upgrade path)
        - outdated: node type found but code hash doesn't match current version (needs update)
    """
    blocked: list[str] = []
    outdated: list[str] = []

    # Cache of code -> computed hash to avoid repeated sha256 work on identical code strings.
    code_hash_cache: dict[str, str] = {}

    for node in nodes:
        node_data = node.get("data", {})
        node_info = node_data.get("node", {})

        component_type = node_data.get("type")
        if not component_type:
            continue

        node_template = node_info.get("template", {})
        node_code_field = node_template.get("code", {})
        node_code = node_code_field.get("value") if isinstance(node_code_field, dict) else None

        if not node_code:
            continue

        expected_hash = type_to_current_hash.get(component_type)
        if expected_hash is None:
            # Unknown type — truly custom component, no upgrade path
            display_name = node_info.get("display_name") or component_type
            node_id = node_data.get("id") or node.get("id", "unknown")
            label = f"{display_name} ({node_id})"
            blocked.append(label)
        else:
            # Compute or reuse hashed code
            node_hash = code_hash_cache.get(node_code)
            if node_hash is None:
                node_hash = _compute_code_hash(node_code)
                code_hash_cache[node_code] = node_hash

            if node_hash != expected_hash:
                display_name = node_info.get("display_name") or component_type
                node_id = node_data.get("id") or node.get("id", "unknown")
                label = f"{display_name} ({node_id})"
                outdated.append(label)

        # Recursively check nested flows (e.g., group nodes / sub-flows)
        flow_data = node_info.get("flow", {})
        if flow_data and isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            nested_nodes = nested_data.get("nodes", [])
            if nested_nodes:
                nested_blocked, nested_outdated = _get_invalid_components(nested_nodes, type_to_current_hash)
                blocked.extend(nested_blocked)
                outdated.extend(nested_outdated)

    return blocked, outdated


def code_hash_matches_any_template(code: str, all_known_hashes: set[str]) -> bool:
    """Check if the given code's hash matches any known component template."""
    return _compute_code_hash(code) in all_known_hashes


def check_flow_and_raise(
    flow_data: dict | None,
    *,
    allow_custom_components: bool,
    type_to_current_hash: dict[str, str] | None = None,
) -> None:
    """Check a flow for custom/outdated components and raise if blocked.

    Each node's code is hashed and compared against the precomputed
    type_to_current_hash dict. The client-side ``edited`` flag is NOT trusted.

    When type_to_current_hash is not available (server still starting), execution
    is blocked entirely (fail-closed).

    Args:
        flow_data: The flow's data dict.
        allow_custom_components: Whether custom components are allowed.
        type_to_current_hash: Dict of {component_type: current_code_hash}.

    Raises:
        ValueError: If custom/unknown code is found, or if outdated components need updating.
    """
    if allow_custom_components:
        return

    if not flow_data:
        return

    nodes = flow_data.get("nodes", [])
    if not nodes:
        return

    if type_to_current_hash is not None:
        blocked, outdated = _get_invalid_components(nodes, type_to_current_hash)

        if blocked:
            blocked_names = ", ".join(blocked)
            logger.warning(f"Flow build blocked: unrecognized component code: {blocked_names}")
            msg = f"Flow build blocked: custom components are not allowed: {blocked_names}"
            raise ValueError(msg)

        if outdated:
            outdated_names = ", ".join(outdated)
            logger.warning(f"Flow build blocked: outdated components must be updated: {outdated_names}")
            msg = f"Flow build blocked: outdated components must be updated before running: {outdated_names}"
            raise ValueError(msg)
    else:
        # Fail closed: hash dict not available, cannot verify code safety.
        logger.error(
            "Flow validation requested but component hash lookups are not yet loaded. "
            "Blocking execution as a safety measure."
        )
        msg = "Flow build blocked: server is still initializing component templates. Please try again in a few seconds."
        raise ValueError(msg)
