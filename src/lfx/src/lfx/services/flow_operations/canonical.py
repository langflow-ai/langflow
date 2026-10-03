"""Canonical JSON values, for comparing what a write expects with what is stored.

Two values are equal when their canonical forms are byte-identical. The form is
RFC 8785 (JSON Canonicalization Scheme): object keys are sorted and numbers are
printed the way JavaScript prints them, so ``1`` and ``1.0`` are the same
value, ``true`` and ``1`` are not, and key order is never a difference.
JavaScript cannot tell integers from floats, so a ``0.0`` that comes back from
the editor as ``0`` must compare equal.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Any

from lfx.services.flow_operations.exceptions import FlowDataValidationError

# Largest integer a JavaScript number holds exactly. Larger integers are
# printed as the double the editor would round them to.
_MAX_SAFE_INTEGER = 2**53
# ECMAScript prints numbers below 1e21 in plain notation.
_MAX_PLAIN_EXPONENT = 21
_MIN_PLAIN_EXPONENT = -6


def json_type(value: Any) -> str:
    """Return the JSON type of a Python value: object, array, string, number, boolean or null."""
    # bool is a subclass of int, so it must be checked first.
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    msg = f"value of type {type(value).__name__} is not JSON"
    raise FlowDataValidationError(msg)


def is_finite_json_number(value: Any) -> bool:
    """Return False for NaN and the infinities, which JSON cannot represent."""
    return not isinstance(value, float) or math.isfinite(value)


def _format_number(value: float) -> str:
    if isinstance(value, int):
        if abs(value) <= _MAX_SAFE_INTEGER:
            return str(value)
        value = float(value)
    if not math.isfinite(value):
        msg = "NaN and Infinity are not valid JSON numbers"
        raise FlowDataValidationError(msg)
    if value == 0:
        return "0"

    # repr() gives the shortest digits that round-trip, which is also what
    # ECMAScript's Number::toString chooses; only the layout differs.
    sign = "-" if value < 0 else ""
    _, digit_tuple, exponent = Decimal(repr(abs(value))).as_tuple()
    digits = "".join(str(digit) for digit in digit_tuple).rstrip("0")
    exponent += len(digit_tuple) - len(digits)
    digits = digits.lstrip("0")
    k = len(digits)
    n = k + exponent  # value == 0.<digits> * 10**n

    if k <= n <= _MAX_PLAIN_EXPONENT:
        return sign + digits + "0" * (n - k)
    if 0 < n <= _MAX_PLAIN_EXPONENT:
        return sign + digits[:n] + "." + digits[n:]
    if _MIN_PLAIN_EXPONENT < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{sign}{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"


def utf16_sort_key(value: str) -> bytes:
    """Order strings by UTF-16 code units, the order JavaScript's default sort uses."""
    return value.encode("utf-16-be", "surrogatepass")


def _write_canonical(value: Any, parts: list[str]) -> None:
    if value is None:
        parts.append("null")
    elif value is True:
        parts.append("true")
    elif value is False:
        parts.append("false")
    elif isinstance(value, (int, float)):
        parts.append(_format_number(value))
    elif isinstance(value, str):
        parts.append(json.dumps(value, ensure_ascii=False))
    elif isinstance(value, list):
        parts.append("[")
        for index, item in enumerate(value):
            if index:
                parts.append(",")
            _write_canonical(item, parts)
        parts.append("]")
    elif isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                msg = f"object key {key!r} is not a string"
                raise FlowDataValidationError(msg)
        parts.append("{")
        for index, key in enumerate(sorted(value, key=utf16_sort_key)):
            if index:
                parts.append(",")
            parts.append(json.dumps(key, ensure_ascii=False))
            parts.append(":")
            _write_canonical(value[key], parts)
        parts.append("}")
    else:
        json_type(value)  # raises for anything that is not JSON


def canonical_json(value: Any) -> str:
    """Serialize a JSON value in RFC 8785 canonical form."""
    parts: list[str] = []
    _write_canonical(value, parts)
    return "".join(parts)


def values_equal(left: Any, right: Any) -> bool:
    """Return whether two JSON values are equal under canonical comparison."""
    if left is right:
        return True
    left_type = json_type(left)
    if left_type != json_type(right):
        return False
    if left_type in {"string", "boolean", "null"}:
        return left == right
    return canonical_json(left) == canonical_json(right)
