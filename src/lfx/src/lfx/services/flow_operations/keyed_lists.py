"""Keyed lists, indexed by item key for one apply call.

Outputs, tool actions and table rows are lists whose items carry a key: an
output's ``name``, a tool action's first tag, a row's ``_id``. A write finds
its item through an index instead of scanning the list, and building the index
checks the list once: every item has a key, no key repeats, and table rows
carry a numeric ``_pos`` and are stored in ``(_pos, _id)`` order.

A table row moves by writing its ``_pos``; the index puts it back in order
with a binary search. Natural lists keep the order writes leave them in.
"""

from __future__ import annotations

import math
from bisect import bisect_left, insort
from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.canonical import utf16_sort_key
from lfx.services.flow_operations.exceptions import FlowOperationValidationError

if TYPE_CHECKING:
    from lfx.services.flow_operations.schema import KeyedList

RowOrder = tuple[float, bytes]


class ListIndex:
    """The items of one keyed list by key, and for a table, its rows' order."""

    __slots__ = ("by_key", "items", "keyed")

    def __init__(self, keyed: KeyedList, items: list[Any], *, context: str) -> None:
        self.keyed = keyed
        self.items = items
        self.by_key: dict[str, dict[str, Any]] = {}
        previous: RowOrder | None = None
        for item in items:
            key = self.require_key(item, context=context)
            if key in self.by_key:
                msg = f"{context}: two items have the key {key!r}"
                raise FlowOperationValidationError(msg)
            self.by_key[key] = item
            if keyed.kind == "table":
                order = self.order(item, context=context)
                if previous is not None and order < previous:
                    msg = f"{context}: table rows must be in ({keyed.position}, {keyed.key[0]}) order"
                    raise FlowOperationValidationError(msg)
                previous = order

    def require_key(self, item: Any, *, context: str) -> str:
        key = self.keyed.key_of(item)
        if not key:
            msg = f"{context}: every item of this list needs a non-empty string {self.keyed.selector_name}"
            raise FlowOperationValidationError(msg)
        return key

    def order(self, row: dict[str, Any], *, context: str) -> RowOrder:
        """Return a table row's place: its numeric ``_pos``, then its ``_id`` in UTF-16 order, as JavaScript sorts."""
        position = row.get(self.keyed.position)
        if isinstance(position, bool) or not isinstance(position, (int, float)) or not math.isfinite(position):
            msg = f"{context}: a table row's {self.keyed.position} must be a finite number"
            raise FlowOperationValidationError(msg)
        # Compared as doubles, as JavaScript holds them, so both engines order rows alike.
        return float(position), utf16_sort_key(row[self.keyed.key[0]])

    def add(self, item: dict[str, Any], *, context: str) -> None:
        """Add an item whose key is not in the list yet."""
        self.by_key[self.require_key(item, context=context)] = item
        if self.keyed.kind == "table":
            insort(self.items, item, key=lambda row: self.order(row, context=context))
        else:
            self.items.append(item)

    def remove(self, key: str, *, context: str) -> dict[str, Any]:
        """Remove the item with ``key``, which must exist, and return it."""
        item = self.by_key.pop(key)
        del self.items[self._position(item, self.order(item, context=context) if self.keyed.kind == "table" else None)]
        return item

    def replace(self, key: str, item: dict[str, Any], *, context: str) -> dict[str, Any]:
        """Replace the item with ``key`` by ``item``, which carries the same key, and return the old item."""
        old = self.by_key[key]
        if self.keyed.kind == "table":
            self.remove(key, context=context)
            self.add(item, context=context)
            return old
        self.items[self._position(old, None)] = item
        self.by_key[key] = item
        return old

    def reorder(self, row: dict[str, Any], before: RowOrder, *, context: str) -> None:
        """Put a table row whose ``_pos`` changed from ``before`` back in order."""
        if self.order(row, context=context) == before:
            return
        del self.items[self._position(row, before)]
        insort(self.items, row, key=lambda item: self.order(item, context=context))

    def _position(self, item: dict[str, Any], order: RowOrder | None) -> int:
        """Return where ``item`` is: by binary search on its order in a table, by identity in a natural list."""
        if order is not None:
            position = bisect_left(self.items, order, key=lambda row: self.order(row, context=""))
        else:
            # Natural lists are short (a component's outputs or tool actions).
            position = next(index for index, candidate in enumerate(self.items) if candidate is item)
        if self.items[position] is not item:
            msg = "keyed list index is out of step with its list"
            raise RuntimeError(msg)
        return position
