"""Canonical sets of administrative resource fields gated on the ``MANAGE`` action.

Route PATCH/PUT handlers consult these sets to decide whether a payload
requires :attr:`FlowAction.MANAGE` (resp. ``DeploymentAction.MANAGE`` /
``ProjectAction.MANAGE``) instead of the regular ``WRITE`` action. Keep these
sets small and stable — the enterprise plugin's policy contract depends on
operators reasoning about a fixed set of higher-privilege fields, not a
moving target.

Why a single ``MANAGE`` per resource (instead of per-field actions)?
- One verb keeps the Casbin policy surface compact.
- The enterprise plugin can still attach fine-grained policies by reading
  ``AuthzContext`` (e.g. the resource id / owner) when MANAGE is requested.
- New sensitive fields land here without forcing a new enum value or
  invalidating existing policies.
"""

from __future__ import annotations

from typing import Final

# Flow administrative fields:
#  - locked: edit-lock toggle; bypassing the lock is a higher-privilege action.
#  - access_type: PRIVATE/PUBLIC visibility toggle; widens external exposure.
#  - endpoint_name: public/webhook URL slug; rebinding it can hijack callers.
#  - webhook: enables the webhook endpoint surface.
#  - mcp_enabled: exposes the flow over the MCP server.
SENSITIVE_FLOW_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "locked",
        "access_type",
        "endpoint_name",
        "webhook",
        "mcp_enabled",
    }
)

# Deployment administrative fields. Empty today: PATCH only accepts
# name/description/provider_data (provider-opaque). MANAGE is still
# introduced on the action enum so policies can grant it once sensitive
# deployment fields exist.
SENSITIVE_DEPLOYMENT_FIELDS: Final[frozenset[str]] = frozenset()

# Project (folder) administrative fields:
#  - auth_settings: governance/policy JSON dict.
#  - parent_id: reparenting changes folder hierarchy / domain scope.
SENSITIVE_PROJECT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "auth_settings",
        "parent_id",
    }
)


def requires_flow_manage(payload_field_set: set[str] | frozenset[str]) -> bool:
    """Return True when a flow PATCH/PUT payload touches a MANAGE-gated field."""
    return bool(SENSITIVE_FLOW_FIELDS & payload_field_set)


def requires_deployment_manage(payload_field_set: set[str] | frozenset[str]) -> bool:
    """Return True when a deployment PATCH/PUT payload touches a MANAGE-gated field."""
    return bool(SENSITIVE_DEPLOYMENT_FIELDS & payload_field_set)


def requires_project_manage(payload_field_set: set[str] | frozenset[str]) -> bool:
    """Return True when a project PATCH/PUT payload touches a MANAGE-gated field."""
    return bool(SENSITIVE_PROJECT_FIELDS & payload_field_set)
