"""Flow validation utilities for custom component blocking.

When `allow_custom_components` is False, components are validated against the server's
known component templates. Any node whose code does not match a known template is
blocked — the client-side `edited` flag is NOT trusted for security decisions.

When the server template cache (`all_types_dict`) is unavailable, execution is
blocked entirely (fail-closed).
"""

from __future__ import annotations

from typing import Any

from lfx.log.logger import logger


def _get_blocked_by_edited_flag(nodes: list[dict]) -> list[str]:
    """Fallback: walk nodes and return display names of any with edited=True.

    Used only when all_types_dict is not available. The edited flag is client-controlled
    and should not be the sole defense — this is a best-effort fallback.

    Also recursively checks group/sub-flow nodes that may contain nested flows.
    """
    blocked: list[str] = []
    for node in nodes:
        node_data = node.get("data", {})
        node_info = node_data.get("node", {})

        if node_info.get("edited", False):
            display_name = node_info.get("display_name") or node_data.get("type", "Unknown")
            node_id = node_data.get("id") or node.get("id", "unknown")
            blocked.append(f"{display_name} ({node_id})")

        # Recursively check nested flows (e.g., group nodes / sub-flows)
        flow_data = node_info.get("flow", {})
        if flow_data and isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            nested_nodes = nested_data.get("nodes", [])
            if nested_nodes:
                blocked.extend(_get_blocked_by_edited_flag(nested_nodes))

    return blocked


def _collect_all_template_codes(all_types_dict: dict[str, Any]) -> set[str]:
    """Build a set of all known template code strings from the server cache."""
    codes: set[str] = set()
    for category_components in all_types_dict.values():
        if not isinstance(category_components, dict):
            continue
        for component_data in category_components.values():
            if not isinstance(component_data, dict):
                continue
            template = component_data.get("template", {})
            code_field = template.get("code", {})
            if isinstance(code_field, dict):
                code_value = code_field.get("value")
                if code_value:
                    codes.add(code_value)
    return codes


def _get_blocked_by_code(nodes: list[dict], known_codes: set[str]) -> list[str]:
    """Walk nodes and return display names of any whose code is not a known template.

    This does NOT trust the `edited` flag — every node's code is checked against the
    server's known templates. If a node's code doesn't match any known template, it is
    treated as custom code regardless of the `edited` flag.
    """
    blocked: list[str] = []
    for node in nodes:
        node_data = node.get("data", {})
        node_info = node_data.get("node", {})

        node_template = node_info.get("template", {})
        node_code_field = node_template.get("code", {})
        node_code = node_code_field.get("value") if isinstance(node_code_field, dict) else None

        if node_code and node_code not in known_codes:
            display_name = node_info.get("display_name") or node_data.get("type", "Unknown")
            node_id = node_data.get("id") or node.get("id", "unknown")
            blocked.append(f"{display_name} ({node_id})")

        # Recursively check nested flows (e.g., group nodes / sub-flows)
        flow_data = node_info.get("flow", {})
        if flow_data and isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            nested_nodes = nested_data.get("nodes", [])
            if nested_nodes:
                blocked.extend(_get_blocked_by_code(nested_nodes, known_codes))

    return blocked


# Legacy type aliases: maps old flow node type names to current all_types_dict keys.
# PromptComponent was renamed from "Prompt" to "Prompt Template" but existing flows
# still reference the old "Prompt" type.
# SYNC: Keep in sync with initial_setup/setup.py and frontend reactflowUtils.ts
_LEGACY_TYPE_ALIASES: dict[str, str] = {
    "Prompt": "Prompt Template",
}


def _find_template_code(component_type: str, all_types_dict: dict[str, Any]) -> str | None:
    """Look up the current template code for a component type across all categories.

    Tries a direct key match first, then falls back to _LEGACY_TYPE_ALIASES
    (handles renamed components like "Prompt" → "Prompt Template").
    """
    # Try direct match, then alias
    types_to_try = [component_type]
    alias = _LEGACY_TYPE_ALIASES.get(component_type)
    if alias:
        types_to_try.append(alias)

    for lookup_type in types_to_try:
        for category_components in all_types_dict.values():
            if not isinstance(category_components, dict):
                continue
            component_data = category_components.get(lookup_type)
            if component_data and isinstance(component_data, dict):
                template = component_data.get("template", {})
                code_field = template.get("code", {})
                if isinstance(code_field, dict):
                    return code_field.get("value")
    return None


def code_matches_any_template(code: str, all_types_dict: dict[str, Any]) -> bool:
    """Check if the given code matches any known server component template."""
    known_codes = _collect_all_template_codes(all_types_dict)
    return code in known_codes


