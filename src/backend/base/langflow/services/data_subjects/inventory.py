"""Every table, and how an erase reaches a person's rows in it (or why it holds none).

A guard test fails when a table exists that is not listed here, so a new table cannot silently
become a place where erased people's data survives.
"""

from __future__ import annotations

ERASED_WITH_FLOW = "erased with each owned flow"
BUILDER_ROWS = "builder rows deleted by user id"
REFERENCE_CLEARED = "reference to the person set to NULL"
END_USER_ROWS = "end-user rows matched by derived id, session prefix or job"
NOT_PERSONAL = "holds no personal data"

TABLE_POLICY: dict[str, str] = {
    "a2a_checkpoints": "not attributable: keyed by run id only (documented limit)",
    "a2a_tasks": ERASED_WITH_FLOW,
    "apikey": BUILDER_ROWS,
    "audit_events": "kept as evidence; account and credential UUIDs plus event-time resource names, no contact details",
    "authz_access_exception": BUILDER_ROWS,
    "authz_audit_log": "kept as evidence; identifying details redacted, subject reference cleared",
    "authz_edit_lock": BUILDER_ROWS,
    "authz_role": REFERENCE_CLEARED,
    "authz_role_assignment": BUILDER_ROWS,
    "authz_role_assignment_grant": "deleted with its role assignment (FK cascade and explicit parent delete)",
    "authz_share": BUILDER_ROWS,
    "authz_team": NOT_PERSONAL,
    "authz_team_member": BUILDER_ROWS,
    "authz_team_member_grant": "deleted with its team membership",
    "background_job_metric_totals": NOT_PERSONAL,
    "casbin_rule": "derived policy, rebuilt by the authorization plugin after the account is deleted",
    "catalog_policy_rule": REFERENCE_CLEARED,
    "connection": BUILDER_ROWS,
    "connection_oauth": BUILDER_ROWS,
    "connection_secret": BUILDER_ROWS,
    "data_subject_request": "the request itself; identifying columns cleared when it closes",
    "deployment": "blocks the erase until undeployed",
    "deployment_provider_account": BUILDER_ROWS,
    "execution_signals": ERASED_WITH_FLOW,
    "file": BUILDER_ROWS,
    "flow": ERASED_WITH_FLOW,
    "flow_operation": (
        "erased with each owned flow; edits to someone else's flow keep the account UUID only, "
        "which names no one once the account is deleted (history is append-only)"
    ),
    "flow_version": ERASED_WITH_FLOW,
    "flow_version_deployment_attachment": "blocks the erase until undeployed",
    "folder": BUILDER_ROWS,
    "ingestion_run": BUILDER_ROWS,
    "job": ERASED_WITH_FLOW,
    "job_checkpoints": ERASED_WITH_FLOW,
    "job_events": ERASED_WITH_FLOW,
    "knowledge_base": BUILDER_ROWS,
    "knowledge_base_storage_migration": "builder rows matched by the `<username>/` storage directory they name",
    "mcp_server": BUILDER_ROWS,
    "memory_base": ERASED_WITH_FLOW,
    "memory_base_preprocessing_output": END_USER_ROWS,
    "memory_base_session": END_USER_ROWS,
    "memory_base_workflow_run": END_USER_ROWS,
    "message": END_USER_ROWS,
    "message_ingestion_record": END_USER_ROWS,
    "model_provider_policy": NOT_PERSONAL,
    "policy_bundle_active": NOT_PERSONAL,
    "policy_bundle_revision": REFERENCE_CLEARED,
    "project_replacement_operation": BUILDER_ROWS,
    "span": ERASED_WITH_FLOW,
    "sso_config": REFERENCE_CLEARED,
    "sso_settings": NOT_PERSONAL,
    "sso_user_profile": BUILDER_ROWS,
    "trace": END_USER_ROWS,
    "transaction": "erased with each owned flow; an end user's and a builder's own runs matched by run owner",
    "trigger": "deleted when the erase is approved",
    "trigger_cleanup": "kept until the provider subscription is revoked or its sealed token expires; holds no content",
    "trigger_event": "deleted with its trigger",
    "trigger_lease": NOT_PERSONAL,
    "trigger_listener_lease": NOT_PERSONAL,
    "trigger_source_version": "deleted with its trigger when the erase is approved",
    "trigger_subscription": "deleted with its trigger",
    "user": "deleted last, through the identity-mutation protocol",
    "variable": BUILDER_ROWS,
    "vertex_build": END_USER_ROWS,
}
