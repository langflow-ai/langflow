/**
 * The node schema: where the view state, units and keyed lists of a flow are.
 *
 * `node_schema.json` is a byte-identical copy of the engine's file in
 * `lfx.services.flow_operations`, so the editor and the server address a flow
 * the same way. A test checks the two files are the same.
 */

import raw from "./node_schema.json";

const WILDCARD = "*";

type KeyPath = (string | number)[];

/**
 * A list whose items are addressed by a key instead of an index. Natural
 * lists (outputs, tool actions) are selected with `{key}` and keep the order
 * writes leave them in; tables are selected with `{id}` and kept sorted by
 * `(position, id)`.
 */
export type KeyedList = {
  kind: "natural" | "table";
  key: KeyPath;
  position?: string;
};

export function selectorName(list: KeyedList): "id" | "key" {
  return list.kind === "table" ? "id" : "key";
}

/** An item's key, or null when it has none. */
export function keyOf(list: KeyedList, item: unknown): string | null {
  let value: unknown = item;
  for (const part of list.key) {
    if (typeof part === "string" && isObject(value)) value = value[part];
    else if (
      typeof part === "number" &&
      Array.isArray(value) &&
      part >= 0 &&
      part < value.length
    )
      value = value[part];
    else return null;
  }
  return typeof value === "string" ? value : null;
}

/** The index of the first item with `key`, or -1. */
export function findItem(
  list: KeyedList,
  items: unknown[],
  key: string,
): number {
  return items.findIndex((item) => keyOf(list, item) === key);
}

// JavaScript compares strings by UTF-16 code units, as the engine does.
function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function orderOf(list: KeyedList, item: unknown): [string, string] {
  const position = isObject(item) ? item[list.position as string] : undefined;
  return [
    typeof position === "string" ? position : "",
    keyOf(list, item) ?? "",
  ];
}

/** Sort table rows in place by `(position, id)`; natural lists are left alone. */
export function sortItems(list: KeyedList, items: unknown[]): void {
  if (list.kind !== "table" || !list.position) return;
  items.sort((left, right) => {
    const [leftPosition, leftId] = orderOf(list, left);
    const [rightPosition, rightId] = orderOf(list, right);
    return compare(leftPosition, rightPosition) || compare(leftId, rightId);
  });
}

/** Whether table rows are already in `(position, id)` order. */
export function isSorted(list: KeyedList, items: unknown[]): boolean {
  if (list.kind !== "table") return true;
  const sorted = [...items];
  sortItems(list, sorted);
  return sorted.every((item, index) => item === items[index]);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

const tables = raw.keyed_lists.tables;
const NATURAL_LISTS = raw.keyed_lists.natural.map(
  (entry) =>
    [entry.path, { kind: "natural", key: entry.key } as KeyedList] as const,
);
const TABLE_PATH: string[] = tables.path;
const TABLE_WHEN_FIELD: Record<string, unknown>[] = tables.when_field;
const TABLE: KeyedList = {
  kind: "table",
  key: [tables.id],
  position: tables.position,
};

export const NODE_SCHEMA = {
  version: raw.version,
  flowViewState: new Set<string>(raw.view_state.flow),
  nodeViewState: new Set<string>(raw.view_state.node),
  nodeViewStatePaths: raw.view_state.node_paths as string[][],
  templateViewState: new Set<string>(raw.view_state.template),
  fieldViewState: new Set<string>(raw.view_state.template_field),
  edgeViewState: new Set<string>(raw.view_state.edge),
  table: TABLE,
};

function samePath(left: readonly unknown[], right: readonly unknown[]) {
  return (
    left.length === right.length &&
    left.every((part, index) => part === right[index])
  );
}

/** The keyed list a node holds at `path`, or null if the schema declares none there. */
export function keyedListAt(
  node: unknown,
  path: readonly unknown[],
): KeyedList | null {
  if (!path.every((part) => typeof part === "string")) return null;
  for (const [listPath, list] of NATURAL_LISTS) {
    if (samePath(path, listPath)) return list;
  }
  if (path.length !== TABLE_PATH.length) return null;
  let wildcard = -1;
  for (let index = 0; index < path.length; index++) {
    if (TABLE_PATH[index] === WILDCARD) wildcard = index;
    else if (path[index] !== TABLE_PATH[index]) return null;
  }
  if (wildcard === -1) return TABLE;
  let field: unknown = node;
  for (const part of path.slice(0, wildcard + 1) as string[]) {
    field = isObject(field) ? field[part] : undefined;
  }
  if (
    isObject(field) &&
    TABLE_WHEN_FIELD.some((condition) =>
      Object.entries(condition).every(([key, value]) => field[key] === value),
    )
  )
    return TABLE;
  return null;
}
