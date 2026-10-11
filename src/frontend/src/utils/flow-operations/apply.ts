/**
 * Applying recorded flow operations to a flow graph in the browser.
 *
 * This is the editor's copy of the server's flow operation engine
 * (`lfx.services.flow_operations`), used to play a flow's history back on the
 * canvas. It must produce exactly what the server does: both run the shared
 * fixtures in `src/lfx/tests/unit/services/flow_operations/fixtures/`, and
 * both read `node_schema.json` for where keyed lists are.
 *
 * Application is copy-on-write: the input graph is never changed, and the
 * result shares every node and edge an operation did not touch.
 *
 * With `inverse`, it also returns, for each operation, the operations that
 * undo it, read from the state each write replaces. History playback keeps
 * those instead of a graph per revision.
 */

import { cloneDeep } from "lodash";
import { jsonType, valuesEqual } from "./canonical";
import {
  checkEdge,
  HANDLE_KEYS,
  handleForms,
  inputKey,
  nodeOutputs,
  OUTPUTS_PATH,
} from "./edge-rules";
import { failedExpectation, invalidOperation } from "./errors";
import { ListIndex } from "./keyed-lists";
import { type KeyedList, keyedListAt, keyOf, selectorName } from "./schema";
import {
  type ApplyOptions,
  type FlowGraph,
  GraphState,
  NODE_OBJECT_PATHS,
  requireNodeObjects,
} from "./state";

export { jsonType } from "./canonical";
export {
  FlowOperationError,
  type FlowOperationErrorName,
} from "./errors";
export type { ApplyOptions, FlowGraph } from "./state";

type JsonObject = Record<string, unknown>;

/** Selects a table row by its `_id`, or a natural-key list item by its key. */
export type Selector = { id: string } | { key: string };
export type PathSegment = string | Selector;

/** What a path must hold before a write: a value, or nothing at all. */
export type Expectation = { value: unknown } | { absent: true };

export type FieldUpdate = {
  id: string;
  op: "set_field" | "delete_field";
  path: PathSegment[];
  value?: unknown;
  from_type?: string;
  template_field?: JsonObject;
  expect?: Expectation;
};

export type FlowOperation = JsonObject & { type: string };

export type ApplyResult = {
  flowData: FlowGraph;
  forwardOperations: FlowOperation[];
  /**
   * With `inverse`: for each operation applied, the operations that undo it.
   * Undo the last operation first, each list in a call of its own, with
   * `restoring` set.
   */
  inverseOperations?: FlowOperation[][];
};

const GRAPH_COLLECTION_KEYS = new Set(["nodes", "edges"]);
// Replacing these whole objects would record an entire node as one opaque value.
const FORBIDDEN_WHOLE_NODE_PATHS = new Set(
  NODE_OBJECT_PATHS.map((path) => JSON.stringify(path)),
);
// An edge's endpoints are its identity: connecting other nodes is another edge.
const FORBIDDEN_EDGE_UPDATE_ROOTS = new Set(["id", "source", "target"]);
// Writes under these edge keys can change which output or input the edge connects.
const EDGE_HANDLE_ROOTS = new Set<string>([...HANDLE_KEYS, "data"]);
const TEMPLATE_PATH = ["data", "node", "template"];
const JSON_TYPE_NAMES = new Set([
  "object",
  "array",
  "string",
  "number",
  "boolean",
  "null",
]);

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isSelector(segment: PathSegment): segment is Selector {
  return typeof segment !== "string";
}

function selectorKey(selector: Selector): string {
  return "id" in selector ? selector.id : selector.key;
}

function clone<T>(value: T): T {
  return value === null || typeof value !== "object" ? value : cloneDeep(value);
}

function dedupe(ids: string[]): string[] {
  return [...new Set(ids)];
}

function pathLabel(path: PathSegment[]): string {
  return JSON.stringify(path);
}

// --- Parsing: the same shapes the engine's models accept --------------------------------

function onlyKeys(value: JsonObject, allowed: string[], context: string) {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key))
      throw invalidOperation(`${context}: unexpected key ${key}`);
  }
}

function parseObjectList(value: unknown, context: string): JsonObject[] {
  if (!Array.isArray(value) || !value.every(isObject))
    throw invalidOperation(`${context} must be a list of objects`);
  return value;
}

