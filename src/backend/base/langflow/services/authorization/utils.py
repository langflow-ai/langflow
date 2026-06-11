"""Backward-compatible re-exports for the split authorization helpers.

The implementations now live in:

* ``langflow.services.authorization.audit``   — batched audit pipeline
* ``langflow.services.authorization.guards``  — ``ensure_*_permission`` family
* ``langflow.services.authorization.listing`` — ``filter_visible_resources``

This module is preserved so existing imports
(``from langflow.services.authorization.utils import ensure_flow_permission``)
keep working. New code should import from the focused submodules above.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from langflow.services.authorization.audit import (
    _AUDIT_BATCH_MAX,
    _AUDIT_QUEUE_MAX,
    _audit_writer_loop,
    _AuditEntry,
    _ensure_audit_writer_started,
    _flush_audit_batch,
    _split_obj,
    audit_decision,
    drain_pending_audit_writes,
)
from langflow.services.authorization.audit import (
    AUDIT_ALLOW as _AUDIT_ALLOW,
)
from langflow.services.authorization.audit import (
    AUDIT_DENY as _AUDIT_DENY,
)
from langflow.services.authorization.audit import (
    AUDIT_OWNER_OVERRIDE as _AUDIT_OWNER_OVERRIDE,
)
from langflow.services.authorization.guards import (
    _ACTION_ENUMS,
    _OWNER_CONTEXT_KEYS,
    _auth_context,
    _coerce_action,
    _ensure_resource_permission,
    _resolve_authz_domain,
    _resolve_flow_domain,
    ensure_deployment_permission,
    ensure_file_permission,
    ensure_flow_permission,
    ensure_knowledge_base_permission,
    ensure_permission,
    ensure_project_permission,
    ensure_share_permission,
    ensure_variable_permission,
)
from langflow.services.authorization.listing import (
    _default_resource_id_getter,
    filter_visible_resources,
)
from langflow.services.deps import get_authorization_service, get_settings_service

# Pre-rename name kept for plugins built against the casbin-specific
# wording. Functionally identical to ``_resolve_authz_domain`` — same
# (workspace_id, scope_id) → domain-string resolution. New code should
# import ``_resolve_authz_domain`` directly.
_resolve_casbin_domain = _resolve_authz_domain


def permission_denied_to_http(exc):
    """Translate an InsufficientPermissionsError into a 403 HTTPException."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message)


__all__ = [
    "_ACTION_ENUMS",
    "_AUDIT_ALLOW",
    "_AUDIT_BATCH_MAX",
    "_AUDIT_DENY",
    "_AUDIT_OWNER_OVERRIDE",
    "_AUDIT_QUEUE_MAX",
    "_OWNER_CONTEXT_KEYS",
    "_AuditEntry",
    "_audit_writer_loop",
    "_auth_context",
    "_coerce_action",
    "_default_resource_id_getter",
    "_ensure_audit_writer_started",
    "_ensure_resource_permission",
    "_flush_audit_batch",
    "_resolve_authz_domain",
    "_resolve_casbin_domain",
    "_resolve_flow_domain",
    "_split_obj",
    "audit_decision",
    "drain_pending_audit_writes",
    "ensure_deployment_permission",
    "ensure_file_permission",
    "ensure_flow_permission",
    "ensure_knowledge_base_permission",
    "ensure_permission",
    "ensure_project_permission",
    "ensure_share_permission",
    "ensure_variable_permission",
    "filter_visible_resources",
    "get_authorization_service",
    "get_settings_service",
    "permission_denied_to_http",
]
