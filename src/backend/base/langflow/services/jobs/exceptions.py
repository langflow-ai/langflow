"""Domain exceptions for the jobs service."""

from __future__ import annotations

# Durable event type a producer emits to pause a run for human input.
HUMAN_INPUT_REQUIRED_EVENT = "human_input_required"


class JobError(RuntimeError):
    """Base exception for job-domain errors."""


class DuplicateJobError(JobError):
    """Raised by create_job() when a non-retryable job with the same dedupe_key already exists.

    (QUEUED, IN_PROGRESS, or COMPLETED).
    FAILED and CANCELLED are retryable and do not trigger this error.
    Extends RuntimeError so existing except RuntimeError callers keep working.
    """


class PauseRequested(JobError):  # noqa: N818
    """Raised in the runner's drive loop when a producer pauses the run for human input.

    Carries the opaque request payload the producer (agent tool-approval or a Human
    Input node) filled in. The runner suspends the job (SUSPENDED, no terminal
    finalization) instead of completing or failing it; ``execute_with_status``
    re-raises it without writing a terminal status.
    """

    def __init__(self, payload: dict | None = None, request_id: str | None = None) -> None:
        super().__init__("Run paused for human input")
        self.payload = payload or {}
        self.request_id = request_id