function parseStringList(value: unknown, context: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string"))
    throw invalidOperation(`${context} must be a list of strings`);
  return value;
}

function parseSegment(segment: unknown, context: string): PathSegment {
  if (typeof segment === "string") return segment;
  if (typeof segment === "number" || typeof segment === "boolean")
    throw invalidOperation(
      `${context}: path segments must be object keys or selectors; integer list indexes are not allowed`,
    );
  if (isObject(segment)) {
    const keys = Object.keys(segment);
    if (
      keys.length === 1 &&
      (keys[0] === "id" || keys[0] === "key") &&
      isNonEmptyString(segment[keys[0]])
    )
      return { [keys[0]]: segment[keys[0]] } as Selector;
  }
  throw invalidOperation(`${context}: invalid path segment`);
}

function parseExpectation(value: unknown, context: string): Expectation {
  if (isObject(value)) {
    const keys = Object.keys(value);
    if (keys.length === 1 && keys[0] === "value") return { value: value.value };
    if (keys.length === 1 && keys[0] === "absent" && value.absent === true)
      return { absent: true };
  }
  throw invalidOperation(
    `${context}.expect must be {"value": ...} or {"absent": true}`,
  );
}

function parseUpdate(value: unknown, context: string): FieldUpdate {
  if (!isObject(value)) throw invalidOperation(`${context} must be an object`);
  if (value.op !== "set_field" && value.op !== "delete_field")
    throw invalidOperation(`${context}: unknown op ${String(value.op)}`);
  const setField = value.op === "set_field";
  onlyKeys(
    value,
    setField
      ? ["id", "op", "path", "value", "from_type", "template_field", "expect"]
      : ["id", "op", "path", "expect"],
    context,
  );
  if (!isNonEmptyString(value.id))
    throw invalidOperation(`${context}: id must be a non-empty string`);
  if (!Array.isArray(value.path) || value.path.length === 0)
    throw invalidOperation(`${context}: path must not be empty`);
  const update: FieldUpdate = {
    id: value.id,
    op: value.op,
    path: value.path.map((segment) => parseSegment(segment, context)),
  };
  if (setField) {
    if (!("value" in value))
      throw invalidOperation(`${context}: set_field requires a value`);
    update.value = value.value;
    if (value.from_type != null) {
      if (
        typeof value.from_type !== "string" ||
        !JSON_TYPE_NAMES.has(value.from_type)
      )
        throw invalidOperation(`${context}: from_type must name a JSON type`);
      update.from_type = value.from_type;
    }
    if (value.template_field != null) {
      if (!isObject(value.template_field))
        throw invalidOperation(`${context}: template_field must be an object`);
      update.template_field = value.template_field;
    }
  }
  if (value.expect != null)
    update.expect = parseExpectation(value.expect, context);
  return update;
}

const OPERATION_KEYS: Record<string, string[]> = {
  add_nodes: ["type", "nodes"],
  update_nodes: ["type", "updates"],
  delete_nodes: ["type", "ids"],
  add_edges: ["type", "edges"],
  update_edges: ["type", "updates"],
  delete_edges: ["type", "ids"],
  update_metadata: ["type", "fields", "delete_keys"],
};

type ParsedOperation =
  | { type: "add_nodes"; nodes: JsonObject[] }
  | { type: "update_nodes" | "update_edges"; updates: FieldUpdate[] }
  | { type: "delete_nodes" | "delete_edges"; ids: string[] }
  | { type: "add_edges"; edges: JsonObject[] }
  | { type: "update_metadata"; fields: JsonObject; delete_keys: string[] };

