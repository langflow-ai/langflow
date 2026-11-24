"""Trusted local configuration errors for source activation and recovery."""

from __future__ import annotations


class SourceConfigurationError(ValueError):
    """A local configuration failure with fixed, safe text for the trigger owner.

    Callers must use locally authored messages without provider responses,
    credential values or user-supplied configuration interpolated into them.
    """
