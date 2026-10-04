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
  findItem,
  isSorted,
  type KeyedList,
  keyedListAt,
  keyOf,
  selectorName,
  sortItems,
} from "./schema";

export { jsonType } from "./canonical";

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

export type FlowGraph = JsonObject & {
  nodes: JsonObject[];
  edges: JsonObject[];
};

export type FlowOperation = JsonObject & { type: string };

export type FlowOperationErrorName =
  | "FlowOperationValidationError"
  | "FlowOperationPreconditionError"
  | "FlowDataValidationError";

export class FlowOperationError extends Error {
  constructor(
    public readonly name: FlowOperationErrorName,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    // Keep instanceof working when compiled to an ES5 target.
    Object.setPrototypeOf(this, FlowOperationError.prototype);
  }
}

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

export type ApplyOptions = {
  /**
   * Skip the `from_type` checks. The history API redacts every secret
   * field's value to null, whether it was set or not, so a reader can't tell
   * which secrets are populated; in a redacted graph a value's JSON type no
   * longer says anything, and replaying for display must not fail on it.
   * Never set this when applying operations that will be stored.
   */
  redacted?: boolean;
  /**
   * Skip the edge rules. Inverses put back a state the history already held,
   * whatever rules it broke (a stored flow may hold an edge into a field that
   * no longer exists). Never set this when applying operations that will be
   * stored.
   */
  restoring?: boolean;
  /** Also compute each operation's inverse; see `ApplyResult`. */
  inverse?: boolean;
};

const GRAPH_COLLECTION_KEYS = new Set(["nodes", "edges"]);
const NODE_OBJECT_PATHS: string[][] = [
  ["data"],
  ["data", "node"],
  ["data", "node", "template"],
];
// Replacing these whole objects would record an entire node as one opaque value.
const FORBIDDEN_WHOLE_NODE_PATHS = new Set(
  NODE_OBJECT_PATHS.map((path) => JSON.stringify(path)),
);
// An edge's endpoints are its identity: connecting other nodes is another edge.
const FORBIDDEN_EDGE_UPDATE_ROOTS = new Set(["id", "source", "target"]);
// Writes under these edge keys change which output or field the edge connects.
const EDGE_HANDLE_ROOTS = new Set(["sourceHandle", "targetHandle", "data"]);
const TEMPLATE_PATH = ["data", "node", "template"];
const OUTPUTS_PATH = ["data", "node", "outputs"];
const JSON_TYPE_NAMES = new Set([
  "object",
  "array",
  "string",
  "number",
  "boolean",
  "null",
]);

function invalidOperation(
  message: string,
  code = "FLOW_OPERATION_INVALID",
): FlowOperationError {
  return new FlowOperationError("FlowOperationValidationError", code, message);
}

function failedExpectation(message: string): FlowOperationError {
  return new FlowOperationError(
    "FlowOperationPreconditionError",
    "EXPECTATION_FAILED",
    message,
  );
}

function invalidGraph(message: string): FlowOperationError {
  return new FlowOperationError(
    "FlowDataValidationError",
    "FLOW_GRAPH_INVALID",
    message,
  );
}

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

// --- Graph state ---------------------------------------------------------------------

class GraphState {
  readonly flowData: JsonObject;
  readonly nodes = new Map<string, JsonObject>();
  readonly edges = new Map<string, JsonObject>();
  readonly edgeIdsByNode = new Map<string, Set<string>>();
  readonly baseNodeIds = new Set<string>();
  readonly baseEdgeIds = new Set<string>();
  // Containers this call made, and so may change. Everything else is shared
  // with the base graph and is never changed.
  private readonly owned = new WeakSet<object>();

  constructor(
    base: unknown,
    readonly options: ApplyOptions,
  ) {
    validateBase(base);
    const graph = base as FlowGraph;
    this.flowData = { ...graph };
    for (const node of graph.nodes) {
      this.nodes.set(node.id as string, node);
      this.baseNodeIds.add(node.id as string);
    }
    for (const edge of graph.edges) {
      this.insertEdge(edge);
      this.baseEdgeIds.add(edge.id as string);
    }
  }

  insertEdge(edge: JsonObject): void {
    const id = edge.id as string;
    this.edges.set(id, edge);
    for (const endpoint of [edge.source, edge.target] as string[]) {
      if (!this.edgeIdsByNode.has(endpoint))
        this.edgeIdsByNode.set(endpoint, new Set());
      this.edgeIdsByNode.get(endpoint)!.add(id);
    }
  }