function parseOperation(operation: unknown): ParsedOperation {
  if (!isObject(operation)) throw invalidOperation("operation must be a dict");
  const type = operation.type as string;
  const keys = OPERATION_KEYS[type];
  if (typeof type !== "string" || !keys)
    throw invalidOperation(
      `Unsupported operation type: ${String(operation.type)}`,
    );
  onlyKeys(operation, keys, type);
  switch (type) {
    case "add_nodes":
      return { type, nodes: parseObjectList(operation.nodes, "nodes") };
    case "add_edges":
      return { type, edges: parseObjectList(operation.edges, "edges") };
    case "delete_nodes":
    case "delete_edges":
      return { type, ids: parseStringList(operation.ids, "ids") };
    case "update_nodes":
    case "update_edges": {
      if (!Array.isArray(operation.updates))
        throw invalidOperation(`${type}.updates must be a list`);
      return {
        type,
        updates: operation.updates.map((update, index) =>
          parseUpdate(update, `${type}[${index}]`),
        ),
      };
    }
    default: {
      const fields = operation.fields ?? {};
      if (!isObject(fields))
        throw invalidOperation("update_metadata.fields must be an object");
      return {
        type: "update_metadata",
        fields,
        delete_keys: parseStringList(
          operation.delete_keys ?? [],
          "update_metadata.delete_keys",
        ),
      };
    }
  }
}

// --- Walking a path --------------------------------------------------------------------

// What a write replaced or removed when there was nothing there; undefined is not JSON, but null is a value.
const ABSENT = Symbol("absent");

/** A keyed list item a path passes through. */
type ItemStep = { items: ListIndex; key: string };

type Walk = {
  parent: unknown;
  steps: ItemStep[];
  // The index of the first segment that does not exist, or null when every one does.
  missingAt: number | null;
};

/**
 * Follow `path` to the value holding its last segment, once. Every container
 * on the way is replaced by one this call owns, so the write changes only
 * containers the call made. A segment that does not fit the value it reads,
 * such as a key of a list, is an error rather than a missing value.
 */
function walk(
  state: GraphState,
  root: JsonObject,
  node: JsonObject | null,
  path: PathSegment[],
  context: string,
): Walk {
  let value: unknown = root;
  const steps: ItemStep[] = [];
  const enter = (container: JsonObject | unknown[], at: string | number) => {
    const child = (container as Record<string | number, unknown>)[at];
    if (child === null || typeof child !== "object") return child;
    const owned = state.own(child);
    (container as Record<string | number, unknown>)[at] = owned;
    return owned;
  };
  for (let index = 0; index < path.length - 1; index++) {
    const part = path[index];
    if (!isSelector(part)) {
      if (!isObject(value))
        throw invalidOperation(
          `${context}.path[${index}]: ${part} reads a key of a value that is not an object`,
        );
      if (!(part in value))
        return { parent: undefined, steps, missingAt: index };
      value = enter(value, part);
      continue;
    }
    const items = keyedList(state, node, path, index, value, context);
    const key = selectorKey(part);
    const slot = items.slots.get(key);
    if (slot === undefined)
      return { parent: undefined, steps, missingAt: index };
    value = enter(items.items, slot);
    steps.push({ items, key });
  }
  return { parent: value, steps, missingAt: null };
}

/** Whether the last segment of `path` exists in `parent`, and its value. */
function readLast(
  state: GraphState,
  node: JsonObject | null,
  parent: unknown,
  path: PathSegment[],
  context: string,
): { exists: boolean; value?: unknown } {
  const last = path[path.length - 1];
  if (!isSelector(last)) {
    if (!isObject(parent))
      throw invalidOperation(
        `${context}.path[${path.length - 1}]: ${last} reads a key of a value that is not an object`,
      );
    return last in parent
      ? { exists: true, value: parent[last] }
      : { exists: false };
  }
  const items = keyedList(state, node, path, path.length - 1, parent, context);
  const slot = items.slots.get(selectorKey(last));
  return slot === undefined
    ? { exists: false }
    : { exists: true, value: items.items[slot] };
}

/** The index of the keyed list `path[index]` selects from, checking the selector fits it. */
function keyedList(
  state: GraphState,
  node: JsonObject | null,
  path: PathSegment[],
  index: number,
  value: unknown,
  context: string,
): ListIndex {
  const list: KeyedList | null = node
    ? keyedListAt(node, path.slice(0, index))
    : null;
  if (!list)
    throw invalidOperation(
      `${context}.path[${index}]: selector on a list the node schema does not declare keyed`,
    );
  const name = selectorName(list);
  if (!(name in (path[index] as Selector)))
    throw invalidOperation(
      `${context}.path[${index}]: items of this list are selected with {"${name}": ...}`,
    );
  if (!Array.isArray(value))
    throw invalidOperation(
      `${context}.path[${index}]: selector on a value that is not a list`,
    );
  return state.listIndex(list, value, `${context}.path[${index}]`);
}

