"""The audit event vocabulary — a public contract.

Once released, a name is never renamed: operators filter their pipelines on it
and group by its first two segments. ``test_events.py`` fails if a published
name changes, and every name's third segment is the row's ``resource_type`` so
the two can never drift apart.
"""

from __future__ import annotations

AUDIT_PREFIX = "langflow.audit"

RESOURCE_FLOW = "flow"

FLOW_CREATED = f"{AUDIT_PREFIX}.flow.created"
FLOW_UPDATED = f"{AUDIT_PREFIX}.flow.updated"
FLOW_DELETED = f"{AUDIT_PREFIX}.flow.deleted"
FLOW_RESTORED = f"{AUDIT_PREFIX}.flow.restored"
FLOW_SAVE_DENIED = f"{AUDIT_PREFIX}.flow.save.denied"
FLOW_PERMISSION_DENIED = f"{AUDIT_PREFIX}.flow.permission.denied"
FLOW_RUN_SUCCEEDED = f"{AUDIT_PREFIX}.flow.run.succeeded"
FLOW_RUN_FAILED = f"{AUDIT_PREFIX}.flow.run.failed"

PUBLISHED_EVENTS = frozenset(
    {
        FLOW_CREATED,
        FLOW_UPDATED,
        FLOW_DELETED,
        FLOW_RESTORED,
        FLOW_SAVE_DENIED,
        FLOW_PERMISSION_DENIED,
        FLOW_RUN_SUCCEEDED,
        FLOW_RUN_FAILED,
    }
)

REASON_VERSION_CONFLICT = "version_conflict"
REASON_PERMISSION_DENIED = "permission_denied"
REASON_VALIDATION_ERROR = "validation_error"
REASON_COMPONENT_ERROR = "component_error"
REASON_TIMEOUT = "timeout"
REASON_OVERWRITE = "overwrite"


def resource_type_of(event: str) -> str:
    """The resource an event is about — the third segment of its name."""
    segments = event.split(".")
    expected_segments = 4
    if len(segments) < expected_segments or not event.startswith(f"{AUDIT_PREFIX}."):
        msg = f"malformed audit event name: {event!r}"
        raise ValueError(msg)
    return segments[2]
