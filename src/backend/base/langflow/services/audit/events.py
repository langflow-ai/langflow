"""The audit event vocabulary — a public contract.

Once released, a name is never renamed: operators filter their pipelines on it
and group by its first three segments. ``test_events.py`` fails if a published
name changes, and every name's third segment is the row's ``resource_type`` so
the two can never drift apart.

Names are the *attempt*, not its outcome — ``flow.update``, never
``flow.updated``. The outcome lives in ``family`` and ``result``, so one name
covers the attempt that worked, the one that failed, and the one that was
refused, and a reader does not have to know three names to follow one action.
"""

from __future__ import annotations

AUDIT_PREFIX = "langflow.audit"

RESOURCE_FLOW = "flow"
RESOURCE_PROJECT = "project"

FLOW_CREATE = f"{AUDIT_PREFIX}.flow.create"
FLOW_UPDATE = f"{AUDIT_PREFIX}.flow.update"
FLOW_DELETE = f"{AUDIT_PREFIX}.flow.delete"
FLOW_RESTORE = f"{AUDIT_PREFIX}.flow.restore"
FLOW_RUN = f"{AUDIT_PREFIX}.flow.run"

PROJECT_CREATE = f"{AUDIT_PREFIX}.project.create"
PROJECT_UPDATE = f"{AUDIT_PREFIX}.project.update"
PROJECT_DELETE = f"{AUDIT_PREFIX}.project.delete"
# One row for the whole operation. The Control Plane asks "what happened to this
# project", and N rows describing the flows underneath answer a question nobody
# asked while burying the one they did.
PROJECT_REPLACE = f"{AUDIT_PREFIX}.project.replace"

PUBLISHED_EVENTS = frozenset(
    {
        FLOW_CREATE,
        FLOW_UPDATE,
        FLOW_DELETE,
        FLOW_RESTORE,
        FLOW_RUN,
        PROJECT_CREATE,
        PROJECT_UPDATE,
        PROJECT_DELETE,
        PROJECT_REPLACE,
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
        msg = f"Not an audit event name: {event!r}"
        raise ValueError(msg)
    return segments[2]