function checkExpectation(
  update: FieldUpdate,
  current: { exists: boolean; value?: unknown },
  context: string,
): void {
  if (!update.expect) return;
  if ("absent" in update.expect) {
    if (current.exists)
      throw failedExpectation(
        `${context}: expected ${pathLabel(update.path)} to be absent, but it exists`,
      );
    return;
  }
  if (!current.exists || !valuesEqual(current.value, update.expect.value))
    throw failedExpectation(
      `${context}: expected ${pathLabel(update.path)} to hold the given value, but found ${current.exists ? "a different value" : "nothing"}`,
    );
}

/**
 * Refuse a set_field that silently changes a value's JSON type. A type change
 * is declared with `from_type`, which also makes it a precondition.
 */
function checkTypeChange(
  current: unknown,
  update: FieldUpdate,
  context: string,
  redacted: boolean,
): void {
  // Types in a redacted graph are not reliable; see ApplyOptions.
  if (redacted) return;
  const exists = current !== ABSENT;
  if (update.from_type == null) {
    if (exists && jsonType(current) !== jsonType(update.value))
      throw invalidOperation(
        `${context}: set_field changes a ${jsonType(current)} to a ${jsonType(update.value)} without declaring from_type`,
        "FIELD_TYPE_CHANGE_UNDECLARED",
      );
    return;
  }
  if (!exists || jsonType(current) !== update.from_type)
    throw invalidOperation(
      `${context}: set_field expected to replace a ${update.from_type} but found ${exists ? jsonType(current) : "nothing"}`,
      "FIELD_TYPE_PRECONDITION_FAILED",
    );
}

/** Write or delete the last segment of the update's path. Return what it replaced or removed, or ABSENT. */
function writeLast(
  state: GraphState,
  node: JsonObject | null,
  parent: unknown,
  update: FieldUpdate,
  context: string,
): unknown {
  const { path } = update;
  const last = path[path.length - 1];
  const redacted = state.options.redacted ?? false;
  if (!isSelector(last)) {
    if (!isObject(parent))
      throw invalidOperation(
        `${context}: path must end at an object property or a keyed list item`,
      );
    const before = last in parent ? parent[last] : ABSENT;
    if (update.op === "delete_field") {
      delete parent[last];
      return before;
    }
    checkTypeChange(before, update, context, redacted);
    parent[last] = clone(update.value);
    return before;
  }
  const items = keyedList(state, node, path, path.length - 1, parent, context);
  const key = selectorKey(last);
  const exists = items.slots.has(key);
  if (update.op === "delete_field") return exists ? items.remove(key) : ABSENT;
  if (keyOf(items.list, update.value) !== key)
    throw invalidOperation(
      `${context}: a list item written at a selector must carry the same key: ${key}`,
    );
  checkTypeChange(
    exists ? items.items[items.slots.get(key)!] : ABSENT,
    update,
    context,
    redacted,
  );
  const value = clone(update.value);
  if (exists) return items.replace(key, value, context, invalidOperation);
  items.add(value, context, invalidOperation);
  return ABSENT;
}

/**
 * Apply one set_field or delete_field to `root`, a node or an edge, walking its
 * path once. `node` is the node whose schema declares keyed lists, or null for
 * an edge, which has none. Returns the value the write replaced or removed
 * (ABSENT when there was none), and records its inverse first when asked.
 */
function applyFieldUpdate(
  state: GraphState,
  root: JsonObject,
  node: JsonObject | null,
  update: FieldUpdate,
  context: string,
  inverses: FieldInverses | null,
): unknown {
  const { path } = update;
  const { parent, steps, missingAt } = walk(state, root, node, path, context);
  const current =
    missingAt === null
      ? readLast(state, node, parent, path, context)
      : { exists: false };
  checkExpectation(update, current, context);
  if (missingAt !== null) {
    const part = path[missingAt];
    throw invalidOperation(
      isSelector(part)
        ? `${context}.path[${missingAt}]: list item does not exist: ${selectorKey(part)}`
        : `${context}.path[${missingAt}]: object path part must be an existing string key: ${part}`,
    );
  }
  inverses?.record(state, node, parent, update, current, context);
  const before = writeLast(state, node, parent, update, context);
  // A write inside a keyed list item must leave its key alone, and a table row its position.
  for (const step of [...steps].reverse()) {
    const item = step.items.items[step.items.slots.get(step.key)!];
    if (keyOf(step.items.list, item) !== step.key)
      throw invalidOperation(
        `${context}: cannot change a list item's ${selectorName(step.items.list)}`,
      );
    if (step.items.list.kind === "table")
      step.items.requirePosition(item, context, invalidOperation);
  }
  return before;
}

