"""Errors raised when the runtime refuses a tweak."""


class TweakRefusedError(Exception):
    """Raised when one or more tweak keys are refused before a flow runs.

    A refusal used to log a warning and drop the key, so a caller received 200
    and could not tell a refused tweak from an applied one. That is a reporting
    failure on a security path: the caller believes a value took effect when it
    did not.

    The API layer maps this to 422. Library callers (``lfx load``) see an
    ordinary Python exception, which is why this is not an ``HTTPException``.
    """

    def __init__(self, refused: list[str], *, reason: str, available: list[str] | None = None) -> None:
        self.refused = refused
        self.reason = reason
        self.available = available or []
        super().__init__(f"Refused tweak keys {refused}: {reason}")
