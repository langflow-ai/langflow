"""Trusted local configuration errors for source activation and recovery."""

from __future__ import annotations


class SourceConfigurationError(ValueError):
    """A local configuration failure with fixed, safe text for the trigger owner.

    Callers must use locally authored messages without provider responses,
    credential values or user-supplied configuration interpolated into them.
    Terminal polling failures stop the affected trigger until it is re-enabled.
    """

    def __init__(self, message: str, *, terminal: bool = False) -> None:
        super().__init__(message)
        self.terminal = terminal