  /** Remove edges by id; return the ones that existed, in the order given. */
  removeEdges(ids: string[]): JsonObject[] {
    const removed: JsonObject[] = [];
    for (const id of dedupe(ids)) {
      const edge = this.edges.get(id);
      if (!edge) continue;
      this.edges.delete(id);
      removed.push(edge);
      for (const endpoint of [edge.source, edge.target] as string[]) {
        const incident = this.edgeIdsByNode.get(endpoint);
        incident?.delete(id);
        if (incident && incident.size === 0)
          this.edgeIdsByNode.delete(endpoint);
      }
    }
    return removed;
  }

  /** Edge ids in the order the graph lists the edges. */
  edgesInGraphOrder(ids: Iterable<string> | undefined): string[] {
    const wanted = new Set(ids ?? []);
    if (wanted.size === 0) return [];
    return [...this.edges.keys()].filter((id) => wanted.has(id));
  }

  /**
   * A container this call may change: `value` itself if this call made it,
   * else a shallow copy. Copying only the containers along a written path
   * keeps the base untouched and shares everything else with it.
   */
  readonly own = <T extends object>(value: T): T => {
    if (this.owned.has(value)) return value;
    const copy = (Array.isArray(value) ? [...value] : { ...value }) as T;
    this.owned.add(copy);
    return copy;
  };

  writableNode(id: string): JsonObject {
    const node = this.own(this.nodes.get(id)!);
    this.nodes.set(id, node);
    return node;
  }

  writableEdge(id: string): JsonObject {
    const edge = this.own(this.edges.get(id)!);
    this.edges.set(id, edge);
    return edge;
  }

  finalize(): FlowGraph {
    return {
      ...this.flowData,
      nodes: [...this.nodes.values()],
      edges: [...this.edges.values()],
    } as FlowGraph;
  }
}

function validateBase(base: unknown): void {
  if (!isObject(base)) throw invalidGraph("flow data must be an object");
  const { nodes, edges } = base;
  if (!Array.isArray(nodes))
    throw invalidGraph("flow data nodes must be a list");
  if (!Array.isArray(edges))
    throw invalidGraph("flow data edges must be a list");
  const nodeIds = new Set<string>();
  for (const node of nodes) {
    if (!isObject(node)) throw invalidGraph("node must be an object");
    if (!isNonEmptyString(node.id))
      throw invalidGraph("node must have a non-empty string id");
    if (nodeIds.has(node.id)) throw invalidGraph("duplicate node id");
    nodeIds.add(node.id);
    requireNodeObjects(node, invalidGraph);
  }
  const edgeIds = new Set<string>();
  for (const edge of edges) {
    if (!isObject(edge)) throw invalidGraph("edge must be an object");
    if (!isNonEmptyString(edge.id))
      throw invalidGraph("edge must have a non-empty string id");
    if (edgeIds.has(edge.id)) throw invalidGraph("duplicate edge id");
    edgeIds.add(edge.id);
    for (const endpoint of [edge.source, edge.target]) {
      if (!isNonEmptyString(endpoint) || !nodeIds.has(endpoint))
        throw invalidGraph("edge endpoint must name an existing node");
    }
  }
}

function requireNodeObjects(
  node: JsonObject,
  error: (message: string) => FlowOperationError,
): void {
  let value: unknown = node;
  for (const path of NODE_OBJECT_PATHS) {
    value = isObject(value) ? value[path[path.length - 1]] : undefined;
    if (!isObject(value))
      throw error(`node ${path.join(".")} must be an object`);
  }
}

// --- Walking paths ---------------------------------------------------------------------

type ListAt = (prefix: PathSegment[]) => KeyedList | null;

const noKeyedLists: ListAt = () => null;

function nodeListAt(node: JsonObject): ListAt {
  return (prefix) => keyedListAt(node, prefix);
}

/** Check that `path[index]` is the right kind of selector on a list the schema declares keyed. */
function keyedListFor(
  path: PathSegment[],
  index: number,
  listAt: ListAt,
  context: string,
): KeyedList {
  const list = listAt(path.slice(0, index));
  if (!list)
    throw invalidOperation(
      `${context}.path[${index}]: selector on a list the node schema does not declare keyed`,
    );
  const name = selectorName(list);
  if (!(name in (path[index] as Selector)))
    throw invalidOperation(
      `${context}.path[${index}]: items of this list are selected with {"${name}": ...}`,
    );
  return list;
}

