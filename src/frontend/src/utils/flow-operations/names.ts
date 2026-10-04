/**
 * Names for the nodes and edges history mentions.
 *
 * Recorded operations carry ids only. A node is named from the flow as it is
 * now, else by the latest name the history shows for it (the timeline's base
 * graph, every `add_nodes` payload and every `display_name` write), else by
 * its id. A deleted edge's endpoints come from the base graph and the
 * `add_edges` payloads.
 */

import type { RecordedOperation } from "@/types/flow/revision";

export type EdgeEnds = { source: string; target: string };

/** What the history shows about names, collected once per timeline. */
export type HistoryNames = {
  nodes: Map<string, string>;
  edges: Map<string, EdgeEnds>;
};

export type FlowNames = {
  /** A node's display name, or its id when no name is known. */
  node: (id: string) => string;
  /** The ids of an edge's endpoints, if the history shows the edge. */
  edge: (id: string) => EdgeEnds | undefined;
};

const DISPLAY_NAME_PATH = ["data", "node", "display_name"];

type GraphLike = { nodes?: unknown; edges?: unknown } | null | undefined;

function list(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter((item) => item !== null && typeof item === "object")
    : [];
}

function displayName(node: Record<string, unknown>): string | undefined {
  const data = node.data as { node?: { display_name?: unknown } } | undefined;
  const name = data?.node?.display_name;
  return typeof name === "string" && name ? name : undefined;
}

function addNodes(names: Map<string, string>, nodes: unknown): void {
  for (const node of list(nodes)) {
    const name = displayName(node);
    if (typeof node.id === "string" && name) names.set(node.id, name);
  }
}

function addEdges(ends: Map<string, EdgeEnds>, edges: unknown): void {
  for (const edge of list(edges)) {
    if (
      typeof edge.id === "string" &&
      typeof edge.source === "string" &&
      typeof edge.target === "string"
    )
      ends.set(edge.id, { source: edge.source, target: edge.target });
  }
}

function isDisplayNamePath(path: unknown): boolean {
  return (
    Array.isArray(path) &&
    path.length === DISPLAY_NAME_PATH.length &&
    DISPLAY_NAME_PATH.every((part, index) => path[index] === part)
  );
}

/** Collect names from a base graph and the operations replayed from it, oldest first. */
export function collectHistoryNames(
  base: GraphLike,
  operations: Iterable<RecordedOperation>,
): HistoryNames {
  const nodes = new Map<string, string>();
  const edges = new Map<string, EdgeEnds>();
  addNodes(nodes, base?.nodes);
  addEdges(edges, base?.edges);
  for (const { operation } of operations) {
    if (operation.type === "add_nodes") addNodes(nodes, operation.nodes);
    else if (operation.type === "add_edges") addEdges(edges, operation.edges);
    else if (operation.type === "update_nodes") {
      for (const update of list(operation.updates)) {
        if (
          update.op === "set_field" &&
          typeof update.id === "string" &&
          isDisplayNamePath(update.path) &&
          typeof update.value === "string" &&
          update.value
        )
          nodes.set(update.id, update.value);
      }
    }
  }
  return { nodes, edges };
}

/** Resolve names from the flow as it is now, then from what the history shows. */
export function flowNames(
  flow: GraphLike,
  history?: HistoryNames | null,
): FlowNames {
  const current = new Map<string, string>();
  addNodes(current, flow?.nodes);
  return {
    node: (id) => current.get(id) ?? history?.nodes.get(id) ?? id,
    edge: (id) => history?.edges.get(id),
  };
}

/** Names when nothing is known: every node by its id. */
export const ID_NAMES: FlowNames = flowNames(null);
