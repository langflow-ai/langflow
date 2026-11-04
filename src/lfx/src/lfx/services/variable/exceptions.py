"""Exceptions raised by variable services."""


class VariableNotFoundError(ValueError):
    """Raised when a requested variable does not exist."""


class RuntimeVariableError(ValueError):
    """An authoritative account lookup failed; another source must not be used."""

    def __init__(self, message: str, *, reason: str | None = None):
        self.reason = reason
        super().__init__(message)
