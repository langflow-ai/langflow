"""Reading the engine's arguments and writing its results, as the Rust binding does.

An argument that is ``bytes`` is UTF-8 JSON text. Any other argument is the
JSON value itself (dict, list, tuple, str, int, float, bool or None), read
with the limits of the JSON parser: at most 127 levels deep, no lone
surrogate, and finite numbers. A ``str`` is a JSON string, never text to
parse. A value that breaks a limit is refused as an invalid graph, with the
same error as text that does not parse; a key that is not a ``str``, or a
value of another type, is a ``TypeError``.

Text with a number too large for a double, such as ``1e400``, is refused as
a ``float`` that is not finite is, for a graph the engine holds or changes
(``finite=True``) and for operations. Validation and repair read it, to
report it and to write ``null`` in its place.

Reading a value copies it, so the engine never shares a container with its
caller: a later change to the argument cannot change the engine's graph, and
a change to a result cannot either. Results are copied out the same way.
"""

from __future__ import annotations

import json
import re
from json.encoder import encode_basestring_ascii as _ascii_string
from typing import Any, NoReturn

import orjson

from lfx.services.flow_operations.exceptions import FlowDataValidationError, FlowOperationValidationError

MAX_DEPTH = 127
_SURROGATE = re.compile("[\ud800-\udfff]")
# orjson reads an integer outside the 64-bit range as a float, which loses its digits. Such a
# float is at least this large, so text that gives one is read again by ``json``.
_U64_LIMIT = 2.0**64
_I64_LIMIT = -(2.0**63)


NOT_FINITE = "NaN and Infinity are not JSON numbers"


def _not_json(why: str) -> FlowDataValidationError:
    return FlowDataValidationError(f"flow data is not valid JSON: {why}")


def _refuse(why: str) -> NoReturn:
    raise _not_json(why)


def _reject_constant(token: str) -> NoReturn:
    msg = f"{token} is not valid JSON"
    raise ValueError(msg)


def _scalar_problem(value: Any, *, finite: bool) -> str | None:
    """The limit a string or number parsed from text breaks, or None."""
    cls = value.__class__
    if cls is str:
        if not value.isascii() and _SURROGATE.search(value):
            return "a string holds a lone surrogate"
    elif finite and cls is float and value - value != 0.0:
        return NOT_FINITE
    return None


def _check_text_value(value: Any, *, finite: bool) -> str | None:
    """The limit a value parsed from text breaks, or None. With ``finite``, a number too large for a double
    (read as a float that is not finite) breaks one.
    """  # noqa: D205
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        cls = item.__class__
        if cls is not dict and cls is not list:
            problem = _scalar_problem(item, finite=finite)
            if problem is not None:
                return problem
            continue
        if depth >= MAX_DEPTH:
            return f"nested more than {MAX_DEPTH} levels deep"
        if cls is dict:
            for key in item:
                if not key.isascii() and _SURROGATE.search(key):
                    return "a string holds a lone surrogate"
            children = item.values()
        else:
            children = item
        for child in children:
            child_cls = child.__class__
            if child_cls is dict or child_cls is list:
                stack.append((child, depth + 1))
            else:
                problem = _scalar_problem(child, finite=finite)
                if problem is not None:
                    return problem
    return None


def parse_text(text: bytes, *, finite: bool = False) -> Any:
    """Parse JSON text strictly: no ``NaN`` or ``Infinity`` token, within the limits. Raises ``ValueError``.

    With ``finite``, a number too large for a double, such as ``1e400``, is refused too.
    """
    try:
        value = orjson.loads(text)
    except orjson.JSONDecodeError:
        pass
    else:
        # orjson refuses a lone surrogate and NaN; the depth, and a lost integer, are left to check.
        found = _depth_and_large_floats(value)
        if found is _TOO_DEEP:
            msg = f"nested more than {MAX_DEPTH} levels deep"
            raise ValueError(msg)
        if found is None:
            return value
    # orjson reads a number too large for a double as inf, which goes this way as a large float.
    value = json.loads(text.decode("utf-8"), parse_constant=_reject_constant)
    broken = _check_text_value(value, finite=finite)
    if broken is not None:
        raise ValueError(broken)
    return value


_TOO_DEEP = object()
_LARGE_FLOAT = object()