// --- Inverses of field writes ------------------------------------------------------------

/**
 * Collects the writes that undo an update batch, read from the state each
 * write replaces. They are undone last first; a path written twice is split
 * into separate operations, since one operation may write a path once.
 */
class FieldInverses {
  private readonly entries: FieldUpdate[] = [];

  /** Record what undoes `update`; called before it is applied. */
  record(
    state: GraphState,
    node: JsonObject | null,
    parent: unknown,
    update: FieldUpdate,
    current: { exists: boolean; value?: unknown },
    context: string,
  ): void {
    const { path } = update;
    const last = path[path.length - 1];
    if (isSelector(last) && update.op === "delete_field" && current.exists) {
      // Removing a natural-list item that is not last cannot be undone by a
      // selector write, which appends; the whole list is written back. A
      // table's order is its rows' positions, so its rows need no such care.
      const items = keyedList(
        state,
        node,
        path,
        path.length - 1,
        parent,
        context,
      );
      if (
        items.list.kind === "natural" &&
        items.slots.get(selectorKey(last)) !== items.items.length - 1
      ) {
        this.entries.push({
          id: update.id,
          op: "set_field",
          path: path.slice(0, -1),
          value: cloneDeep(items.items),
        });
        return;
      }
    }
    if (!current.exists) {
      if (update.op === "set_field")
        this.entries.push({ id: update.id, op: "delete_field", path });
      return;
    }
    const entry: FieldUpdate = {
      id: update.id,
      op: "set_field",
      path,
      value: current.value,
    };
    if (
      update.op === "set_field" &&
      jsonType(current.value) !== jsonType(update.value)
    )
      entry.from_type = jsonType(update.value);
    this.entries.push(entry);
  }

  operations(type: string): FlowOperation[] {
    const operations: FlowOperation[] = [];
    let batch: FieldUpdate[] = [];
    let written = new Set<string>();
    for (const entry of [...this.entries].reverse()) {
      const key = JSON.stringify([entry.id, entry.path]);
      if (written.has(key)) {
        operations.push({ type, updates: batch });
        batch = [];
        written = new Set();
      }
      written.add(key);
      batch.push(entry);
    }
    if (batch.length > 0) operations.push({ type, updates: batch });
    return operations;
  }
}

// --- Operations ------------------------------------------------------------------------

type Applied = { forward: FlowOperation[]; inverse: FlowOperation[] };

const NOTHING: Applied = { forward: [], inverse: [] };

function forwardUpdates(type: string, updates: FieldUpdate[]): FlowOperation {
  return { type, updates: cloneDeep(updates) };
}

/** False for a delete that found nothing to remove, which is not recorded. */
function changed(update: FieldUpdate, before: unknown): boolean {
  return !(update.op === "delete_field" && before === ABSENT);
}

function applyAddNodes(state: GraphState, nodes: JsonObject[]): Applied {
  if (nodes.length === 0) return NOTHING;
  const seen = new Set<string>();
  const payloads: JsonObject[] = [];
  nodes.forEach((node, index) => {
    const context = `add_nodes[${index}]`;
    if (!isNonEmptyString(node.id))
      throw invalidOperation(
        `${context}: node must have a non-empty string id`,
      );
    requireNodeObjects(node, (message) =>
      invalidOperation(`${context}: ${message}`),
    );
    if (seen.has(node.id))
      throw invalidOperation(
        `add_nodes: duplicate node id in request: ${node.id}`,
      );
    if (state.nodes.has(node.id))
      throw invalidOperation(`add_nodes: node id already exists: ${node.id}`);
    seen.add(node.id);
    const payload = clone(node);
    state.nodes.set(node.id, payload);
    payloads.push(payload);
  });
  return {
    forward: [{ type: "add_nodes", nodes: payloads }],
    inverse: [{ type: "delete_nodes", ids: [...seen] }],
  };
}

