"""Domain exceptions for the flow-history module.

These are raised by the CRUD layer and translated to HTTP responses at the API boundary.
"""

from __future__ import annotations


class FlowHistoryError(Exception):
    """Base exception for flow-history domain errors."""


class FlowHistoryDataTooLargeError(FlowHistoryError):
    """Raised when flow data exceeds the configured size limit."""

    def __init__(self, data_size: int, max_size: int) -> None:
        self.data_size = data_size
        self.max_size = max_size
        super().__init__(
            f"Flow data size ({data_size:,} bytes) exceeds the maximum allowed "
            f"for history snapshots ({max_size:,} bytes)"
        )


class FlowHistorySerializationError(FlowHistoryError):
    """Raised when flow data cannot be serialized."""


class FlowHistoryVersionConflictError(FlowHistoryError):
    """Raised when version number conflicts exhaust all retries."""


class FlowHistoryNotFoundError(FlowHistoryError):
    """Raised when a history entry is not found."""
