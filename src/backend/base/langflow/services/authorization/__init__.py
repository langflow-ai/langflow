"""OSS authorization service package (pass-through default; plugins enforce)."""

from langflow.services.authorization.actions import (
    DeploymentAction,
    FileAction,
    FlowAction,
    KnowledgeBaseAction,
    ProjectAction,
    ShareAction,
    VariableAction,
)
from langflow.services.authorization.audit import (
    audit_decision,
    drain_pending_audit_writes,
)
from langflow.services.authorization.decorators import requires_flow_permission, requires_resource_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.guards import (
    ensure_deployment_permission,
    ensure_file_permission,
    ensure_flow_permission,
    ensure_flows_permission,
    ensure_knowledge_base_permission,
    ensure_permission,
    ensure_project_permission,
    ensure_share_permission,
    ensure_variable_permission,
    should_apply_owner_override,
)
from langflow.services.authorization.listing import (
    apply_owned_or_visible_prefilter,
    apply_owned_or_visible_scope_prefilter,
    filter_visible_resources,
    resource_visible_in_scope,
    restrict_to_owned_or_visible,
    restrict_to_owned_or_visible_scope,
    visible_id_prefilter,
    visible_scope_prefilter,
)
from langflow.services.authorization.service import LangflowAuthorizationService

__all__ = [
    "DeploymentAction",
    "FileAction",
    "FlowAction",
    "KnowledgeBaseAction",
    "LangflowAuthorizationService",
    "ProjectAction",
    "ShareAction",
    "VariableAction",
    "apply_owned_or_visible_prefilter",
    "apply_owned_or_visible_scope_prefilter",
    "audit_decision",
    "authorized_or_owner_scoped",
    "deny_to_404",
    "drain_pending_audit_writes",
    "ensure_deployment_permission",
    "ensure_file_permission",
    "ensure_flow_permission",
    "ensure_flows_permission",
    "ensure_knowledge_base_permission",
    "ensure_permission",
    "ensure_project_permission",
    "ensure_share_permission",
    "ensure_variable_permission",
    "filter_visible_resources",
    "requires_flow_permission",
    "requires_resource_permission",
    "resource_visible_in_scope",
    "restrict_to_owned_or_visible",
    "restrict_to_owned_or_visible_scope",
    "should_apply_owner_override",
    "visible_id_prefilter",
    "visible_scope_prefilter",
]
