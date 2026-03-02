"""Domain exceptions for the flow-history module.

These are raised by the CRUD layer and translated to HTTP responses at the API boundary.
"""

from __future__ import annotations


class FlowHistoryError(Exception):
    """Base exception for flow-history domain errors."""


class FlowHistorySerializationError(FlowHistoryError):
    """Raised when flow data cannot be serialized."""


class FlowHistoryVersionConflictError(FlowHistoryError):
    """Raised when version number conflicts exhaust all retries."""


class FlowHistoryNotFoundError(FlowHistoryError):
    """Raised when a history entry is not found."""
