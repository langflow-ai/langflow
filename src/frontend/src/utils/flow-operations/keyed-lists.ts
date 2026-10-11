/**
 * Keyed lists, indexed by item key for one apply call: the editor's copy of
 * the engine's `lfx.services.flow_operations.keyed_lists`.
 *
 * Outputs, tool actions and table rows are lists whose items carry a key: an
 * output's `name`, a tool action's first tag, a row's `_id`. A write finds its
 * item through an index instead of scanning the list, and building the index
 * checks the list once: every item has a key, no key repeats, and every table
 * row carries a numeric `_pos`.
 *
 * Natural lists keep the order writes leave them in. A table's order is its
 * rows' `(_pos, _id)`, not their places in the array, so the engine never
 * sorts a table: a new row is appended, and a deleted row's slot is taken by
 * the last row.
 *
 * The index maps keys to slots rather than to items, since writes replace the
 * items they pass through with copies of their own.
 */

import { isRowPosition } from "./canonical";
import { type KeyedList, keyOf, selectorName } from "./schema";

type JsonObject = Record<string, unknown>;

export class ListIndex {
  readonly slots = new Map<string, number>();

  constructor(
    readonly list: KeyedList,
    readonly items: unknown[],
    context: string,
    invalid: (message: string) => Error,
  ) {
    items.forEach((item, slot) => {
      const key = this.requireKey(item, context, invalid);
      if (this.slots.has(key))
        throw invalid(`${context}: two items have the key ${key}`);
      if (list.kind === "table") this.requirePosition(item, context, invalid);
      this.slots.set(key, slot);
    });
  }

  requireKey(
    item: unknown,
    context: string,
    invalid: (message: string) => Error,
  ): string {
    const key = keyOf(this.list, item);
    if (!key)
      throw invalid(
        `${context}: every item of this list needs a non-empty string ${selectorName(this.list)}`,
      );
    return key;
  }

  /** Check that a table row carries a finite numeric position. */
  requirePosition(
    row: unknown,
    context: string,
    invalid: (message: string) => Error,
  ): void {
    const position = (row as JsonObject)[this.list.position as string];
    if (!isRowPosition(position))
      throw invalid(
        `${context}: a table row's ${this.list.position} must be a finite number`,
      );
  }

  /** Append an item whose key is not in the list yet. */
  add(item: unknown, context: string, invalid: (message: string) => Error) {
    const key = this.requireKey(item, context, invalid);
    if (this.list.kind === "table")
      this.requirePosition(item, context, invalid);
    this.slots.set(key, this.items.length);
    this.items.push(item);
  }

  /** Remove the item with `key`, which must exist, and return it. */
  remove(key: string): unknown {
    const slot = this.slots.get(key)!;
    this.slots.delete(key);
    const item = this.items[slot];
    if (this.list.kind === "table") {
      const last = this.items.pop();
      if (slot < this.items.length) {
        // The removed row was not the last one: the last row takes its slot.
        this.items[slot] = last;
        this.slots.set(keyOf(this.list, last)!, slot);
      }
      return item;
    }
    // A natural list keeps its order; the items after the removed one move up.
    this.items.splice(slot, 1);
    for (let later = slot; later < this.items.length; later++)
      this.slots.set(keyOf(this.list, this.items[later])!, later);
    return item;
  }

  /** Replace the item with `key` by `item`, which carries the same key. */
  replace(
    key: string,
    item: unknown,
    context: string,
    invalid: (message: string) => Error,
  ): unknown {
    if (this.list.kind === "table")
      this.requirePosition(item, context, invalid);
    const slot = this.slots.get(key)!;
    const old = this.items[slot];
    this.items[slot] = item;
    return old;
  }
}
