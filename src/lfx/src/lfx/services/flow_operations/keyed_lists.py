"""Keyed lists, indexed by item key.

Outputs, tool actions and table rows are lists whose items carry a key: an
output's ``name``, a tool action's first tag, a row's ``__id__``. A write finds
its item through an index instead of scanning the list. Building the index
reads the list once, and counts what breaks the keyed list rules: an item
without a key, a key that repeats, an item without a numeric ``__pos__``.
Apply refuses a write into such a list; replay does not.

Every keyed list is ordered by its items' ``(__pos__, key)``, not by their
places in the array: readers sort items when they strip ``__pos__``, so the
engine never sorts a list. A new item is appended, and the last item moves
into a deleted item's place. A list whose items carry no ``__pos__`` keeps its
array order, so a deleted item's followers move up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.services.flow_operations.exceptions import FlowOperationValidationError

if TYPE_CHECKING:
    from lfx.services.flow_operations.schema import KeyedList


def _quoted(value: str) -> str:
    return repr(value)


class ListIndex:
    """The array index of every item of one keyed list, by key, and what the list breaks of the rules.

    Building the index never fails. Apply refuses a write into a list that
    breaks the rules (``problem``); replay writes into it, and fails only when
    a key it looks up names two items.
    """

    __slots__ = ("items", "keyed", "keyless", "repeated", "slots", "unpositioned")

    def __init__(self, keyed: KeyedList, items: list[Any]) -> None:
        self.keyed = keyed
        # The list this index describes; an owner checks it is still the list it reads.
        self.items = items
        # The array index of each item whose key no other item has, by key.
        self.slots: dict[str, int] = {}
        # The keys that two items or more have, in the order the list repeats them.
        self.repeated: dict[str, None] = {}
        # How many items have no non-empty string key.
        self.keyless = 0
        # How many items have no finite numeric position.
        self.unpositioned = 0
        key_of, has_position = keyed.key_of, keyed.has_position
        slots, repeated = self.slots, self.repeated
        for slot, item in enumerate(items):
            if not has_position(item):
                self.unpositioned += 1
            key = key_of(item)
            if not key:
                self.keyless += 1
            elif key in repeated:
                continue
            elif key in slots:
                del slots[key]
                repeated[key] = None
            else:
                slots[key] = slot

    def copy(self, items: list[Any]) -> ListIndex:
        """This index for ``items``, a copy of the list it describes."""
        index = ListIndex.__new__(ListIndex)
        index.keyed = self.keyed
        index.items = items
        index.slots = dict(self.slots)
        index.repeated = dict(self.repeated)
        index.keyless = self.keyless
        index.unpositioned = self.unpositioned
        return index

    def problem(self) -> str | None:
        """The first rule the list breaks, if any: an item without a key, a repeated key, an item without a position."""
        problem = self.key_problem()
        if problem is None and self.unpositioned:
            return unpositioned_problem(self.keyed)
        return problem

    def key_problem(self) -> str | None:
        """The first rule about keys the list breaks, if any: an item without a key, then a repeated key."""
        if self.keyless:
            return "every item of this list needs a non-empty string key"
        for key in self.repeated:
            return f"two items have the key {_quoted(key)}"
        return None

    def check_keys(self, context: str) -> None:
        """Raise when an item has no key or two items share one: a reader that finds items by key needs this."""
        problem = self.key_problem()
        if problem is not None:
            msg = f"{context}: {problem}"
            raise FlowOperationValidationError(msg)

    def find(self, key: str, context: str) -> int | None:
        """The array index of the item with ``key``, or None when no item has it. Raises when two items have it."""
        if key in self.repeated:
            msg = f"{context}: two items have the key {_quoted(key)}"
            raise FlowOperationValidationError(msg)
        return self.slots.get(key)

    def slot(self, key: str) -> int | None:
        """The array index of the item with ``key``, when only one item has it."""
        return self.slots.get(key)

    def keys(self) -> list[str]:
        """The keys that only one item has."""
        return list(self.slots)

    def add(self, key: str, item: Any) -> None:
        """Append ``item``, whose key ``key`` is not in the list yet."""
        if not self.keyed.has_position(item):
            self.unpositioned += 1
        self.slots[key] = len(self.items)
        self.items.append(item)

    def replace(self, slot: int, item: Any) -> None:
        """Replace the item at ``slot`` by ``item``, which carries the same key."""
        has_position = self.keyed.has_position
        now = has_position(item)
        old = self.items[slot]
        self.items[slot] = item
        self.position_changed(has_position(old), now)

    def position_changed(self, before: bool, after: bool) -> None:  # noqa: FBT001
        """Count a write inside an item that gave it, or took away, its position."""
        if before and not after:
            self.unpositioned += 1
        elif after and not before:
            self.unpositioned -= 1

    def remove(self, key: str) -> Any:
        """Remove the item with ``key`` and return it, or return None when no item has it."""
        slot = self.slots.pop(key, None)
        if slot is None:
            return None
        items = self.items
        item = remove_item(self.keyed, items, slot)
        if not self.keyed.has_position(item):
            # The items after it moved up one place.
            self.unpositioned -= 1
            slots = self.slots
            for other, later in slots.items():
                if later > slot:
                    slots[other] = later - 1
            return item
        if slot < len(items):
            moved_key = self.keyed.key_of(items[slot])
            if moved_key is not None and moved_key in self.slots:
                self.slots[moved_key] = slot
        return item


def unpositioned_problem(keyed: KeyedList) -> str:
    return f"a list item's {keyed.position} must be a finite number"


def check_position(keyed: KeyedList, item: Any, context: str) -> None:
    """Raise unless a list item carries a finite numeric position."""
    if not keyed.has_position(item):
        msg = f"{context}: {unpositioned_problem(keyed)}"
        raise FlowOperationValidationError(msg)


def find_item(keyed: KeyedList, items: list[Any], key: str) -> int | None:
    """The array index of the first item with ``key``, found by reading every item, or None."""
    key_of = keyed.key_of
    for slot, item in enumerate(items):
        if key_of(item) == key:
            return slot
    return None


def remove_item(keyed: KeyedList, items: list[Any], slot: int) -> Any:
    """Remove the item at ``slot``.

    The order of a list is its items' positions, so the last item moves into
    the gap. An item without a position belongs to a list that keeps its
    array order, so the items after it move up.
    """
    item = items[slot]
    if keyed.has_position(item):
        last = items.pop()
        if slot < len(items):
            items[slot] = last
        return item
    del items[slot]
    return item
