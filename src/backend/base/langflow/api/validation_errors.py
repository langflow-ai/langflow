"""Request-validation (422) responses that name the failing field without echoing its value.

FastAPI's default handler returns ``jsonable_encoder(exc.errors())``. Every
pydantic error in that list carries ``input`` -- the raw value that failed, or
for a missing field the whole enclosing object -- and some carry a ``ctx`` or a
``msg`` that quotes it. A 422 therefore reflected whatever the caller sent,
credential material included, into proxy logs, browser devtools and error
trackers (LE-2462, O1). The caller learns nothing it did not send; the fix is
about where the body ends up.

The handler keeps the response shape, ``{"detail": [{"type", "loc", "msg"}]}``,
so a client still sees which field failed and why, and removes the values:

* ``input`` is dropped from every entry.
* ``ctx`` keeps only keys pydantic fills from the schema (``min_length``,
  ``pattern``, ``expected``...). Keys filled from the submitted value
  (``error``, ``tag``, ``tz_actual``...) and unknown keys are dropped, and a
  custom (non-pydantic) error type keeps no ``ctx`` at all.
* ``msg`` is rewritten only when it can quote the input: the error carried an
  input-derived ctx key, or it is not a built-in pydantic type (a validator's
  own message). Submitted strings of at least ``MIN_REDACTED_LENGTH``
  characters are replaced with ``REDACTED`` there.

Response-model validation is untouched: FastAPI raises ``ResponseValidationError``
for that, a different exception this handler is not registered for.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, get_args

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic_core.core_schema import ErrorType

if TYPE_CHECKING:
    from fastapi.exceptions import RequestValidationError

REDACTED = "[redacted]"
# Shorter submitted strings stay in a message: redacting "a" or "id" would shred
# the validator's own wording, and a value that short is not a credential.
MIN_REDACTED_LENGTH = 8

# ctx keys pydantic fills from the field's schema, never from the submitted value.
_SCHEMA_CTX_KEYS = frozenset(
    {
        "class",
        "class_name",
        "decimal_places",
        "discriminator",
        "encoding",
        "expected",
        "expected_schemes",
        "expected_tags",
        "expected_version",
        "field_type",
        "ge",
        "gt",
        "le",
        "lt",
        "max_digits",
        "max_length",
        "method_name",
        "min_length",
        "multiple_of",
        "pattern",
        "tz_expected",
        "whole_digits",
    }
)
_BUILTIN_ERROR_TYPES = frozenset(get_args(ErrorType))


def _submitted_strings(value: object) -> set[str]:
    """Every string and number in a submitted value. Mapping keys are field names, not values."""
    found: set[str] = set()
    # Iterative, so a deeply nested body cannot exhaust the recursion limit here.
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            found.add(item)
        elif isinstance(item, Mapping):
            pending.extend(item.values())
        elif isinstance(item, list | tuple | set | frozenset):
            pending.extend(item)
        elif isinstance(item, int | float) and not isinstance(item, bool):
            found.add(str(item))
    return found


def _scrub_msg(msg: str, submitted: object) -> str:
    fragments = [fragment for fragment in _submitted_strings(submitted) if len(fragment) >= MIN_REDACTED_LENGTH]
    # Longest first, so a value containing a shorter one is replaced whole.
    for fragment in sorted(fragments, key=len, reverse=True):
        msg = msg.replace(fragment, REDACTED)
    return msg


def _redact_error(error: Mapping[str, Any]) -> dict[str, Any]:
    raw_ctx = error.get("ctx")
    ctx: Mapping[str, Any] = raw_ctx if isinstance(raw_ctx, Mapping) else {}
    # A built-in message is rendered from its ctx, so it quotes input only through
    # an input-derived key. A custom error's message and ctx are the author's own:
    # nothing says which of its keys hold input, so none are kept.
    builtin = error.get("type") in _BUILTIN_ERROR_TYPES
    msg = str(error.get("msg", ""))
    if not builtin or any(key not in _SCHEMA_CTX_KEYS for key in ctx):
        msg = _scrub_msg(msg, error.get("input"))
    kept_ctx = {key: value for key, value in ctx.items() if key in _SCHEMA_CTX_KEYS} if builtin else {}
    return {
        "type": error.get("type"),
        "loc": error.get("loc", ()),
        "msg": msg,
        **({"ctx": kept_ctx} if kept_ctx else {}),
    }


def redact_validation_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return copies of pydantic error entries without the values the caller submitted."""
    return [_redact_error(error) for error in errors]


async def request_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Drop-in for FastAPI's default handler: same status and shape, no submitted values."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(redact_validation_errors(exc.errors()))},
    )
