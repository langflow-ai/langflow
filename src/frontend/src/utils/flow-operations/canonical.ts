/**
 * Canonical form of flow data, the editor's copy of the engine's
 * `lfx.services.flow_operations.canonical`.
 *
 * Two graphs are equal when their canonical forms are identical: RFC 8785
 * (JSON Canonicalization Scheme) applied to the graph with its view state
 * removed, edge handle strings spelled canonically, and nodes and edges
 * ordered by id. JavaScript already prints numbers and orders strings the way
 * RFC 8785 asks, so this is mostly key sorting.
 */

import { NODE_SCHEMA } from "./schema";

type JsonObject = Record<string, unknown>;

const HANDLE_QUOTE = "œ";
const EDGE_HANDLE_KEYS = ["sourceHandle", "targetHandle"];

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

function writeCanonical(value: unknown, parts: string[]): void {
  if (value === null) parts.push("null");
  else if (typeof value === "boolean") parts.push(value ? "true" : "false");
  else if (typeof value === "number") {
    if (!Number.isFinite(value))
      throw new TypeError("NaN and Infinity are not valid JSON numbers");
    parts.push(String(value));
  } else if (typeof value === "string") parts.push(JSON.stringify(value));
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

/** Whether two JSON values are equal under canonical comparison. */
export function valuesEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  const type = jsonType(left);
  if (type !== jsonType(right)) return false;
  if (type === "string" || type === "boolean" || type === "null") return false;
  return canonicalJson(left) === canonicalJson(right);
}

function without(object: JsonObject, keys: Set<string>): JsonObject {
  const result: JsonObject = {};
  for (const [key, value] of Object.entries(object)) {
    if (!keys.has(key)) result[key] = value;
  }
  return result;
}

function byId(entries: unknown[]): unknown[] {
  const idOf = (entry: unknown) =>
    isObject(entry) && typeof entry.id === "string" ? entry.id : "";
  return [...entries].sort((left, right) => {
    const a = idOf(left);
    const b = idOf(right);
    return a < b ? -1 : a > b ? 1 : 0;
  });
}

/** A handle string re-serialized canonically, or the value unchanged if it is not one. */
export function canonicalHandle(handle: unknown): unknown {
  if (typeof handle !== "string") return handle;
  try {
    const parsed = JSON.parse(handle.replaceAll(HANDLE_QUOTE, '"'));
    if (parsed === null || typeof parsed !== "object") return handle;
    return canonicalJson(parsed).replaceAll('"', HANDLE_QUOTE);
  } catch {
    return handle;
  }
}

function canonicalNode(node: unknown): unknown {
  if (!isObject(node)) return node;
  const result = without(node, NODE_SCHEMA.nodeViewState);
  const data = result.data;
  if (!isObject(data) || !isObject(data.node)) return result;
  const hidden = new Set(
    NODE_SCHEMA.nodeViewStatePaths
      .filter(
        (path) => path.length === 3 && path[0] === "data" && path[1] === "node",
      )
      .map((path) => path[2]),
  );
  const nodeData = without(data.node, hidden);
  const template = nodeData.template;
  if (isObject(template)) {
    const fields: JsonObject = {};
    for (const [key, field] of Object.entries(template)) {
      if (NODE_SCHEMA.templateViewState.has(key)) continue;
      fields[key] = isObject(field)
        ? without(field, NODE_SCHEMA.fieldViewState)
        : field;
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
    if (key in result) result[key] = canonicalHandle(result[key]);
  }
  return result;
}

/**
 * Flow data without view state, with canonical handles, and nodes and edges
 * ordered by id. Shares nested values with `flowData`: serialize or compare
 * it, never change it.
 */
export function canonicalGraph(flowData: JsonObject): JsonObject {
  const graph = without(flowData, NODE_SCHEMA.flowViewState);
  if (Array.isArray(graph.nodes))
    graph.nodes = byId(graph.nodes.map(canonicalNode));
  if (Array.isArray(graph.edges))
    graph.edges = byId(graph.edges.map(canonicalEdge));
  return graph;
}

/** Flow data serialized in canonical graph form; its SHA-256 is the graph's hash. */
export function canonicalGraphJson(flowData: JsonObject): string {
  return canonicalJson(canonicalGraph(flowData));
}
