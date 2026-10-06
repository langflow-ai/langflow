from pydantic import AwareDatetime, BaseModel, Field


class BasePayload(BaseModel):
    """Common fields retained for local run-event consumers."""

    client_type: str | None = Field(default=None, serialization_alias="clientType")


class RunPayload(BasePayload):
    """A completed flow run retained for local enterprise consumers."""

    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str = Field("", serialization_alias="runErrorMessage")
    run_id: str | None = Field(None, serialization_alias="runId")
    # Set at the run-event boundary for local consumers; never exported.
    run_completed_at: AwareDatetime | None = Field(default=None, exclude=True)
