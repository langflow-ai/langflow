/**
 * The indexed graph an apply call works on.
 *
 * Nodes and edges are indexed by id, and edges by the nodes they touch.
 * Indexes that only some writes need are built the first time a write asks
 * for them and kept up to date afterwards: keyed lists by item key, each
 * edge's handles, and each node's connections by the input or output they use.
 *
 * Application is copy-on-write: the base graph is never changed, and the
 * result shares every container a write did not pass through.
 */

import {
  type Connections,
  type Handles,
  inputKey,
  readHandles,
} from "./edge-rules";
import { invalidGraph, invalidOperation } from "./errors";
import { ListIndex } from "./keyed-lists";
import type { KeyedList } from "./schema";

type JsonObject = Record<string, unknown>;

export type FlowGraph = JsonObject & {
  nodes: JsonObject[];
  edges: JsonObject[];
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
   * Apply inverses. Inverses put back a state the history already held,
   * whatever rules it broke (a stored flow may hold an edge into a field that
   * no longer exists), and they add and delete every edge they touch
   * explicitly. So the edge rules and the edges a removed field or output
   * would take with it are both skipped. Never set this when applying
   * operations that will be stored.
   */
  restoring?: boolean;
  /** Also compute each operation's inverse; see `ApplyResult`. */
  inverse?: boolean;
};

// Every node carries these as objects for its whole lifetime; operations patch
// inside them instead of replacing them.
export const NODE_OBJECT_PATHS: string[][] = [
  ["data"],
  ["data", "node"],
  ["data", "node", "template"],
];

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

export class GraphState {
  readonly flowData: JsonObject;
  readonly nodes = new Map<string, JsonObject>();
  readonly edges = new Map<string, JsonObject>();
  readonly edgeIdsByNode = new Map<string, Set<string>>();
  readonly baseNodeIds = new Set<string>();
  readonly baseEdgeIds = new Set<string>();
  // Containers this call made, and so may change. Everything else is shared
  // with the base graph and is never changed.
  private readonly owned = new WeakSet<object>();
  // Keyed lists indexed so far, by list.
  private readonly listIndexes = new WeakMap<unknown[], ListIndex>();
  // Handles read so far, by edge id.
  private readonly handlesById = new Map<string, Handles>();
  // Connections indexed so far, by node id. A node's entry, once built, covers
  // every edge at that node, and every one of those edges has its handles read.
  private readonly connectionsById = new Map<string, Connections>();

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
      this.edges.set(edge.id as string, edge);
      this.attach(edge);
      this.baseEdgeIds.add(edge.id as string);
    }
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

  /** The index of `items`, built the first time the list is addressed. */
  listIndex(list: KeyedList, items: unknown[], context: string): ListIndex {
    let index = this.listIndexes.get(items);
    if (!index) {
      index = new ListIndex(list, items, context, invalidOperation);
      this.listIndexes.set(items, index);
    }
    return index;
  }

  /** An edge's handles, read strictly the first time. */
  handles(edge: JsonObject): Handles {
    const id = edge.id as string;
    let handles = this.handlesById.get(id);
    if (!handles) {
      handles = readHandles(edge);
      this.handlesById.set(id, handles);
    }
    return handles;
  }

  /** A node's connections, reading the handles of its edges the first time. */
  connections(nodeId: string): Connections {
    let connections = this.connectionsById.get(nodeId);
    if (!connections) {
      connections = { inputs: new Map(), outputs: new Map() };
      for (const edgeId of this.edgeIdsByNode.get(nodeId) ?? []) {
        const edge = this.edges.get(edgeId)!;
        connect(connections, nodeId, edge, this.handles(edge));
      }
      this.connectionsById.set(nodeId, connections);
    }
    return connections;
  }

  insertEdge(edge: JsonObject): void {
    this.edges.set(edge.id as string, edge);
    this.attach(edge);
    this.indexConnections(edge);
  }

  /** Remove edges by id; return the ones that existed, each once, in the order given. */
  removeEdges(ids: Iterable<string>): JsonObject[] {
    const removed: JsonObject[] = [];
    for (const id of new Set(ids)) {
      const edge = this.edges.get(id);
      if (!edge) continue;
      this.edges.delete(id);
      removed.push(edge);
      this.unindexConnections(edge);
      for (const endpoint of [edge.source, edge.target] as string[]) {
        const incident = this.edgeIdsByNode.get(endpoint);
        incident?.delete(id);
        if (incident && incident.size === 0)
          this.edgeIdsByNode.delete(endpoint);
      }
    }
    return removed;
  }

  /** Remove a node and return the ids of the edges at it, which the caller removes. */
  removeNode(nodeId: string): Set<string> {
    this.nodes.delete(nodeId);
    this.connectionsById.delete(nodeId);
    return new Set(this.edgeIdsByNode.get(nodeId) ?? []);
  }

  /** Drop what is indexed about an edge's handles before they are rewritten. */
  forgetHandles(edge: JsonObject): void {
    this.unindexConnections(edge);
  }

  /** Index an edge's handles again after they were rewritten and checked. */
  reindexHandles(edge: JsonObject): void {
    this.indexConnections(edge);
  }

  finalize(): FlowGraph {
    return {
      ...this.flowData,
      nodes: [...this.nodes.values()],
      edges: [...this.edges.values()],
    } as FlowGraph;
  }

  private attach(edge: JsonObject): void {
    for (const endpoint of [edge.source, edge.target] as string[]) {
      if (!this.edgeIdsByNode.has(endpoint))
        this.edgeIdsByNode.set(endpoint, new Set());
      this.edgeIdsByNode.get(endpoint)!.add(edge.id as string);
    }
  }

  private indexConnections(edge: JsonObject): void {
    for (const nodeId of new Set([edge.source, edge.target] as string[])) {
      const connections = this.connectionsById.get(nodeId);
      if (connections) connect(connections, nodeId, edge, this.handles(edge));
    }
  }

  private unindexConnections(edge: JsonObject): void {
    const id = edge.id as string;
    const handles = this.handlesById.get(id);
    if (!handles) return;
    this.handlesById.delete(id);
    for (const nodeId of new Set([edge.source, edge.target] as string[])) {
      const connections = this.connectionsById.get(nodeId);
      if (connections) disconnect(connections, nodeId, edge, handles);
    }
  }
}

function addTo(map: Map<string, Set<string>>, key: string, id: string) {
  if (!map.has(key)) map.set(key, new Set());
  map.get(key)!.add(id);
}

function connect(
  connections: Connections,
  nodeId: string,
  edge: JsonObject,
  handles: Handles,
): void {
  const id = edge.id as string;
  if (edge.target === nodeId)
    addTo(connections.inputs, inputKey(handles.input), id);
  if (edge.source === nodeId) addTo(connections.outputs, handles.output, id);
}

function disconnect(
  connections: Connections,
  nodeId: string,
  edge: JsonObject,
  handles: Handles,
): void {
  const id = edge.id as string;
  if (edge.target === nodeId)
    connections.inputs.get(inputKey(handles.input))?.delete(id);
  if (edge.source === nodeId)
    connections.outputs.get(handles.output)?.delete(id);
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

/** Check that a node carries `data`, `data.node` and `data.node.template` as objects. */
export function requireNodeObjects(
  node: JsonObject,
  error: (message: string) => Error,
): void {
  let value: unknown = node;
  for (const path of NODE_OBJECT_PATHS) {
    value = isObject(value) ? value[path[path.length - 1]] : undefined;
    if (!isObject(value))
      throw error(`node ${path.join(".")} must be an object`);
  }
}
