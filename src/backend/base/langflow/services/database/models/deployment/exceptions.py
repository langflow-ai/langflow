from __future__ import annotations


class DeploymentGuardError(Exception):
    """Raised when a DB trigger blocks an operation due to deployment constraints."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


_GUARD_PREFIX = "DEPLOYMENT_GUARD:"
_DETAIL_TRUNCATION_MARKERS = (
    " [SQL:",
    "\n[SQL:",
    " (Background on this error at:",
    "\n(Background on this error at:",
)


def _clean_guard_detail(detail: str) -> str:
    cleaned = detail.strip()
    for marker in _DETAIL_TRUNCATION_MARKERS:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0].strip()
    # Keep only the first line for wrapped DB error strings.
    if "\n" in cleaned:
        cleaned = cleaned.split("\n", 1)[0].strip()
    return cleaned


def parse_deployment_guard_error(exc: BaseException) -> DeploymentGuardError | None:
    """Walk chained exceptions and extract deployment guard trigger messages."""
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current)

        _before_prefix, separator, after_prefix = message.partition(_GUARD_PREFIX)
        if separator and ":" in after_prefix:
            _error_code, human_message = after_prefix.split(":", 1)
            return DeploymentGuardError(detail=_clean_guard_detail(human_message))

        current = current.__cause__ or current.__context__

    return None
