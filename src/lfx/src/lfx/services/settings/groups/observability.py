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
    audit_enabled: bool = False
    """If set to True, record who changed each resource, when, and whether it worked.

    Off by default: the log is durable storage a deployment opts into.
    """
    audit_anonymize_payload: bool = False
    """Drop the payload from every audit row, keeping only who, what and when."""

    max_flow_version_entries_per_flow: int = 50
    """Max version history entries per flow. Oldest entries pruned on next snapshot.

    If retroactively lowered below the current count for a flow,
    the oldest entries are deleted only when the next entry is created.
    """
