"""Decode legacy index dictionaries as data, without a pickle VM or imports.

Rust Chroma writes a dictionary. Older Python Chroma wraps that dictionary in
PersistentData. The only supported object opcode is that inert wrapper. No
constructor, callable, extension, persistent ID, or reducer is executed.
"""

from __future__ import annotations

import pickletools
from dataclasses import dataclass
from typing import Any

from lfx.base.knowledge_bases.migration.protocol import AutomaticMigrationLimitError, MigrationProtocolError

MAX_INDEX_METADATA_BYTES = 32 * 1024 * 1024
_MAX_OPERATIONS = 4_000_000
_MAX_STACK = 2_000_000
_MARK = object()
_CLASS = object()
_PERSISTENT_DATA = "chromadb.segment.impl.vector.local_persistent_hnsw PersistentData"


@dataclass
class _Wrapper:
    state: dict | None = None


def read_index_metadata(payload: bytes) -> dict[str, Any]:
    """Read a bounded index dictionary and reject every executable pickle opcode."""
    if len(payload) > MAX_INDEX_METADATA_BYTES:
        msg = "Legacy index metadata exceeds the automatic migration limit"
        raise AutomaticMigrationLimitError(msg)
    stack: list = []
    memo: dict = {}

    def marked() -> list:
        """Pop values through the last pickle marker without constructing objects."""
        items = []
        while stack and stack[-1] is not _MARK:
            items.append(stack.pop())
        if not stack:
            raise ValueError
        stack.pop()
        return items[::-1]

    try:
        for count, (opcode, argument, position) in enumerate(pickletools.genops(payload)):
            if count > _MAX_OPERATIONS or len(stack) > _MAX_STACK or len(memo) > _MAX_STACK:
                msg = "Legacy index metadata exceeds automatic reader resource limits"
                raise AutomaticMigrationLimitError(msg)
            name = opcode.name
            if name == "PROTO":
                if argument not in (2, 3, 4, 5):
                    raise ValueError
            elif name == "FRAME":
                if argument > len(payload) - position - 9:
                    raise ValueError
            elif name == "MARK":
                stack.append(_MARK)
            elif name == "NONE":
                stack.append(None)
            elif name in ("BININT", "BININT1", "BININT2", "LONG1", "LONG4", "INT", "LONG") or name in (
                "BINUNICODE",
                "SHORT_BINUNICODE",
                "BINUNICODE8",
                "UNICODE",
            ):
                stack.append(argument)
            elif name == "EMPTY_DICT":
                stack.append({})
            elif name == "EMPTY_TUPLE":
                stack.append(())
            elif name == "SETITEMS":
                items = marked()
                if type(stack[-1]) is not dict or len(items) % 2:
                    raise ValueError
                for key, value in zip(items[::2], items[1::2], strict=True):
                    if not _valid_key(key) or key in stack[-1]:
                        raise ValueError
                    stack[-1][key] = value
            elif name == "SETITEM":
                value, key = stack.pop(), stack.pop()
                if type(stack[-1]) is not dict or not _valid_key(key) or key in stack[-1]:
                    raise ValueError
                stack[-1][key] = value
            elif name in ("BINPUT", "LONG_BINPUT", "PUT", "MEMOIZE"):
                index = len(memo) if name == "MEMOIZE" else argument
                if index in memo or not 0 <= index <= _MAX_STACK:
                    raise ValueError
                memo[index] = stack[-1]
            elif name in ("BINGET", "LONG_BINGET", "GET"):
                stack.append(memo[argument])
            elif name == "GLOBAL":
                if argument != _PERSISTENT_DATA:
                    raise ValueError
                stack.append(_CLASS)
            elif name == "STACK_GLOBAL":
                class_name, module = stack.pop(), stack.pop()
                if (
                    type(module) is not str
                    or type(class_name) is not str
                    or f"{module} {class_name}" != _PERSISTENT_DATA
                ):
                    raise ValueError
                stack.append(_CLASS)
            elif name == "NEWOBJ":
                arguments, target = stack.pop(), stack.pop()
                if target is not _CLASS or arguments != ():
                    raise ValueError
                stack.append(_Wrapper())
            elif name == "BUILD":
                state = stack.pop()
                if not isinstance(stack[-1], _Wrapper) or type(state) is not dict:
                    raise ValueError
                stack[-1].state = state
            elif name == "STOP":
                if position != len(payload) - 1 or len(stack) != 1:
                    raise ValueError
                result = stack[0].state if isinstance(stack[0], _Wrapper) else stack[0]
                if type(result) is not dict:
                    raise ValueError
                return result
            else:
                raise ValueError
    except AutomaticMigrationLimitError:
        raise
    except (ValueError, KeyError, IndexError, TypeError, OverflowError) as exc:
        msg = "Legacy index metadata is damaged or uses an unsupported format"
        raise MigrationProtocolError(msg) from exc
    msg = "Legacy index metadata has no completion marker"
    raise MigrationProtocolError(msg)


def _valid_key(key: Any) -> bool:
    """Bound native label keys before hashing to prevent integer collision attacks."""
    return type(key) is str or (type(key) is int and 0 <= key < 2**64)
