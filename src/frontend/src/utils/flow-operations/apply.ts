/**
 * Applying recorded flow operations to a flow graph in the browser.
 *
 * This is the editor's copy of the server's flow operation engine
 * (`lfx.services.flow_operations`), used to play a flow's history back on the
 * canvas. It must produce exactly what the server does: both run the shared
 * cases in `src/lfx/tests/unit/services/flow_operations/fixtures/apply_cases.json`.
 *
 * Application is copy-on-write: the input graph is never changed, and the
 * result shares every node and edge an operation did not touch. Keeping one
 * graph per revision during playback therefore costs only what changed, which
 * is what makes stepping backward free.
 */

import { cloneDeep } from "lodash";

type JsonObject = Record<string, unknown>;
type PathSegment = string | number;

export type FlowGraph = JsonObject & {
  nodes: JsonObject[];
  edges: JsonObject[];
};

export type FlowOperation = JsonObject & { type: string };

export type FlowOperationErrorName =
  | "FlowOperationValidationError"
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
};

export type ApplyOptions = {
  /**
   * Skip the `from_type` checks. Operations read from the history API have
   * literal secrets replaced with null, so in a redacted graph a value's JSON
   * type no longer says anything; replaying them for display must not fail on
   * it. Never set this when applying operations that will be stored.
   */
  redacted?: boolean;
};

const GRAPH_COLLECTION_KEYS = new Set(["nodes", "edges"]);
const NODE_OBJECT_PATHS: PathSegment[][] = [
  ["data"],
  ["data", "node"],
  ["data", "node", "template"],
];
const FORBIDDEN_WHOLE_NODE_PATHS = new Set(
  NODE_OBJECT_PATHS.map((path) => JSON.stringify(path)),
);

function invalidOperation(
  message: string,
  code = "FLOW_OPERATION_INVALID",
): FlowOperationError {
  return new FlowOperationError("FlowOperationValidationError", code, message);
}

function invalidGraph(message: string): FlowOperationError {
  return new FlowOperationError(
    "FlowDataValidationError",
    "FLOW_GRAPH_INVALID",
    message,
  );
}

export function jsonType(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  switch (typeof value) {
    case "boolean":
      return "boolean";
    case "number":
      return "number";
    case "string":
      return "string";
    case "object":
      return "object";
    default:
      throw invalidGraph(`value of type ${typeof value} is not JSON`);
  }
}

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isArrayIndex(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value);
}

function clone<T>(value: T): T {
  return value === null || typeof value !== "object" ? value : cloneDeep(value);
}

class GraphState {
  readonly flowData: JsonObject;
  readonly nodes = new Map<string, JsonObject>();
  readonly edges = new Map<string, JsonObject>();
  readonly edgeIdsByNode = new Map<string, Set<string>>();
  readonly baseNodeIds = new Set<string>();
  private readonly copiedNodeIds = new Set<string>();

