from pydantic import BaseModel


class ObservabilitySettings(BaseModel):
    """Metrics exposure and historical record retention."""

    prometheus_enabled: bool = False
    """If set to True, Langflow will expose Prometheus metrics."""
    prometheus_port: int = 9090
    """The port on which Langflow will expose Prometheus metrics. 9090 is the default port."""

    max_transactions_to_keep: int = 3000
    """The maximum number of transactions to keep in the database."""
    max_vertex_builds_to_keep: int = 3000
    """The maximum number of vertex builds to keep in the database."""
    max_vertex_builds_per_vertex: int = 50
    """The maximum number of builds to keep per vertex. Older builds will be deleted."""
    max_flow_version_entries_per_flow: int = 50
    """Max version history entries per flow. Oldest entries pruned on next snapshot.

    If retroactively lowered below the current count for a flow,
    the oldest entries are deleted only when the next entry is created.
    """

    flow_audit_enabled: bool = False
    """If set to True, record who changed a flow's graph and what they changed.

    Off by default: the trail is durable storage a deployment opts into, and an
    autosave writes several times a minute.
    """
    max_flow_audit_entries_per_flow: int = 200
    """Max audit entries kept per flow. Oldest entries pruned when a new one opens.

    Coalescing bounds how fast the trail grows, not how far: a flow edited every
    day accrues an entry per session forever. Pruning happens only when a session
    starts, so a burst of editing never pays for it.
    """
    flow_audit_session_window_seconds: int = 300
    """How long one person's edits keep folding into a single audit entry.

    An entry per write is unreadable — typing a word produces one per keystroke
    burst — so consecutive edits by the same person to the same flow extend the
    open entry until they stop for this long.
    """
