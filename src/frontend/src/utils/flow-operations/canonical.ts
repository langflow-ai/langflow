/**
 * Canonical form of flow data, the editor's copy of the engine's
 * `lfx.services.flow_operations.canonical`.
 *
 * Two graphs are equal when their canonical forms are the same JSON value:
 * the graph with its view state removed, edge handle strings replaced by the
 * objects they encode, and nodes, edges and table rows treated as collections
 * keyed by id, since their array order is not state (a table's order is its
 * rows' `(_pos, _id)`). Equality compares that form structurally and stops at
 * the first difference; only the hash serializes it, with collections
 * ordered, as RFC 8785 (JSON Canonicalization Scheme) text. JavaScript
 * already prints numbers and orders strings the way RFC 8785 asks, so the
 * serialization is mostly key sorting.
 */

import { keyedListAt, NODE_SCHEMA } from "./schema";

type JsonObject = Record<string, unknown>;

const HANDLE_QUOTE = "œ";
const EDGE_HANDLE_KEYS = ["sourceHandle", "targetHandle"];
const NODE_DATA_VIEW_STATE = new Set(
  NODE_SCHEMA.nodeViewStatePaths
    .filter(
      (path) => path.length === 3 && path[0] === "data" && path[1] === "node",
    )
    .map((path) => path[2]),
);

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** The JSON type of a value: object, array, string, number, boolean or null. */
export function jsonType(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  switch (typeof value) {
    case "boolean":
    case "number":
    case "string":
    case "object":
      return typeof value;
    default:
      throw new TypeError(`value of type ${typeof value} is not JSON`);
  }
}

function finiteNumber(value: number): number {
  if (!Number.isFinite(value))
    throw new TypeError("NaN and Infinity are not valid JSON numbers");
  return value;
}

function writeCanonical(value: unknown, parts: string[]): void {
  if (value === null) parts.push("null");
  else if (typeof value === "boolean") parts.push(value ? "true" : "false");
  else if (typeof value === "number") parts.push(String(finiteNumber(value)));
  else if (typeof value === "string") parts.push(JSON.stringify(value));
  else if (Array.isArray(value)) {
    parts.push("[");
    value.forEach((item, index) => {
      if (index) parts.push(",");
      writeCanonical(item, parts);
    });
    parts.push("]");
  } else if (isObject(value)) {
    parts.push("{");
    // The default sort compares UTF-16 code units, as RFC 8785 requires.
    Object.keys(value)
      .sort()
      .forEach((key, index) => {
        if (index) parts.push(",");
        parts.push(JSON.stringify(key), ":");
        writeCanonical(value[key], parts);
      });
    parts.push("}");
  } else {
    jsonType(value);
  }
}

/** A JSON value in RFC 8785 canonical form. */
export function canonicalJson(value: unknown): string {
  const parts: string[] = [];
  writeCanonical(value, parts);
  return parts.join("");
}

/**
 * Whether two JSON values have the same canonical form, stopping at the first
 * difference: objects compare key by key in any order, arrays item by item.
 */
export function valuesEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  const type = jsonType(left);
  if (type !== jsonType(right)) return false;
  if (type === "number")
    return finiteNumber(left as number) === finiteNumber(right as number);
  if (type === "array") {
    const leftItems = left as unknown[];
    const rightItems = right as unknown[];
    return (
      leftItems.length === rightItems.length &&
      leftItems.every((item, index) => valuesEqual(item, rightItems[index]))
    );
  }
  if (type === "object") {
    const leftObject = left as JsonObject;
    const rightObject = right as JsonObject;
    const keys = Object.keys(leftObject);
    return (
      keys.length === Object.keys(rightObject).length &&
      keys.every(
        (key) =>
          Object.hasOwn(rightObject, key) &&
          valuesEqual(leftObject[key], rightObject[key]),
      )
    );
  }
  return false;
}

/** Whether a value is a valid table row position: a finite number. */
export function isRowPosition(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * A table's rows in order: by `(_pos, _id)`, or as stored for a legacy table
 * without them. Ids compare by UTF-16 code units, as the engine sorts them.
 */
export function orderedRows<T>(rows: T[]): T[] {
  const idKey = NODE_SCHEMA.table.key[0] as string;
  const positionKey = NODE_SCHEMA.table.position as string;
  const positioned = rows.every(
    (row) =>
      isObject(row) &&
      isRowPosition(row[positionKey]) &&
      typeof row[idKey] === "string",
  );
  if (!positioned) return [...rows];
  return [...rows].sort((left, right) => {
    const a = left as JsonObject;
    const b = right as JsonObject;
    const byPosition = (a[positionKey] as number) - (b[positionKey] as number);
    if (byPosition !== 0) return byPosition;
    const aId = a[idKey] as string;
    const bId = b[idKey] as string;
    return aId < bId ? -1 : aId > bId ? 1 : 0;
  });
}

/** The object a handle string encodes (JSON with `œ` for `"`), or null when it encodes none. */
export function parseHandle(handle: unknown): JsonObject | null {
  if (typeof handle !== "string") return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(handle.replaceAll(HANDLE_QUOTE, '"'));
  } catch {
    return null;
  }
  return isObject(parsed) ? parsed : null;
}