  constructor(
    base: unknown,
    readonly options: ApplyOptions = {},
  ) {
    validateBase(base);
    const graph = base as FlowGraph;
    this.flowData = { ...graph };
    for (const node of graph.nodes) {
      this.nodes.set(node.id as string, node);
      this.baseNodeIds.add(node.id as string);
    }
    for (const edge of graph.edges) this.insertEdge(edge);
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

  removeEdges(ids: string[]): string[] {
    const removed: string[] = [];
    for (const id of dedupe(ids)) {
      const edge = this.edges.get(id);
      if (!edge) continue;
      this.edges.delete(id);
      removed.push(id);
      for (const endpoint of [edge.source, edge.target] as string[]) {
        const incident = this.edgeIdsByNode.get(endpoint);
        incident?.delete(id);
        if (incident && incident.size === 0)
          this.edgeIdsByNode.delete(endpoint);
      }
    }
    return removed;
  }

  /** Copy a node from the base graph before its first change, so the base stays untouched. */
  writableNode(id: string): JsonObject {
    if (this.baseNodeIds.has(id) && !this.copiedNodeIds.has(id)) {
      this.nodes.set(id, cloneDeep(this.nodes.get(id)!));
      this.copiedNodeIds.add(id);
    }
    return this.nodes.get(id)!;
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
    value = isObject(value)
      ? value[path[path.length - 1] as string]
      : undefined;
    if (!isObject(value))
      throw error(`node ${path.join(".")} must be an object`);
  }
}

function dedupe(ids: string[]): string[] {
  return [...new Set(ids)];
}

function requireStringList(value: unknown, context: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string"))
    throw invalidOperation(`${context} must be a list of strings`);
  return value;
}

function requireObjectList(value: unknown, context: string): JsonObject[] {
  if (!Array.isArray(value))
    throw invalidOperation(`${context} must be a list`);
  return value as JsonObject[];
}

function applyAddNodes(
  state: GraphState,
  operation: FlowOperation,
): FlowOperation[] {
  const nodes = requireObjectList(operation.nodes, "add_nodes.nodes");
  if (nodes.length === 0) return [];
  const seen = new Set<string>();
  const payloads: JsonObject[] = [];
  for (const node of nodes) {
    if (!isObject(node))
      throw invalidOperation("add_nodes: node must be a dict");
    if (!isNonEmptyString(node.id))
      throw invalidOperation("add_nodes: node must have a non-empty string id");
    requireNodeObjects(node, invalidOperation);
    if (seen.has(node.id))
      throw invalidOperation("add_nodes: duplicate node id in request");
    if (state.nodes.has(node.id))
      throw invalidOperation("add_nodes: node id already exists");
    seen.add(node.id);
    const payload = clone(node);
    state.nodes.set(node.id, payload);
    payloads.push(payload);
  }
  return [{ type: "add_nodes", nodes: payloads }];
}

type NodeUpdate = {
  id: string;
  op: "set_field" | "delete_field";
  path: PathSegment[];
  value?: unknown;
  from_type?: string | null;
  template_field?: JsonObject | null;
};

function parseUpdates(value: unknown): NodeUpdate[] {
  const updates = requireObjectList(value, "update_nodes.updates");
  for (const update of updates) {
    if (!isObject(update))
      throw invalidOperation("update_nodes entry must be an object");
    if (update.op !== "set_field" && update.op !== "delete_field")
      throw invalidOperation(`update_nodes: unknown op ${String(update.op)}`);
    if (!isNonEmptyString(update.id))
      throw invalidOperation(
        "update_nodes entry id must be a non-empty string",
      );
    const path = update.path;
    if (!Array.isArray(path) || path.length === 0)
      throw invalidOperation("update_nodes entry path must not be empty");
    for (const segment of path) {
      if (typeof segment !== "string" && !isArrayIndex(segment))
        throw invalidOperation(
          "update_nodes entry path segments must be strings or integers",
        );
    }
    if (update.op === "set_field" && !("value" in update))
      throw invalidOperation("set_field requires a value");
  }
  return updates as unknown as NodeUpdate[];
}

function applyUpdateNodes(
  state: GraphState,
  operation: FlowOperation,
): FlowOperation[] {
  const updates = parseUpdates(operation.updates);
  if (updates.length === 0) return [];
  const seenPaths = new Set<string>();
  for (const update of updates) {
    const key = JSON.stringify([update.id, update.path]);
    if (seenPaths.has(key))
      throw invalidOperation(
        "update_nodes: multiple field updates for node/path",
      );
    seenPaths.add(key);
  }
  for (const update of updates) {
    if (!state.nodes.has(update.id))
      throw invalidOperation(`update_nodes: node does not exist: ${update.id}`);
    if (!state.baseNodeIds.has(update.id))
      throw invalidOperation(
        "update_nodes: cannot update node that does not exist in the original flow",
      );
    if (update.path[0] === "id")
      throw invalidOperation("cannot modify node identity");
    if (FORBIDDEN_WHOLE_NODE_PATHS.has(JSON.stringify(update.path)))
      throw invalidOperation("cannot update entire node data objects");
    const node = state.writableNode(update.id);
    if (update.op === "set_field")
      setField(node, update, state.options.redacted ?? false);
    else deleteField(node, update.path);
  }
  return [
    {
      type: "update_nodes",
      updates: updates.map((update) => {
        const copy: JsonObject = cloneDeep(update) as JsonObject;
        if (copy.from_type == null) delete copy.from_type;
        if (copy.template_field == null) delete copy.template_field;
        return copy;
      }),
    },
  ];
}

function containerAt(
  node: JsonObject,
  path: PathSegment[],
): JsonObject | unknown[] {
  let value: unknown = node;
  for (const segment of path.slice(0, -1)) {
    if (Array.isArray(value)) {
      if (!isArrayIndex(segment))
        throw invalidOperation("array path part must be an integer index");
      if (segment < 0 || segment >= value.length)
        throw invalidOperation("array index is out of range");
      value = value[segment];
    } else if (isObject(value)) {
      if (typeof segment !== "string" || !(segment in value))
        throw invalidOperation(
          "object path part must be an existing string key",
        );
      value = value[segment];
    } else {
      throw invalidOperation("path must pass through objects or arrays");
    }
  }
  if (!Array.isArray(value) && !isObject(value))
    throw invalidOperation("path must end at an object or array");
  return value;
}

function setField(
  node: JsonObject,
  update: NodeUpdate,
  redacted: boolean,
): void {
  const container = containerAt(node, update.path);
  const last = update.path[update.path.length - 1];
  const exists = Array.isArray(container)
    ? isArrayIndex(last) && last >= 0 && last < container.length
    : typeof last === "string" && last in container;
  const current = exists
    ? (container as Record<PathSegment, unknown>)[last]
    : undefined;

  // Types in a redacted graph are not reliable; see ApplyOptions.
  if (!redacted && update.from_type == null) {
    if (exists && jsonType(current) !== jsonType(update.value))
      throw invalidOperation(
        "set_field changes a value's JSON type without declaring from_type",
        "FIELD_TYPE_CHANGE_UNDECLARED",
      );
  } else if (!redacted && (!exists || jsonType(current) !== update.from_type)) {
    throw invalidOperation(
      "set_field from_type does not match the value it replaces",
      "FIELD_TYPE_PRECONDITION_FAILED",
    );
  }

  if (Array.isArray(container)) {
    if (!isArrayIndex(last))
      throw invalidOperation("array path part must be an integer index");
    if (last < 0 || last >= container.length)
      throw invalidOperation("array index is out of range");
    container[last] = clone(update.value);
  } else {
    if (typeof last !== "string")
      throw invalidOperation("object path part must be a string");
    container[last] = clone(update.value);
  }
}

function deleteField(node: JsonObject, path: PathSegment[]): void {
  const container = containerAt(node, path);
  const last = path[path.length - 1];
  if (Array.isArray(container) || typeof last !== "string")
    throw invalidOperation("delete only supports object properties");
  delete container[last];
}

function applyDeleteNodes(
  state: GraphState,
  operation: FlowOperation,
): FlowOperation[] {
  const ids = dedupe(requireStringList(operation.ids, "delete_nodes.ids"));
  if (ids.length === 0) return [];
  for (const id of ids) {
    if (!state.baseNodeIds.has(id))
      throw invalidOperation(
        "delete_nodes: cannot delete node that does not exist in the original flow",
      );
  }
  const removedNodes: string[] = [];
  const incidentEdges: string[] = [];
  for (const id of ids) {
    if (!state.nodes.has(id)) continue;
    state.nodes.delete(id);
    removedNodes.push(id);
    incidentEdges.push(...(state.edgeIdsByNode.get(id) ?? []));
    state.edgeIdsByNode.delete(id);
  }
  if (removedNodes.length === 0) return [];
  const removedEdges = state.removeEdges(incidentEdges);
  const forward: FlowOperation[] = [
    { type: "delete_nodes", ids: removedNodes },
  ];
  if (removedEdges.length > 0)
    forward.push({ type: "delete_edges", ids: removedEdges });
  return forward;
}

function applyAddEdges(
  state: GraphState,
  operation: FlowOperation,
): FlowOperation[] {
  const edges = requireObjectList(operation.edges, "add_edges.edges");
  if (edges.length === 0) return [];
  const seen = new Set<string>();
  const payloads: JsonObject[] = [];
  for (const edge of edges) {
    if (!isObject(edge))
      throw invalidOperation("add_edges: edge must be a dict");
    if (!isNonEmptyString(edge.id))
      throw invalidOperation("add_edges: edge must have a non-empty string id");
    if (!isNonEmptyString(edge.source))
      throw invalidOperation(
        "add_edges: edge must have a non-empty string source",
      );
    if (!isNonEmptyString(edge.target))
      throw invalidOperation(
        "add_edges: edge must have a non-empty string target",
      );
    if (seen.has(edge.id))
      throw invalidOperation("add_edges: duplicate edge id in request");
    if (state.edges.has(edge.id))
      throw invalidOperation("add_edges: edge id already exists");
    if (!state.nodes.has(edge.source))
      throw invalidOperation("add_edges: source node does not exist");
    if (!state.nodes.has(edge.target))
      throw invalidOperation("add_edges: target node does not exist");
    seen.add(edge.id);
    const payload = clone(edge);
    state.insertEdge(payload);
    payloads.push(payload);
  }
  return [{ type: "add_edges", edges: payloads }];
}

function applyDeleteEdges(
  state: GraphState,
  operation: FlowOperation,
): FlowOperation[] {
  const removed = state.removeEdges(
    requireStringList(operation.ids, "delete_edges.ids"),
  );
  return removed.length > 0 ? [{ type: "delete_edges", ids: removed }] : [];
}

function applyUpdateMetadata(
  state: GraphState,
  operation: FlowOperation,
): FlowOperation[] {
  const fields = (operation.fields ?? {}) as JsonObject;
  if (!isObject(fields))
    throw invalidOperation("update_metadata.fields must be an object");
  const deleteKeys = dedupe(
    requireStringList(
      operation.delete_keys ?? [],
      "update_metadata.delete_keys",
    ),
  );
  for (const key of Object.keys(fields)) {
    if (GRAPH_COLLECTION_KEYS.has(key))
      throw invalidOperation(
        `update_metadata: cannot set graph collection key ${key}`,
      );
  }
  for (const key of deleteKeys) {
    if (GRAPH_COLLECTION_KEYS.has(key))
      throw invalidOperation(
        `update_metadata: cannot delete graph collection key ${key}`,
      );
  }
  if (Object.keys(fields).length === 0 && deleteKeys.length === 0) return [];
  for (const [key, value] of Object.entries(fields))
    state.flowData[key] = clone(value);
  for (const key of deleteKeys) delete state.flowData[key];

  const forward: FlowOperation = { type: "update_metadata" };
  if (Object.keys(fields).length > 0) forward.fields = cloneDeep(fields);
  if (deleteKeys.length > 0) forward.delete_keys = deleteKeys;
  return [forward];
}

const HANDLERS: Record<
  string,
  (state: GraphState, operation: FlowOperation) => FlowOperation[]
> = {
  add_nodes: applyAddNodes,
  update_nodes: applyUpdateNodes,
  delete_nodes: applyDeleteNodes,
  add_edges: applyAddEdges,
  delete_edges: applyDeleteEdges,
  update_metadata: applyUpdateMetadata,
};

/** Apply operations in order to a copy of `base`; `base` is never changed. */
export function applyFlowOperations(
  base: unknown,
  operations: FlowOperation[],
  options: ApplyOptions = {},
): ApplyResult {
  const state = new GraphState(base, options);
  const forwardOperations: FlowOperation[] = [];
  for (const operation of operations) {
    const handler = isObject(operation)
      ? HANDLERS[operation.type as string]
      : undefined;
    if (!handler)
      throw invalidOperation(
        `Unsupported operation type: ${String(operation?.type)}`,
      );
    forwardOperations.push(...handler(state, operation));
  }
  return { flowData: state.finalize(), forwardOperations };
}