function rejectRepeatedPaths(updates: FieldUpdate[], kind: string): void {
  const seen = new Set<string>();
  for (const update of updates) {
    const key = JSON.stringify([update.id, update.path]);
    if (seen.has(key))
      throw invalidOperation(
        `${kind}: multiple field updates for one id and path: ${update.id} ${pathLabel(update.path)}`,
      );
    seen.add(key);
  }
}

function samePrefix(path: PathSegment[], prefix: string[]): boolean {
  return (
    path.length >= prefix.length &&
    prefix.every((part, index) => path[index] === part)
  );
}

/** The edges a write left without an end: into a removed template field, or from or into a removed output. */
function detachedEdges(
  state: GraphState,
  nodeId: string,
  update: FieldUpdate,
  before: unknown,
): Set<string> {
  const { path } = update;
  if (before === ABSENT) return new Set();
  if (
    update.op === "delete_field" &&
    path.length === TEMPLATE_PATH.length + 1 &&
    samePrefix(path, TEMPLATE_PATH)
  ) {
    const field = path[path.length - 1] as string;
    return new Set(
      state
        .connections(nodeId)
        .inputs.get(inputKey({ kind: "field", name: field })) ?? [],
    );
  }
  if (!samePrefix(path, OUTPUTS_PATH)) return new Set();
  let removedOutputs: string[];
  if (path.length === OUTPUTS_PATH.length + 1 && update.op === "delete_field") {
    removedOutputs = [selectorKey(path[path.length - 1] as Selector)];
  } else if (path.length === OUTPUTS_PATH.length) {
    // The whole list was replaced or deleted: the outputs it no longer has are gone.
    if (!Array.isArray(before))
      throw invalidOperation(
        `node ${nodeId}: data.node.outputs must be a list`,
      );
    const list = keyedListAt(state.nodes.get(nodeId), OUTPUTS_PATH)!;
    const old = new ListIndex(
      list,
      before,
      `node ${nodeId}: data.node.outputs`,
      invalidOperation,
    );
    const now = nodeOutputs(state, nodeId);
    removedOutputs = [...old.slots.keys()].filter(
      (name) => !now?.slots.has(name),
    );
  } else return new Set();
  if (removedOutputs.length === 0) return new Set();
  const connections = state.connections(nodeId);
  const detached = new Set<string>();
  for (const name of removedOutputs) {
    for (const id of connections.outputs.get(name) ?? []) detached.add(id);
    for (const id of connections.inputs.get(
      inputKey({ kind: "output", name }),
    ) ?? [])
      detached.add(id);
  }
  return detached;
}

function applyUpdateNodes(state: GraphState, updates: FieldUpdate[]): Applied {
  if (updates.length === 0) return NOTHING;
  rejectRepeatedPaths(updates, "update_nodes");
  const inverses = state.options.inverse ? new FieldInverses() : null;
  const applied: FieldUpdate[] = [];
  const detached = new Set<string>();
  updates.forEach((update, index) => {
    const context = `update_nodes[${index}]`;
    if (!state.nodes.has(update.id))
      throw invalidOperation(`update_nodes: node does not exist: ${update.id}`);
    if (!state.baseNodeIds.has(update.id))
      throw invalidOperation(
        `update_nodes: cannot update node that does not exist in the original flow: ${update.id}`,
      );
    if (update.path[0] === "id")
      throw invalidOperation(`${context}.path: cannot modify node identity`);
    if (FORBIDDEN_WHOLE_NODE_PATHS.has(JSON.stringify(update.path)))
      throw invalidOperation(
        `${context}.path: cannot update entire node data objects at path ${pathLabel(update.path)}`,
      );
    const node = state.writableNode(update.id);
    const before = applyFieldUpdate(
      state,
      node,
      node,
      update,
      context,
      inverses,
    );
    if (changed(update, before)) applied.push(update);
    // Inverses add back every edge they take away, so restoring never cascades.
    if (!state.options.restoring)
      for (const id of detachedEdges(state, update.id, update, before))
        detached.add(id);
  });

  const forward =
    applied.length > 0 ? [forwardUpdates("update_nodes", applied)] : [];
  const inverse = inverses?.operations("update_nodes") ?? [];
  const removedEdges = state.removeEdges(detached);
  if (removedEdges.length > 0) {
    forward.push({
      type: "delete_edges",
      ids: removedEdges.map((edge) => edge.id as string),
    });
    inverse.push({ type: "add_edges", edges: removedEdges });
  }
  return { forward, inverse };
}