function without(object: JsonObject, keys: Set<string>): JsonObject {
  const result: JsonObject = {};
  for (const [key, value] of Object.entries(object)) {
    if (!keys.has(key)) result[key] = value;
  }
  return result;
}

/** Map each entry's id to it, or null when an entry has no string id or two share one. */
function byId(entries: unknown[], idKey: string): JsonObject | null {
  const result: JsonObject = {};
  for (const entry of entries) {
    const id = isObject(entry) ? entry[idKey] : undefined;
    if (typeof id !== "string" || Object.hasOwn(result, id)) return null;
    result[id] = entry;
  }
  return result;
}

function tableAsCollection(
  node: JsonObject,
  key: string,
  field: unknown,
  keyed: boolean,
): unknown {
  if (!isObject(field) || !Array.isArray(field.value)) return field;
  const path = ["data", "node", "template", key, "value"];
  if (keyedListAt(node, path) !== NODE_SCHEMA.table) return field;
  if (!keyed) return { ...field, value: orderedRows(field.value) };
  const rows = byId(field.value, NODE_SCHEMA.table.key[0] as string);
  return rows ? { ...field, value: rows } : field;
}

function canonicalNode(node: unknown, keyed: boolean): unknown {
  if (!isObject(node)) return node;
  const result = without(node, NODE_SCHEMA.nodeViewState);
  const data = result.data;
  if (!isObject(data) || !isObject(data.node)) return result;
  const nodeData = without(data.node, NODE_DATA_VIEW_STATE);
  const template = nodeData.template;
  if (isObject(template)) {
    const fields: JsonObject = {};
    for (const [key, field] of Object.entries(template)) {
      if (NODE_SCHEMA.templateViewState.has(key)) continue;
      const visible = isObject(field)
        ? without(field, NODE_SCHEMA.fieldViewState)
        : field;
      fields[key] = tableAsCollection(node, key, visible, keyed);
    }
    nodeData.template = fields;
  }
  result.data = { ...data, node: nodeData };
  return result;
}

function canonicalEdge(edge: unknown): unknown {
  if (!isObject(edge)) return edge;
  const result = without(edge, NODE_SCHEMA.edgeViewState);
  for (const key of EDGE_HANDLE_KEYS) {
    const parsed = parseHandle(result[key]);
    if (parsed) result[key] = parsed;
  }
  return result;
}

function idOf(entry: unknown): string {
  // Entries without a string id sort first; a graph that has them fails validation anyway.
  return isObject(entry) && typeof entry.id === "string" ? entry.id : "";
}

/**
 * Flow data in canonical form. With `keyed`, nodes, edges and table rows whose
 * ids are unique become mappings from id to entry, for comparison; without it
 * they stay lists ordered by id (rows by `(_pos, _id)`), for serialization.
 * Shares nested values with `flowData`: compare or serialize it, never change it.
 */
export function canonicalGraph(flowData: JsonObject, keyed = true): JsonObject {
  const graph = without(flowData, NODE_SCHEMA.flowViewState);
  for (const key of ["nodes", "edges"]) {
    const entries = graph[key];
    if (!Array.isArray(entries)) continue;
    const canonical = entries.map((entry) =>
      key === "nodes" ? canonicalNode(entry, keyed) : canonicalEdge(entry),
    );
    if (keyed) {
      graph[key] = byId(canonical, "id") ?? canonical;
    } else {
      graph[key] = canonical.sort((left, right) => {
        const a = idOf(left);
        const b = idOf(right);
        return a < b ? -1 : a > b ? 1 : 0;
      });
    }
  }
  return graph;
}

/** Flow data serialized in canonical graph form; its SHA-256 is the graph's hash. */
export function canonicalGraphJson(flowData: JsonObject): string {
  return canonicalJson(canonicalGraph(flowData, false));
}

/** Whether two flow data objects are the same graph, stopping at the first difference. */
export function graphsEqual(left: JsonObject, right: JsonObject): boolean {
  return valuesEqual(canonicalGraph(left), canonicalGraph(right));
}
