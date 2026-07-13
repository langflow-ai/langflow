"""Domain exceptions for the jobs service."""

from __future__ import annotations


class JobError(RuntimeError):
    """Base exception for job-domain errors."""


class DuplicateJobError(JobError):
    """Raised by create_job() when a non-retryable job with the same dedupe_key already exists.

    (QUEUED, IN_PROGRESS, or COMPLETED).
    FAILED and CANCELLED are retryable and do not trigger this error.
    Extends RuntimeError so existing except RuntimeError callers keep working.
    """