function applyUpdateEdges(state: GraphState, updates: FieldUpdate[]): Applied {
  if (updates.length === 0) return NOTHING;
  rejectRepeatedPaths(updates, "update_edges");
  const inverses = state.options.inverse ? new FieldInverses() : null;
  const applied: FieldUpdate[] = [];
  // The handles of each edge the batch writes under a handle key, as they were before.
  const handlesBefore = new Map<string, JsonObject>();
  updates.forEach((update, index) => {
    const context = `update_edges[${index}]`;
    if (!state.edges.has(update.id))
      throw invalidOperation(`update_edges: edge does not exist: ${update.id}`);
    if (!state.baseEdgeIds.has(update.id))
      throw invalidOperation(
        `update_edges: cannot update edge that does not exist in the original flow: ${update.id}`,
      );
    const root = update.path[0];
    if (typeof root === "string" && FORBIDDEN_EDGE_UPDATE_ROOTS.has(root))
      throw invalidOperation(
        `${context}.path: cannot modify an edge's ${root}; connecting different nodes is a different edge, so delete it and add another`,
      );
    const edge = state.writableEdge(update.id);
    if (
      typeof root === "string" &&
      EDGE_HANDLE_ROOTS.has(root) &&
      !handlesBefore.has(update.id)
    )
      handlesBefore.set(update.id, handleForms(edge));
    const before = applyFieldUpdate(
      state,
      edge,
      null,
      update,
      context,
      inverses,
    );
    if (changed(update, before)) applied.push(update);
  });

  // An edge whose handles the batch changed is rewired, so it is checked like a new one.
  for (const [edgeId, before] of handlesBefore) {
    const edge = state.edges.get(edgeId)!;
    if (valuesEqual(handleForms(edge), before)) continue;
    state.forgetHandles(edge);
    if (!state.options.restoring) checkEdge(state, edge);
    state.reindexHandles(edge);
  }
  return {
    forward:
      applied.length > 0 ? [forwardUpdates("update_edges", applied)] : [],
    inverse: inverses?.operations("update_edges") ?? [],
  };
}

function applyDeleteNodes(state: GraphState, requested: string[]): Applied {
  const ids = dedupe(requested);
  if (ids.length === 0) return NOTHING;
  for (const id of ids) {
    if (!state.baseNodeIds.has(id))
      throw invalidOperation(
        `delete_nodes: cannot delete node that does not exist in the original flow: ${id}`,
      );
  }
  const removedNodes: JsonObject[] = [];
  const incident = new Set<string>();
  for (const id of ids) {
    const node = state.nodes.get(id);
    if (!node) continue;
    for (const edgeId of state.removeNode(id)) incident.add(edgeId);
    removedNodes.push(node);
  }
  if (removedNodes.length === 0) return NOTHING;
  const removedEdges = state.removeEdges(incident);
  const forward: FlowOperation[] = [
    {
      type: "delete_nodes",
      ids: removedNodes.map((node) => node.id as string),
    },
  ];
  const inverse: FlowOperation[] = [{ type: "add_nodes", nodes: removedNodes }];
  if (removedEdges.length > 0) {
    forward.push({
      type: "delete_edges",
      ids: removedEdges.map((edge) => edge.id as string),
    });
    inverse.push({ type: "add_edges", edges: removedEdges });
  }
  return { forward, inverse };
}