def _get_outdated_components(nodes: list[dict], all_types_dict: dict[str, Any]) -> list[str]:
    """Walk nodes and return display names of any whose code matches a known template but not the CURRENT template for their type.

    These are core components from a previous Langflow version that need updating.
    Distinct from blocked components (unknown code) — these have code that matches
    an older version of a known component type.
    """
    outdated: list[str] = []
    known_codes = _collect_all_template_codes(all_types_dict)

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

        # Skip nodes with unknown code — those are caught by _get_blocked_by_code
        if node_code not in known_codes:
            continue

        # Check if the code matches the CURRENT template for this specific type
        current_code = _find_template_code(component_type, all_types_dict)
        if current_code and node_code != current_code:
            display_name = node_info.get("display_name") or component_type
            node_id = node_data.get("id") or node.get("id", "unknown")
            outdated.append(f"{display_name} ({node_id})")

        # Recursively check nested flows
        flow_data = node_info.get("flow", {})
        if flow_data and isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            nested_nodes = nested_data.get("nodes", [])
            if nested_nodes:
                outdated.extend(_get_outdated_components(nested_nodes, all_types_dict))

    return outdated


def validate_flow_custom_components(flow_data: dict | None) -> list[str]:
    """Validate that a flow contains no custom (edited) components.

    Fallback path — uses the client-side edited flag. Prefer check_flow_and_raise()
    with all_types_dict for security-critical checks.

    Args:
        flow_data: The flow's data dict (containing nodes and edges).

    Returns:
        A list of blocked component descriptions. Empty list means all components are allowed.
    """
    if not flow_data:
        return []

    # Avoid creating a new empty list each call when the key is missing
    nodes = flow_data.get("nodes")
    if not nodes:
        return []

    return _get_blocked_by_edited_flag(nodes)


def validate_flows_custom_components(flows: list[dict]) -> dict[str, list[str]]:
    """Validate multiple flows for custom components.

    Args:
        flows: List of flow dicts, each with 'name' and 'data' keys.

    Returns:
        Dict mapping flow names to lists of blocked component descriptions.
        Only includes flows that have blocked components.
    """
    blocked_flows: dict[str, list[str]] = {}

    for flow in flows:
        name = flow.get("name", "Unknown Flow")
        data = flow.get("data")
        if not data:
            # Skip flows with no data to avoid an unnecessary function call
            continue

        # Skip flows that have no nodes without allocating a default list
        nodes = data.get("nodes")
        if not nodes:
            continue

        # Delegate to the single-flow validator to keep behavior centralized
        blocked = validate_flow_custom_components(data)
        if blocked:
            blocked_flows[name] = blocked
    return blocked_flows


def check_flow_and_raise(
    flow_data: dict | None,
    *,
    allow_custom_components: bool,
    all_types_dict: dict[str, Any] | None = None,
) -> None:
    """Check a flow for custom/outdated components and raise if blocked.

    When all_types_dict is available, every node's code is checked against the server's
    known templates — the client-side `edited` flag is NOT trusted. If all_types_dict is
    not available, execution is blocked entirely (fail-closed) until the template cache
    is populated.

    Args:
        flow_data: The flow's data dict.
        allow_custom_components: Whether custom components are allowed.
        all_types_dict: Dict of current component templates keyed by category.

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

    if all_types_dict is not None:
        # Primary path: verify code against server templates (ignores edited flag)
        known_codes = _collect_all_template_codes(all_types_dict)
        blocked = _get_blocked_by_code(nodes, known_codes)
        if blocked:
            blocked_names = ", ".join(blocked)
            logger.warning(f"Flow build blocked: unrecognized component code: {blocked_names}")
            msg = f"Flow build blocked: custom components are not allowed: {blocked_names}"
            raise ValueError(msg)

        # Also check for outdated components (known code, but wrong version for the type)
        outdated = _get_outdated_components(nodes, all_types_dict)
        if outdated:
            outdated_names = ", ".join(outdated)
            logger.warning(f"Flow build blocked: outdated components must be updated: {outdated_names}")
            msg = f"Flow build blocked: outdated components must be updated before running: {outdated_names}"
            raise ValueError(msg)
    else:
        # Fail closed: template cache not available, cannot verify code safety.
        # This typically happens during server startup before the component cache is populated.
        logger.error(
            "Flow validation requested but component template cache is not yet loaded. "
            "Blocking execution as a safety measure."
        )
        msg = "Flow build blocked: server is still initializing component templates. Please try again in a few seconds."
        raise ValueError(msg)