def _depth_and_large_floats(value: Any) -> object | None:
    """``_TOO_DEEP`` for a value nested more than ``MAX_DEPTH`` levels deep, ``_LARGE_FLOAT`` for one that holds
    a float outside the 64-bit integer range, which may have been an integer, or None.
    """  # noqa: D205
    if value.__class__ is not dict and value.__class__ is not list:
        return _LARGE_FLOAT if value.__class__ is float and not _I64_LIMIT <= value < _U64_LIMIT else None
    large = False
    stack = [(value, 0)]
    pop, push = stack.pop, stack.append
    while stack:
        item, depth = pop()
        if depth >= MAX_DEPTH:
            return _TOO_DEEP
        for child in item.values() if item.__class__ is dict else item:
            cls = child.__class__
            if cls is dict or cls is list:
                push((child, depth + 1))
            elif cls is float and not _I64_LIMIT <= child < _U64_LIMIT:
                large = True
    return _LARGE_FLOAT if large else None


def read_data(value: Any, *, finite: bool = False) -> Any:
    """A graph, or any other value the engine reads as data: an invalid graph error when it is not JSON.

    With ``finite``, for a graph the engine holds or changes, text with a number too large for a double is
    refused too.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return parse_text(bytes(value), finite=finite)
        except (ValueError, RecursionError, UnicodeDecodeError) as error:
            raise _not_json(str(error)) from None
    return read_value(value)


def read_operations(value: Any) -> Any:
    """A list of operations, before it is parsed: invalid operations when its text is not JSON or holds a number
    too large for a double.
    """  # noqa: D205
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return parse_text(bytes(value), finite=True)
        except (ValueError, RecursionError, UnicodeDecodeError) as error:
            msg = f"operations are not valid JSON: {error}"
            raise FlowOperationValidationError(msg) from None
    return read_value(value)


def read_value(value: Any, depth: int = 0) -> Any:
    """A copy of a Python value read as JSON, with the limits of the JSON parser."""
    cls = value.__class__
    if cls is dict:
        if depth >= MAX_DEPTH:
            _refuse(f"nested more than {MAX_DEPTH} levels deep")
        out = {}
        child_depth = depth + 1
        for key, item in value.items():
            if key.__class__ is not str:
                key = _key(key)  # noqa: PLW2901
            elif not key.isascii() and _SURROGATE.search(key):
                _refuse("a string holds a lone surrogate")
            item_cls = item.__class__
            if item_cls is str:
                if not item.isascii() and _SURROGATE.search(item):
                    _refuse("a string holds a lone surrogate")
                out[key] = item
            elif item_cls is int or item_cls is bool or item is None:
                out[key] = item
            elif item_cls is float:
                if item - item != 0.0:
                    _refuse("NaN and Infinity are not JSON numbers")
                out[key] = item
            else:
                out[key] = read_value(item, child_depth)
        return out
    if cls is list or cls is tuple:
        if depth >= MAX_DEPTH:
            _refuse(f"nested more than {MAX_DEPTH} levels deep")
        return [read_value(item, depth + 1) for item in value]
    if cls is str:
        if not value.isascii() and _SURROGATE.search(value):
            _refuse("a string holds a lone surrogate")
        return value
    if cls is int or cls is bool or value is None:
        return value
    if cls is float:
        if value - value != 0.0:
            _refuse("NaN and Infinity are not JSON numbers")
        return value
    return _read_subclass(value, depth)


def _key(key: Any) -> str:
    if not isinstance(key, str):
        msg = "a JSON object's keys must be str"
        raise TypeError(msg)
    key = str(key)
    if not key.isascii() and _SURROGATE.search(key):
        _refuse("a string holds a lone surrogate")
    return key


def _read_subclass(value: Any, depth: int) -> Any:
    """A value of a subclass of a JSON type, read as that type."""
    if isinstance(value, str):
        return read_value(str(value), depth)
    if isinstance(value, dict):
        return read_value(dict(value), depth)
    if isinstance(value, (list, tuple)):
        return read_value(list(value), depth)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return read_value(float(value), depth)
    msg = f"{type(value).__name__} is not a JSON value"
    raise TypeError(msg)


def copy_json(value: Any) -> Any:
    """A copy of a JSON value that shares no container with it. Strings and numbers cannot change: they are shared."""
    cls = value.__class__
    if cls is dict:
        out = {}
        for key, item in value.items():
            item_cls = item.__class__
            if item_cls is dict or item_cls is list:
                out[key] = copy_json(item)
            else:
                out[key] = item
        return out
    if cls is list:
        return [copy_json(item) if item.__class__ is dict or item.__class__ is list else item for item in value]
    return value


# --- Writing JSON text -----------------------------------------------------------------------
#
# The engine writes the text the Rust engine writes: no spaces, and ASCII only, every other
# character escaped as ``\uXXXX`` in lower-case hex (a pair of escapes above U+FFFF), as
# ``json.dumps`` writes by default and as stored flows hold it. orjson writes everything else as
# the Rust engine does (numbers, and the escapes of quotes, backslashes and control characters),
# but writes other characters as UTF-8. So orjson writes each node, edge and other top-level value,
# and the text of one that is not ASCII is encoded again as ASCII with ``backslashreplace``, which
# writes ``\uXXXX`` for a character from U+0100 to U+FFFF. Every edge holds such characters (each
# handle holds ``œ``), and many nodes do. A character below U+0100 or above U+FFFF, which
# ``backslashreplace`` writes in another form, is escaped first. This is faster than
# ``json.dumps``, which also writes some floats in another form (``1e-07`` for ``1e-7``), and
# faster than escaping each string that is not ASCII before orjson writes it, or escaping with a
# regular expression.

_U64_END = 2**64
_I64_START = -(2**63)
_ASCII_BYTES = bytes(range(128))
# The first bytes of the UTF-8 of a character from U+0080 to U+00FF, and above U+FFFF: no other
# byte of UTF-8 has these values.
_OTHER_LEADS = (b"\xc2", b"\xc3", b"\xf0", b"\xf1", b"\xf2", b"\xf3", b"\xf4")
# Up to this many characters are escaped by one pass each; more by one ``translate``, which reads
# every character more slowly.
_REPLACES = 16


def _with_big_ints(value: Any) -> Any:
    """``value`` with each integer of more than 64 bits, which orjson does not write, as a ``Fragment`` of its
    digits.
    """  # noqa: D205
    cls = value.__class__
    if cls is dict:
        return {key: _with_big_ints(item) for key, item in value.items()}
    if cls is list:
        return [_with_big_ints(item) for item in value]
    if cls is int and not _I64_START <= value < _U64_END:
        return orjson.Fragment(str(value).encode("ascii"))
    return value


def _piece(value: Any) -> bytes:
    """One value as ASCII JSON text."""
    try:
        data = orjson.dumps(value)
    except TypeError:
        data = orjson.dumps(_with_big_ints(value))
    if data.isascii():
        return data
    text = data.decode("utf-8")
    if any(lead in data for lead in _OTHER_LEADS):
        others = {
            character: _ascii_string(character)[1:-1]
            for character in set(data.translate(None, _ASCII_BYTES).decode("utf-8"))
            if character < "\u0100" or character > "\uffff"
        }
        if len(others) <= _REPLACES:
            for character, escape in others.items():
                text = text.replace(character, escape)
        else:
            text = text.translate({ord(character): escape for character, escape in others.items()})
    return text.encode("ascii", "backslashreplace")


def dump_bytes(value: Any) -> bytes:
    """JSON text of a value the engine holds, as the Rust engine writes it, as ASCII ``bytes``."""
    if value.__class__ is not dict:
        return _piece(value)
    # A graph's nodes and edges are written one by one, so only those that are not ASCII are encoded again. The
    # pieces are joined once: each join of a large graph's text copies all of it.
    parts: list[bytes] = []
    append = parts.append
    for key, item in value.items():
        append(b"," if parts else b"{")
        append(_piece(key))
        append(b":")
        if item.__class__ is list:
            append(b"[")
            for index, entry in enumerate(item):
                if index:
                    append(b",")
                append(_piece(entry))
            append(b"]")
        else:
            append(_piece(item))
    append(b"}" if parts else b"{}")
    return b"".join(parts)


def dumps(value: Any) -> str:
    """JSON text of a value the engine holds, as the Rust engine writes it: the same characters."""
    return dump_bytes(value).decode("ascii")
