"""Reading the engine's arguments and writing its results, as the Rust binding does.

An argument that is ``bytes`` is UTF-8 JSON text. Any other argument is the
JSON value itself (dict, list, tuple, str, int, float, bool or None), read
with the limits of the JSON parser: at most 127 levels deep, no lone
surrogate, and finite numbers. A ``str`` is a JSON string, never text to
parse. A value that breaks a limit is refused as an invalid graph, with the
same error as text that does not parse; a key that is not a ``str``, or a
value of another type, is a ``TypeError``.

Reading a value copies it, so the engine never shares a container with its
caller: a later change to the argument cannot change the engine's graph, and
a change to a result cannot either. Results are copied out the same way.
"""

from __future__ import annotations

import json
import re
from typing import Any, NoReturn

import orjson

from lfx.services.flow_operations.exceptions import FlowDataValidationError, FlowOperationValidationError

MAX_DEPTH = 127
_SURROGATE = re.compile("[\ud800-\udfff]")
# orjson reads an integer of more than 64 bits as a float, which loses its digits.
_LONG_INTEGER = re.compile(rb"[0-9]{19,}")


def _not_json(why: str) -> FlowDataValidationError:
    return FlowDataValidationError(f"flow data is not valid JSON: {why}")


def _refuse(why: str) -> NoReturn:
    raise _not_json(why)


def _reject_constant(token: str) -> NoReturn:
    msg = f"{token} is not valid JSON"
    raise ValueError(msg)


def _check_text_value(value: Any) -> str | None:
    """The limit a value parsed from text breaks, or None. Text never holds a non-finite number."""
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        cls = item.__class__
        if cls is dict:
            if depth >= MAX_DEPTH:
                return f"nested more than {MAX_DEPTH} levels deep"
            for key, child in item.items():
                if not key.isascii() and _SURROGATE.search(key):
                    return "a string holds a lone surrogate"
                child_cls = child.__class__
                if child_cls is dict or child_cls is list:
                    stack.append((child, depth + 1))
                elif child_cls is str and not child.isascii() and _SURROGATE.search(child):
                    return "a string holds a lone surrogate"
        elif cls is list:
            if depth >= MAX_DEPTH:
                return f"nested more than {MAX_DEPTH} levels deep"
            for child in item:
                child_cls = child.__class__
                if child_cls is dict or child_cls is list:
                    stack.append((child, depth + 1))
                elif child_cls is str and not child.isascii() and _SURROGATE.search(child):
                    return "a string holds a lone surrogate"
        elif cls is str and not item.isascii() and _SURROGATE.search(item):
            return "a string holds a lone surrogate"
    return None


def parse_text(text: bytes) -> Any:
    """Parse JSON text strictly: no ``NaN`` or ``Infinity`` token, within the limits. Raises ``ValueError``."""
    if _LONG_INTEGER.search(text) is None:
        try:
            value = orjson.loads(text)
        except orjson.JSONDecodeError:
            value = _SLOW
    else:
        value = _SLOW
    if value is _SLOW:
        value = json.loads(text.decode("utf-8"), parse_constant=_reject_constant)
    broken = _check_text_value(value)
    if broken is not None:
        raise ValueError(broken)
    return value


_SLOW = object()


def read_data(value: Any) -> Any:
    """A graph, or any other value the engine reads as data: an invalid graph error when it is not JSON."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return parse_text(bytes(value))
        except (ValueError, RecursionError, UnicodeDecodeError) as error:
            raise _not_json(str(error)) from None
    return read_value(value)


def read_operations(value: Any) -> Any:
    """A list of operations, before it is parsed: invalid operations when its text is not JSON."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return parse_text(bytes(value))
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


def dumps(value: Any) -> str:
    """JSON text of a value the engine holds."""
    try:
        return orjson.dumps(value).decode("utf-8")
    except TypeError:
        # An integer of more than 64 bits keeps its digits.
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