function selectedList(
  container: unknown,
  path: PathSegment[],
  index: number,
  listAt: ListAt,
  context: string,
): [KeyedList, unknown[]] {
  const list = keyedListFor(path, index, listAt, context);
  if (!Array.isArray(container))
    throw invalidOperation(
      `${context}.path[${index}]: selector on a value that is not a list`,
    );
  return [list, container];
}

type Own = <T extends object>(value: T) => T;

/**
 * The container holding the last path segment; every earlier segment must
 * exist. Each container on the way is replaced by `own(container)`, so the
 * write changes only containers the caller owns.
 */
function walkToParent(
  root: JsonObject,
  path: PathSegment[],
  listAt: ListAt,
  context: string,
  own: Own,
): unknown {
  let value: unknown = root;
  const enter = (container: JsonObject | unknown[], at: string | number) => {
    const child = (container as Record<string | number, unknown>)[at];
    if (child === null || typeof child !== "object") return child;
    const owned = own(child);
    (container as Record<string | number, unknown>)[at] = owned;
    return owned;
  };
  for (let index = 0; index < path.length - 1; index++) {
    const part = path[index];
    if (!isSelector(part)) {
      if (!isObject(value) || !(part in value))
        throw invalidOperation(
          `${context}.path[${index}]: object path part must be an existing string key: ${part}`,
        );
      value = enter(value, part);
      continue;
    }
    const [list, items] = selectedList(value, path, index, listAt, context);
    const position = findItem(list, items, selectorKey(part));
    if (position === -1)
      throw invalidOperation(
        `${context}.path[${index}]: list item does not exist: ${selectorKey(part)}`,
      );
    value = enter(items, position);
  }
  return value;
}

/** Whether `path` exists, and its value, without changing anything. */
function readPath(
  root: JsonObject,
  path: PathSegment[],
  listAt: ListAt,
  context: string,
): { exists: boolean; value?: unknown } {
  let value: unknown = root;
  for (let index = 0; index < path.length; index++) {
    const part = path[index];
    if (!isSelector(part)) {
      if (!isObject(value) || !(part in value)) return { exists: false };
      value = value[part];
      continue;
    }
    const list = keyedListFor(path, index, listAt, context);
    if (!Array.isArray(value)) return { exists: false };
    const position = findItem(list, value, selectorKey(part));
    if (position === -1) return { exists: false };
    value = value[position];
  }
  return { exists: true, value };
}

function checkExpectation(
  root: JsonObject,
  update: FieldUpdate,
  listAt: ListAt,
  context: string,
): void {
  if (!update.expect) return;
  const { exists, value } = readPath(root, update.path, listAt, context);
  if ("absent" in update.expect) {
    if (exists)
      throw failedExpectation(
        `${context}: expected ${pathLabel(update.path)} to be absent, but it exists`,
      );
    return;
  }
  if (!exists || !valuesEqual(value, update.expect.value))
    throw failedExpectation(
      `${context}: expected ${pathLabel(update.path)} to hold the given value, but found ${exists ? "a different value" : "nothing"}`,
    );
}

/**
 * Refuse a set_field that silently changes a value's JSON type. A type change
 * is declared with `from_type`, which also makes it a precondition.
 */
