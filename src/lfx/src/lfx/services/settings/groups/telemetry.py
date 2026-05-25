from pydantic import BaseModel


class TelemetrySettings(BaseModel):
    """Telemetry, error tracking, and tracing settings."""

    # Sentry
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float | None = 1.0
    sentry_profiles_sample_rate: float | None = 1.0

    # Telemetry
    do_not_track: bool = False
    """If set to True, Langflow will not track telemetry."""
    telemetry_base_url: str = "https://langflow.gateway.scarf.sh"

    transactions_storage_enabled: bool = True
    """If set to True, Langflow will track transactions between flows."""
    vertex_builds_storage_enabled: bool = True
    """If set to True, Langflow will keep track of each vertex builds (outputs) in the UI for any flow."""

    deactivate_tracing: bool = False
    """If set to True, tracing will be deactivated."""
