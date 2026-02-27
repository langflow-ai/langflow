"""Domain exceptions for the flow version module.

These are raised by the CRUD layer and translated to HTTP responses at the API boundary.
"""

from __future__ import annotations


class FlowVersionError(Exception):
    """Base exception for flow version domain errors."""


class FlowVersionDataTooLargeError(FlowVersionError):
    """Raised when flow data exceeds the configured size limit."""

    def __init__(self, data_size: int, max_size: int) -> None:
        self.data_size = data_size
        self.max_size = max_size
        super().__init__(
            f"Flow data size ({data_size:,} bytes) exceeds the maximum allowed "
            f"for version snapshots ({max_size:,} bytes)"
        )


class FlowVersionSerializationError(FlowVersionError):
    """Raised when flow data cannot be serialized."""


class FlowVersionConflictError(FlowVersionError):
    """Raised when version number conflicts exhaust all retries."""


class FlowVersionNotFoundError(FlowVersionError):
    """Raised when a version is not found."""
