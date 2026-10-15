"""Keyed lists, indexed by item key for one apply call.

Outputs, tool actions and table rows are lists whose items carry a key: an
output's ``name``, a tool action's first tag, a row's ``_id``. A write finds
its item through an index instead of scanning the list, and building the index
checks the list once: every item has a key, no key repeats, and every table
row carries a numeric ``_pos``.

Natural lists keep the order writes leave them in. A table's order is its
rows' ``(_pos, _id)``, not their places in the array: readers sort rows when
they strip the row keys, so the engine never sorts a table. A new row is
appended, and a deleted row's slot is taken by the last row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.canonical import is_finite_number
from lfx.services.flow_operations.exceptions import FlowOperationValidationError

if TYPE_CHECKING:
    from lfx.services.flow_operations.schema import KeyedList


class ListIndex:
    """The items of one keyed list by key, and for a table, each row's slot in the array."""

    __slots__ = ("by_key", "items", "keyed", "slots")

    def __init__(self, keyed: KeyedList, items: list[Any], *, context: str) -> None:
        self.keyed = keyed
        self.items = items
        self.by_key: dict[str, dict[str, Any]] = {}
        self.slots: dict[str, int] | None = {} if keyed.kind == "table" else None
        for slot, item in enumerate(items):
            key = self.require_key(item, context=context)
            if key in self.by_key:
                msg = f"{context}: two items have the key {key!r}"
                raise FlowOperationValidationError(msg)
            self.by_key[key] = item
            if self.slots is not None:
                self.require_position(item, context=context)
                self.slots[key] = slot

    def require_key(self, item: Any, *, context: str) -> str:
        key = self.keyed.key_of(item)
        if not key:
            msg = f"{context}: every item of this list needs a non-empty string {self.keyed.selector_name}"
            raise FlowOperationValidationError(msg)
        return key

    def require_position(self, row: dict[str, Any], *, context: str) -> None:
        """Check that a table row carries a finite numeric position."""
        position = row.get(self.keyed.position)
        if isinstance(position, bool) or not isinstance(position, (int, float)) or not is_finite_number(position):
            msg = f"{context}: a table row's {self.keyed.position} must be a finite number"
            raise FlowOperationValidationError(msg)

    def add(self, item: dict[str, Any], *, context: str) -> None:
        """Append an item whose key is not in the list yet."""
        key = self.require_key(item, context=context)
        if self.slots is not None:
            self.require_position(item, context=context)
            self.slots[key] = len(self.items)
        self.by_key[key] = item
        self.items.append(item)

    def remove(self, key: str) -> dict[str, Any]:
        """Remove the item with ``key``, which must exist, and return it."""
        item = self.by_key.pop(key)
        if self.slots is None:
            del self.items[self._slot_of(item)]
            return item
        slot = self.slots.pop(key)
        last = self.items.pop()
        if slot < len(self.items):
            # The removed row was not the last one: the last row takes its slot.
            self.items[slot] = last
            self.slots[self.keyed.key_of(last)] = slot
        return item

    def replace(self, key: str, item: dict[str, Any], *, context: str) -> dict[str, Any]:
        """Replace the item with ``key`` by ``item``, which carries the same key, and return the old item."""
        old = self.by_key[key]
        if self.slots is not None:
            self.require_position(item, context=context)
            self.items[self.slots[key]] = item
        else:
            self.items[self._slot_of(old)] = item
        self.by_key[key] = item
        return old

    def _slot_of(self, item: dict[str, Any]) -> int:
        # Natural lists are short (a component's outputs or tool actions), and their order is kept.
        return next(slot for slot, candidate in enumerate(self.items) if candidate is item)
