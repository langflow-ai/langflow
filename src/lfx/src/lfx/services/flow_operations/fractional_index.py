"""Fractional positions: string keys that sort between any two others.

A port of David Greenspan's fractional indexing scheme as published by
rocicorp (``fractional-indexing``, CC0), unchanged so that the editor's
TypeScript copy generates the same keys. Table rows store one of these keys
in ``_pos``; moving a row writes a new key between its new neighbours.

A key is an integer part followed by a fraction. The integer part's first
character encodes its length: ``a``..``z`` for non-negative integers of 1 to
26 digits, ``A``..``Z`` for negative ones. Digits are base 62, ``0-9A-Za-z``
in ASCII order, so keys compare correctly as plain strings, and a fraction
never ends in ``0``.
"""

from __future__ import annotations

BASE_62_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


class FractionalIndexError(ValueError):
    """Raised for keys outside the scheme or bounds that are out of order."""


def _midpoint(a: str, b: str | None, digits: str) -> str:
    """Return a fraction strictly between ``a`` and ``b``.

    ``a`` may be empty; ``b`` is None (no upper bound) or non-empty, and
    ``a < b`` when it is given. Neither may end in a zero digit.
    """
    zero = digits[0]
    if b is not None and a >= b:
        msg = f"{a} >= {b}"
        raise FractionalIndexError(msg)
    if a[-1:] == zero or (b and b[-1:] == zero):
        msg = "trailing zero"
        raise FractionalIndexError(msg)
    if b:
        # Remove the longest common prefix, padding `a` with zeros as we go;
        # `b` cannot end before `a` while they share a prefix.
        n = 0
        while (a[n] if n < len(a) else zero) == (b[n] if n < len(b) else None):
            n += 1
        if n > 0:
            return b[:n] + _midpoint(a[n:], b[n:], digits)
    # The first digits (or the lack of one) differ.
    digit_a = digits.index(a[0]) if a else 0
    digit_b = digits.index(b[0]) if b is not None else len(digits)
    if digit_b - digit_a > 1:
        # Math.round(0.5 * (digit_a + digit_b)) in the reference: halves round up.
        return digits[(digit_a + digit_b + 1) // 2]
    # The first digits are consecutive.
    if b and len(b) > 1:
        return b[:1]
    # `b` is None or a single digit: keep `a`'s first digit and look for a
    # midpoint after it, e.g. midpoint("49", "5") is "4" + midpoint("9", None).
    return digits[digit_a] + _midpoint(a[1:], None, digits)


def _integer_length(head: str) -> int:
    if "a" <= head <= "z":
        return ord(head) - ord("a") + 2
    if "A" <= head <= "Z":
        return ord("Z") - ord(head) + 2
    msg = f"invalid order key head: {head}"
    raise FractionalIndexError(msg)


def _validate_integer(integer: str) -> None:
    if len(integer) != _integer_length(integer[0]):
        msg = f"invalid integer part of order key: {integer}"
        raise FractionalIndexError(msg)


def _integer_part(key: str) -> str:
    length = _integer_length(key[0])
    if length > len(key):
        msg = f"invalid order key: {key}"
        raise FractionalIndexError(msg)
    return key[:length]


def validate_order_key(key: str, digits: str = BASE_62_DIGITS) -> None:
    """Raise ``FractionalIndexError`` unless ``key`` is a key of the scheme."""
    if not isinstance(key, str) or not key:
        msg = f"invalid order key: {key!r}"
        raise FractionalIndexError(msg)
    if key == "A" + digits[0] * 26:
        msg = f"invalid order key: {key}"
        raise FractionalIndexError(msg)
    integer = _integer_part(key)
    fraction = key[len(integer) :]
    if fraction[-1:] == digits[0]:
        msg = f"invalid order key: {key}"
        raise FractionalIndexError(msg)


def is_order_key(key: object, digits: str = BASE_62_DIGITS) -> bool:
    """Return whether ``key`` is a valid key of the scheme."""
    try:
        validate_order_key(key, digits)  # type: ignore[arg-type]
    except FractionalIndexError:
        return False
    return True


def _increment_integer(integer: str, digits: str) -> str | None:
    """Return the next integer part, or None past the largest one."""
    _validate_integer(integer)
    head, digs = integer[0], list(integer[1:])
    carry = True
    i = len(digs) - 1
    while carry and i >= 0:
        d = digits.index(digs[i]) + 1
        if d == len(digits):
            digs[i] = digits[0]
        else:
            digs[i] = digits[d]
            carry = False
        i -= 1
    if not carry:
        return head + "".join(digs)
    if head == "Z":
        return "a" + digits[0]
    if head == "z":
        return None
    next_head = chr(ord(head) + 1)
    if next_head > "a":
        digs.append(digits[0])
    else:
        digs.pop()
    return next_head + "".join(digs)


def _decrement_integer(integer: str, digits: str) -> str | None:
    """Return the previous integer part, or None before the smallest one."""
    _validate_integer(integer)
    head, digs = integer[0], list(integer[1:])
    borrow = True
    i = len(digs) - 1
    while borrow and i >= 0:
        d = digits.index(digs[i]) - 1
        if d == -1:
            digs[i] = digits[-1]
        else:
            digs[i] = digits[d]
            borrow = False
        i -= 1
    if not borrow:
        return head + "".join(digs)
    if head == "a":
        return "Z" + digits[-1]
    if head == "A":
        return None
    previous_head = chr(ord(head) - 1)
    if previous_head < "Z":
        digs.append(digits[-1])
    else:
        digs.pop()
    return previous_head + "".join(digs)


def generate_key_between(a: str | None, b: str | None, digits: str = BASE_62_DIGITS) -> str:
    """Return a key strictly between ``a`` and ``b``; None stands for the start or the end."""
    if a is not None:
        validate_order_key(a, digits)
    if b is not None:
        validate_order_key(b, digits)
    if a is not None and b is not None and a >= b:
        msg = f"{a} >= {b}"
        raise FractionalIndexError(msg)

    if a is None:
        if b is None:
            return "a" + digits[0]
        integer_b = _integer_part(b)
        fraction_b = b[len(integer_b) :]
        if integer_b == "A" + digits[0] * 26:
            return integer_b + _midpoint("", fraction_b, digits)
        if integer_b < b:
            return integer_b
        result = _decrement_integer(integer_b, digits)
        if result is None:
            msg = "cannot decrement any more"
            raise FractionalIndexError(msg)
        return result

    if b is None:
        integer_a = _integer_part(a)
        fraction_a = a[len(integer_a) :]
        incremented = _increment_integer(integer_a, digits)
        return integer_a + _midpoint(fraction_a, None, digits) if incremented is None else incremented

    integer_a = _integer_part(a)
    fraction_a = a[len(integer_a) :]
    integer_b = _integer_part(b)
    fraction_b = b[len(integer_b) :]
    if integer_a == integer_b:
        return integer_a + _midpoint(fraction_a, fraction_b, digits)
    incremented = _increment_integer(integer_a, digits)
    if incremented is None:
        msg = "cannot increment any more"
        raise FractionalIndexError(msg)
    if incremented < b:
        return incremented
    return integer_a + _midpoint(fraction_a, None, digits)


def generate_n_keys_between(a: str | None, b: str | None, n: int, digits: str = BASE_62_DIGITS) -> list[str]:
    """Return ``n`` distinct sorted keys between ``a`` and ``b``.

    With both ends None the keys are ``a0, a1, ...``; with one end None they
    are consecutive integers; otherwise they are short keys spread between
    the two.
    """
    if n == 0:
        return []
    if n == 1:
        return [generate_key_between(a, b, digits)]
    if b is None:
        key = generate_key_between(a, b, digits)
        result = [key]
        for _ in range(n - 1):
            key = generate_key_between(key, b, digits)
            result.append(key)
        return result
    if a is None:
        key = generate_key_between(a, b, digits)
        result = [key]
        for _ in range(n - 1):
            key = generate_key_between(a, key, digits)
            result.append(key)
        result.reverse()
        return result
    mid = n // 2
    key = generate_key_between(a, b, digits)
    return [
        *generate_n_keys_between(a, key, mid, digits),
        key,
        *generate_n_keys_between(key, b, n - mid - 1, digits),
    ]


__all__ = [
    "BASE_62_DIGITS",
    "FractionalIndexError",
    "generate_key_between",
    "generate_n_keys_between",
    "is_order_key",
    "validate_order_key",
]
