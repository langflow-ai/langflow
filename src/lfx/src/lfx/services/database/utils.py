"""Small validation helpers shared by the lfx-owned ORM models.

Moved from ``langflow.services.database.utils`` (which re-exports them) so the
model modules in ``lfx.services.database.models`` have no langflow imports.
Pure functions — no engine/session dependencies.
"""


def require_non_empty(value: str | None, error_msg: str) -> str:
    """Return a stripped non-empty string, or raise ``ValueError``."""
    stripped = (value or "").strip()
    if not stripped:
        raise ValueError(error_msg)
    return stripped


def validate_non_empty_string(v: str, info: object) -> str:
    """Validate a string field is non-empty after stripping whitespace.

    Intended for use inside ``@field_validator`` methods on SQLModel/Pydantic
    models.  Raises ``ValueError`` with the field name if the value is blank.
    """
    stripped = v.strip()
    if not stripped:
        field = getattr(info, "field_name", "Field")
        msg = f"{field} must not be empty"
        raise ValueError(msg)
    return stripped


def validate_non_empty_string_preserve_value(v: str, info: object) -> str:
    """Validate a string field is non-empty without normalizing its value."""
    if not v.strip():
        field = getattr(info, "field_name", "Field")
        msg = f"{field} must not be empty"
        raise ValueError(msg)
    return v


def validate_non_empty_string_optional(v: str | None, info: object) -> str | None:
    """Like :func:`validate_non_empty_string` but allows ``None`` (skip)."""
    if v is None:
        return v
    return validate_non_empty_string(v, info)


def normalize_string_or_none(v: str | None) -> str | None:
    """Strip whitespace from *v* and return ``None`` if the result is blank."""
    if v is None:
        return None
    stripped = v.strip()
    return stripped if stripped else None
