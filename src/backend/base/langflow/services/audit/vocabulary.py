"""The audit vocabulary: every value a producer may write into a closed column.

These strings are a published contract. The Control Plane translates them into
its public Deployment API, so a value is added here but never renamed.
"""

from __future__ import annotations

from enum import Enum


class AuditEventType(str, Enum):
    """Which question an event answers: was it permitted, or what did it do."""

    AUTHZ = "authz"
    ACTION = "action"


class AuditResult(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


RESULTS_BY_EVENT_TYPE: dict[AuditEventType, frozenset[AuditResult]] = {
    AuditEventType.AUTHZ: frozenset({AuditResult.ALLOW, AuditResult.DENY}),
    AuditEventType.ACTION: frozenset({AuditResult.SUCCEEDED, AuditResult.FAILED}),
}

RESULTS_REQUIRING_ERROR_CODE = frozenset({AuditResult.DENY, AuditResult.FAILED})


class AuditActorType(str, Enum):
    """How the request authenticated, never who it claims to act for."""

    USER = "user"
    API_KEY = "api_key"  # pragma: allowlist secret
    SERVICE = "service"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class AuditOperation(str, Enum):
    """The shape of the mutation that was attempted."""

    CREATE = "create"
    REPLACE = "replace"
    PATCH = "patch"
    DELETE = "delete"


class AuditResourceType(str, Enum):
    PROJECT = "project"
    FLOW = "flow"


class AuditErrorCode(str, Enum):
    """Safe machine classifications; the raw exception is never stored."""

    PERMISSION_DENIED = "PERMISSION_DENIED"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    PROJECT_NAME_CONFLICT = "PROJECT_NAME_CONFLICT"
    FLOW_NOT_FOUND = "FLOW_NOT_FOUND"
    FLOW_ID_CONFLICT = "FLOW_ID_CONFLICT"
    FLOW_NAME_CONFLICT = "FLOW_NAME_CONFLICT"
    INVALID_CONTENT = "INVALID_CONTENT"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


def audit_action(resource_type: AuditResourceType, permission: str) -> str:
    """The permission-level action name, such as ``project:write``."""
    return f"{resource_type.value}:{permission}"


PROJECT_CREATE = audit_action(AuditResourceType.PROJECT, "create")
PROJECT_WRITE = audit_action(AuditResourceType.PROJECT, "write")
PROJECT_DELETE = audit_action(AuditResourceType.PROJECT, "delete")
FLOW_CREATE = audit_action(AuditResourceType.FLOW, "create")
FLOW_WRITE = audit_action(AuditResourceType.FLOW, "write")
FLOW_DELETE = audit_action(AuditResourceType.FLOW, "delete")

ACTIONS_BY_RESOURCE_TYPE: dict[AuditResourceType, frozenset[str]] = {
    AuditResourceType.PROJECT: frozenset({PROJECT_CREATE, PROJECT_WRITE, PROJECT_DELETE}),
    AuditResourceType.FLOW: frozenset({FLOW_CREATE, FLOW_WRITE, FLOW_DELETE}),
}
