"""Domain exceptions for the flow-history module.

These are raised by the CRUD layer and translated to HTTP responses at the API boundary.
"""

from __future__ import annotations


class FlowVersionError(Exception):
    """Base exception for flow-version domain errors."""


class FlowVersionSerializationError(FlowVersionError):
    """Raised when flow data cannot be serialized."""


class FlowVersionConflictError(FlowVersionError):
    """Raised when version number conflicts exhaust all retries."""


class FlowVersionNotFoundError(FlowVersionError):
    """Raised when a version entry is not found."""
