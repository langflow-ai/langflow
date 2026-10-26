from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator


class ObservabilitySettings(BaseModel):
    """Metrics exposure and historical record retention."""

    prometheus_enabled: bool = False
    """If set to True, Langflow will expose Prometheus metrics."""
    prometheus_port: int = 9090
    """The port on which Langflow will expose Prometheus metrics. 9090 is the default port."""

    background_metrics_interval: int = Field(default=15, gt=0)
    """Seconds between background-execution DB-derived metric collector ticks.

    Must be > 0. ``asyncio.sleep`` returns immediately for zero or a negative value, which
    would turn the collector into a tight database-polling loop rather than a slow one."""

    max_transactions_to_keep: int = 3000
    """The maximum number of transactions to keep in the database."""
    max_vertex_builds_to_keep: int = 3000
    """The maximum number of vertex builds to keep in the database."""
    max_vertex_builds_per_vertex: int = 50
    """The maximum number of builds to keep per vertex. Older builds will be deleted."""
    audit_enabled: bool = False
    """If set to True, record an append-only audit event for each audited Flow and Project operation.

    Off by default: the audit history is durable storage a deployment opts into. When on,
    a committed operation and its event share one transaction.
    """
    audit_retention_days: int = 90
    """Days an audit event is kept. Cleanup deletes by timestamp only; 0 keeps events forever."""
    audit_trusted_api_key: SecretStr | None = Field(default=None, exclude=True)
    """API-key value allowed to assert represented audit identity after database authentication.

    Supply through a deployment Secret. This does not create or activate a key.
    The existing record-ID allowlist remains supported. Unset trusts no additional key.
    """
    audit_trusted_api_key_ids: list[UUID] = []
    """Database API-key record IDs allowed to assert represented audit identity.

    Comma-separated UUIDs or a programmatic UUID list. Empty adds no trusted record IDs. During key
    rotation both old and new record IDs may be allowed. User IDs and env keys do
    not grant this audit-only privilege.
    """

    @field_validator("audit_trusted_api_key_ids", mode="before")
    @classmethod
    def normalize_audit_trusted_api_key_ids(cls, value: str | list[UUID] | None) -> list[UUID]:
        """Strip each entry once, parse UUIDs, and preserve first-occurrence ordering."""
        entries = value.split(",") if isinstance(value, str) else (value or [])
        normalized = (str(entry).strip() for entry in entries)
        return list(dict.fromkeys(UUID(entry) for entry in normalized if entry))

    audit_exclude_events: list[str] = []
    """Audited actions never recorded, comma-separated: ``flow:write``, ``flow:*`` or ``*:delete``.

    Entries are only normalized here. The application decides what they match, and an
    entry that matches nothing is reported at startup and excludes nothing.
    """

    @field_validator("audit_exclude_events", mode="before")
    @classmethod
    def normalize_audit_exclude_events(cls, value: str | list[str] | None) -> list[str]:
        entries = value.split(",") if isinstance(value, str) else (value or [])
        normalized = (str(entry).strip().lower() for entry in entries)
        return list(dict.fromkeys(entry for entry in normalized if entry))

    max_flow_version_entries_per_flow: int = 50
    """Max version history entries per flow. Oldest entries pruned on next snapshot.

    If retroactively lowered below the current count for a flow,
    the oldest entries are deleted only when the next entry is created.
    """