function applyAddEdges(state: GraphState, edges: JsonObject[]): Applied {
  if (edges.length === 0) return NOTHING;
  const seen = new Set<string>();
  const payloads: JsonObject[] = [];
  edges.forEach((edge, index) => {
    const context = `add_edges[${index}]`;
    for (const key of ["id", "source", "target"]) {
      if (!isNonEmptyString(edge[key]))
        throw invalidOperation(
          `${context}: edge must have a non-empty string ${key}`,
        );
    }
    const id = edge.id as string;
    if (seen.has(id))
      throw invalidOperation(`add_edges: duplicate edge id in request: ${id}`);
    if (state.edges.has(id))
      throw invalidOperation(`add_edges: edge id already exists: ${id}`);
    if (!state.nodes.has(edge.source as string))
      throw invalidOperation(
        `add_edges: source node does not exist: ${edge.source}`,
      );
    if (!state.nodes.has(edge.target as string))
      throw invalidOperation(
        `add_edges: target node does not exist: ${edge.target}`,
      );
    seen.add(id);
    const payload = clone(edge);
    if (!state.options.restoring) checkEdge(state, payload);
    state.insertEdge(payload);
    payloads.push(payload);
  });
  return {
    forward: [{ type: "add_edges", edges: payloads }],
    inverse: [{ type: "delete_edges", ids: [...seen] }],
  };
}

function applyDeleteEdges(state: GraphState, ids: string[]): Applied {
  const removed = state.removeEdges(ids);
  if (removed.length === 0) return NOTHING;
  return {
    forward: [
      { type: "delete_edges", ids: removed.map((edge) => edge.id as string) },
    ],
    inverse: [{ type: "add_edges", edges: removed }],
  };
}

function applyUpdateMetadata(
  state: GraphState,
  fields: JsonObject,
  requestedDeleteKeys: string[],
): Applied {
  for (const key of Object.keys(fields)) {
    if (GRAPH_COLLECTION_KEYS.has(key))
      throw invalidOperation(
        `update_metadata: cannot set graph collection key ${key}`,
      );
  }
  for (const key of requestedDeleteKeys) {
    if (GRAPH_COLLECTION_KEYS.has(key))
      throw invalidOperation(
        `update_metadata: cannot delete graph collection key ${key}`,
      );
  }
  const deleteKeys = dedupe(requestedDeleteKeys);
  if (Object.keys(fields).length === 0 && deleteKeys.length === 0)
    return NOTHING;

  const restore: JsonObject = {};
  const remove: string[] = [];
  for (const key of new Set([...Object.keys(fields), ...deleteKeys])) {
    if (key in state.flowData) restore[key] = state.flowData[key];
    else remove.push(key);
  }
  for (const [key, value] of Object.entries(fields))
    state.flowData[key] = clone(value);
  for (const key of deleteKeys) delete state.flowData[key];

  const forward: FlowOperation = { type: "update_metadata" };
  if (Object.keys(fields).length > 0) forward.fields = cloneDeep(fields);
  if (deleteKeys.length > 0) forward.delete_keys = deleteKeys;
  const inverse: FlowOperation = { type: "update_metadata" };
  if (Object.keys(restore).length > 0) inverse.fields = restore;
  if (remove.length > 0) inverse.delete_keys = remove;
  return { forward: [forward], inverse: [inverse] };
}

// --- Entry point -----------------------------------------------------------------------

function applyOperation(
  state: GraphState,
  operation: ParsedOperation,
): Applied {
  switch (operation.type) {
    case "add_nodes":
      return applyAddNodes(state, operation.nodes);
    case "update_nodes":
      return applyUpdateNodes(state, operation.updates);
    case "delete_nodes":
      return applyDeleteNodes(state, operation.ids);
    case "add_edges":
      return applyAddEdges(state, operation.edges);
    case "update_edges":
      return applyUpdateEdges(state, operation.updates);
    case "delete_edges":
      return applyDeleteEdges(state, operation.ids);
    case "update_metadata":
      return applyUpdateMetadata(
        state,
        operation.fields,
        operation.delete_keys,
      );
  }
}

/** Apply operations in order to a copy of `base`; `base` is never changed. */
export function applyFlowOperations(
  base: unknown,
  operations: FlowOperation[],
  options: ApplyOptions = {},
): ApplyResult {
  if (!Array.isArray(operations))
    throw invalidOperation("operations must be a list");
  const parsed = operations.map(parseOperation);
  const state = new GraphState(base, options);
  const forwardOperations: FlowOperation[] = [];
  const inverseOperations: FlowOperation[][] = [];
  for (const operation of parsed) {
    const { forward, inverse } = applyOperation(state, operation);
    forwardOperations.push(...forward);
    inverseOperations.push(inverse);
  }
  const result: ApplyResult = {
    flowData: state.finalize(),
    forwardOperations,
  };
  if (options.inverse) result.inverseOperations = inverseOperations;
  return result;
}