function checkTypeChange(
  exists: boolean,
  current: unknown,
  update: FieldUpdate,
  context: string,
  redacted: boolean,
): void {
  // Types in a redacted graph are not reliable; see ApplyOptions.
  if (redacted) return;
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

/** Apply one set_field or delete_field. Return what a delete removed, if anything. */
function applyFieldUpdate(
  root: JsonObject,
  update: FieldUpdate,
  listAt: ListAt,
  context: string,
  redacted: boolean,
  own: Own,
): { removed: boolean; value?: unknown } {
  const { path } = update;
  const parent = walkToParent(root, path, listAt, context, own);
  const last = path[path.length - 1];
  let result: { removed: boolean; value?: unknown } = { removed: false };

  if (!isSelector(last)) {
    if (!isObject(parent))
      throw invalidOperation(
        update.op === "delete_field"
          ? `${context}: delete only supports object properties and keyed list items`
          : `${context}: path must end at an object property or a keyed list item`,
      );
    if (update.op === "set_field") {
      checkTypeChange(last in parent, parent[last], update, context, redacted);
      parent[last] = clone(update.value);
    } else if (last in parent) {
      result = { removed: true, value: parent[last] };
      delete parent[last];
    }
  } else {
    const [list, items] = selectedList(
      parent,
      path,
      path.length - 1,
      listAt,
      context,
    );
    const key = selectorKey(last);
    const position = findItem(list, items, key);
    if (update.op === "set_field") {
      if (keyOf(list, update.value) !== key)
        throw invalidOperation(
          `${context}: a list item written at a selector must carry the same key: ${key}`,
        );
      checkTypeChange(
        position !== -1,
        position !== -1 ? items[position] : undefined,
        update,
        context,
        redacted,
      );
      const value = clone(update.value);
      if (position === -1) items.push(value);
      else items[position] = value;
      sortItems(list, items);
    } else if (position !== -1) {
      result = { removed: true, value: items.splice(position, 1)[0] };
    }
  }

  checkItemKeysUnchanged(root, path, listAt, context);
  return result;
}

/** After a write inside a keyed list item, the item must keep its key; re-sort a moved table row. */
function checkItemKeysUnchanged(
  root: JsonObject,
  path: PathSegment[],
  listAt: ListAt,
  context: string,
): void {
  let value: unknown = root;
  for (let index = 0; index < path.length - 1; index++) {
    const part = path[index];
    if (!isSelector(part)) {
      value = isObject(value) ? value[part] : undefined;
      continue;
    }
    const list = listAt(path.slice(0, index)) as KeyedList;
    const items = value as unknown[];
    const position = findItem(list, items, selectorKey(part));
    if (position === -1)
      throw invalidOperation(
        `${context}: cannot change a list item's ${selectorName(list)}`,
      );
    if (
      list.kind === "table" &&
      index + 2 === path.length &&
      path[index + 1] === list.position
    ) {
      sortItems(list, items);
      return;
    }
    value = items[position];
  }
}

// --- Inverses of field writes ------------------------------------------------------------

/**
 * Collects the writes that undo an update batch, read from the state each
 * write replaces. They are undone last first; a path written twice is split
 * into separate operations, since one operation may write a path once.
 */
class FieldInverses {
  private readonly entries: FieldUpdate[] = [];

  /** Record what undoes `update`; call before applying it. */
  before(
    root: JsonObject,
    update: FieldUpdate,
    listAt: ListAt,
    context: string,
  ) {
    const whole = this.wholeListToRestore(root, update, listAt, context);
    if (whole) {
      this.entries.push(whole);
      return;
    }
    const { exists, value } = readPath(root, update.path, listAt, context);
    if (!exists) {
      if (update.op === "set_field")
        this.entries.push({
          id: update.id,
          op: "delete_field",
          path: update.path,
        });
      return;
    }
    const entry: FieldUpdate = {
      id: update.id,
      op: "set_field",
      path: update.path,
      value,
    };
    if (update.op === "set_field" && jsonType(value) !== jsonType(update.value))
      entry.from_type = jsonType(update.value);
    this.entries.push(entry);
  }

  /**
   * A write that reorders a list in a way a selector write cannot reverse
   * (removing a natural-key item that was not last, or sorting a table that
   * was not sorted) is undone by writing the whole list back.
   */
  private wholeListToRestore(
    root: JsonObject,
    update: FieldUpdate,
    listAt: ListAt,
    context: string,
  ): FieldUpdate | null {
    const { path } = update;
    let value: unknown = root;
    for (let index = 0; index < path.length; index++) {
      const part = path[index];
      if (!isSelector(part)) {
        value = isObject(value) ? value[part] : undefined;
        continue;
      }
      const list = keyedListFor(path, index, listAt, context);
      if (!Array.isArray(value)) return null;
      const items = value;
      const position = findItem(list, items, selectorKey(part));
      const last = index === path.length - 1;
      const reorders =
        list.kind === "table"
          ? !isSorted(list, items)
          : last &&
            update.op === "delete_field" &&
            position !== -1 &&
            position !== items.length - 1;
      if (reorders)
        return {
          id: update.id,
          op: "set_field",
          path: path.slice(0, index),
          value: cloneDeep(items),
        };
      if (position === -1) return null;
      value = items[position];
    }
    return null;
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
  return prefix.every((part, index) => path[index] === part);
}

/** The edges a removed template field or output was connected through. */
function edgesAttachedTo(
  state: GraphState,
  nodeId: string,
  path: PathSegment[],
  removed: unknown,
): string[] {
  let fieldName: string | null = null;
  let outputName: string | null = null;
  const last = path[path.length - 1];
  if (
    path.length === TEMPLATE_PATH.length + 1 &&
    samePrefix(path, TEMPLATE_PATH) &&
    typeof last === "string" &&
    isObject(removed)
  )
    fieldName = last;
  else if (
    path.length === OUTPUTS_PATH.length + 1 &&
    samePrefix(path, OUTPUTS_PATH) &&
    isSelector(last) &&
    "key" in last
  )
    outputName = last.key;
  else return [];

  const attached: string[] = [];
  for (const edgeId of state.edgesInGraphOrder(
    state.edgeIdsByNode.get(nodeId),
  )) {
    const edge = state.edges.get(edgeId)!;
    const [sourceHandle, targetHandle] = edgeHandles(edge);
    if (fieldName !== null) {
      if (edge.target === nodeId && targetHandle?.fieldName === fieldName)
        attached.push(edgeId);
      continue;
    }
    const fromOutput =
      edge.source === nodeId && sourceHandle?.name === outputName;
    const intoLoopOutput =
      edge.target === nodeId && loopTargetOutput(targetHandle) === outputName;
    if (fromOutput || intoLoopOutput) attached.push(edgeId);
  }
  return attached;
}

function applyUpdateNodes(state: GraphState, updates: FieldUpdate[]): Applied {
  if (updates.length === 0) return NOTHING;
  rejectRepeatedPaths(updates, "update_nodes");
  const inverses = state.options.inverse ? new FieldInverses() : null;
  const cascaded: string[] = [];
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
    checkExpectation(
      state.nodes.get(update.id)!,
      update,
      nodeListAt(state.nodes.get(update.id)!),
      context,
    );
    const node = state.writableNode(update.id);
    const listAt = nodeListAt(node);
    inverses?.before(node, update, listAt, context);
    const { removed, value } = applyFieldUpdate(
      node,
      update,
      listAt,
      context,
      state.options.redacted ?? false,
      state.own,
    );
    if (removed)
      cascaded.push(...edgesAttachedTo(state, update.id, update.path, value));
  });

  const forward = [forwardUpdates("update_nodes", updates)];
  const inverse = inverses?.operations("update_nodes") ?? [];
  const removedEdges = state.removeEdges(cascaded);
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
  const endpointsBefore = new Map<string, string>();
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
    const current = state.edges.get(update.id)!;
    if (
      typeof root === "string" &&
      EDGE_HANDLE_ROOTS.has(root) &&
      !endpointsBefore.has(update.id)
    )
      endpointsBefore.set(update.id, edgeEndpointNames(current));
    checkExpectation(current, update, noKeyedLists, context);
    const edge = state.writableEdge(update.id);
    inverses?.before(edge, update, noKeyedLists, context);
    applyFieldUpdate(
      edge,
      update,
      noKeyedLists,
      context,
      state.options.redacted ?? false,
      state.own,
    );
  });

  for (const [edgeId, before] of endpointsBefore) {
    const edge = state.edges.get(edgeId)!;
    // Only an edge that now connects a different output or field makes a new
    // claim; rewriting the types or data of an edge where it stands keeps
    // legacy edges editable.
    if (edgeEndpointNames(edge) !== before)
      checkEdgeRules(state, edge, `update_edges: edge ${edgeId}`);
  }
  return {
    forward: [forwardUpdates("update_edges", updates)],
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
  const incidentEdges: string[] = [];
  for (const id of ids) {
    const node = state.nodes.get(id);
    if (!node) continue;
    state.nodes.delete(id);
    removedNodes.push(node);
    incidentEdges.push(...state.edgesInGraphOrder(state.edgeIdsByNode.get(id)));
    state.edgeIdsByNode.delete(id);
  }
  if (removedNodes.length === 0) return NOTHING;
  const removedEdges = state.removeEdges(incidentEdges);
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
    if (!state.options.restoring) checkEdgeRules(state, payload, context);
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

// --- Edge rules ------------------------------------------------------------------------

/** Parse a handle string, JSON with `œ` standing for `"`, into its object. */
function parseHandle(handle: unknown): JsonObject | null {
  if (isObject(handle)) return handle;
  if (typeof handle !== "string") return null;
  try {
    const parsed = JSON.parse(handle.replaceAll("œ", '"'));
    return isObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

/** An edge's source and target handle objects, preferring `data` over the strings. */
function edgeHandles(edge: JsonObject): [JsonObject | null, JsonObject | null] {
  const data = isObject(edge.data) ? edge.data : {};
  const source = isObject(data.sourceHandle) ? data.sourceHandle : null;
  const target = isObject(data.targetHandle) ? data.targetHandle : null;
  return [
    source ?? parseHandle(edge.sourceHandle),
    target ?? parseHandle(edge.targetHandle),
  ];
}

/**
 * The output a loop feedback edge targets, or null. A Loop component takes
 * its feedback on one of its own outputs: the target handle then names an
 * output (`name`) instead of a template field (`fieldName`).
 */
function loopTargetOutput(targetHandle: JsonObject | null): string | null {
  if (!targetHandle || "fieldName" in targetHandle) return null;
  return typeof targetHandle.name === "string" ? targetHandle.name : null;
}

function edgeEndpointNames(edge: JsonObject): string {
  const [sourceHandle, targetHandle] = edgeHandles(edge);
  const target = !targetHandle
    ? null
    : "fieldName" in targetHandle
      ? ["field", targetHandle.fieldName ?? null]
      : ["output", targetHandle.name ?? null];
  return JSON.stringify([sourceHandle?.name ?? null, target]);
}

/** Group nodes and notes have no fixed fields or outputs to check edges against. */
function isExemptNode(node: JsonObject): boolean {
  if (node.type === "noteNode") return true;
  const nodeData = isObject(node.data) ? node.data.node : undefined;
  return !isObject(nodeData) || "flow" in nodeData;
}

function nodePart(node: JsonObject, key: string): unknown {
  const nodeData = isObject(node.data) ? node.data.node : undefined;
  return isObject(nodeData) ? nodeData[key] : undefined;
}

function outputNames(node: JsonObject): Set<string> | null {
  if (isExemptNode(node)) return null;
  const outputs = nodePart(node, "outputs");
  if (!Array.isArray(outputs)) return null;
  return new Set(
    outputs
      .filter((output) => isObject(output) && typeof output.name === "string")
      .map((output) => output.name as string),
  );
}

function templateFields(node: JsonObject): JsonObject | null {
  if (isExemptNode(node)) return null;
  const template = nodePart(node, "template");
  return isObject(template) ? template : null;
}

/**
 * Check that an edge's handles name an existing output and field, and that a
 * single input stays single. Edges without handle data, and the ends of edges
 * at group nodes, notes and nodes without a template or outputs, are exempt.
 */
function checkEdgeRules(
  state: GraphState,
  edge: JsonObject,
  context: string,
): void {
  const [sourceHandle, targetHandle] = edgeHandles(edge);
  const source = state.nodes.get(edge.source as string)!;
  const target = state.nodes.get(edge.target as string)!;

  if (typeof sourceHandle?.name === "string") {
    const names = outputNames(source);
    if (names && !names.has(sourceHandle.name))
      throw invalidOperation(
        `${context}: source node ${edge.source} has no output ${sourceHandle.name}`,
        "EDGE_HANDLE_NOT_FOUND",
      );
  }

  if (!targetHandle) return;
  const loopOutput = loopTargetOutput(targetHandle);
  if (loopOutput !== null) {
    const names = outputNames(target);
    if (names && !names.has(loopOutput))
      throw invalidOperation(
        `${context}: target node ${edge.target} has no output ${loopOutput}`,
        "EDGE_HANDLE_NOT_FOUND",
      );
    return;
  }

  const fieldName = targetHandle.fieldName;
  const template = templateFields(target);
  if (!template || typeof fieldName !== "string") return;
  const field = template[fieldName];
  if (!isObject(field))
    throw invalidOperation(
      `${context}: target node ${edge.target} has no field ${fieldName}`,
      "EDGE_HANDLE_NOT_FOUND",
    );
  if (field.list === true) return;
  for (const otherId of state.edgesInGraphOrder(
    state.edgeIdsByNode.get(edge.target as string),
  )) {
    const other = state.edges.get(otherId)!;
    if (otherId === edge.id || other.target !== edge.target) continue;
    const [, otherTarget] = edgeHandles(other);
    if (otherTarget?.fieldName === fieldName)
      throw invalidOperation(
        `${context}: field ${fieldName} of node ${edge.target} takes one connection and already has one (${otherId})`,
        "EDGE_TARGET_OCCUPIED",
      );
  }
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
