import { cloneDeep, isEqual } from "lodash";
import type { AllNodeType, EdgeType } from "@/types/flow";
import type { FlowOperation, UpdateMetadataOp } from "@/types/flow-operations";

export function coalesceDeleteIds(ids: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const id of ids) {
    if (!seen.has(id)) {
      seen.add(id);
      result.push(id);
    }
  }
  return result;
}

function nodeSnapshot(node: AllNodeType): AllNodeType {
  const { selected: _selected, ...rest } = node;
  return rest as AllNodeType;
}

function edgeSnapshot(edge: EdgeType): EdgeType {
  const { selected: _selected, ...rest } = edge;
  return rest as EdgeType;
}

function nodesEqual(a: AllNodeType, b: AllNodeType): boolean {
  return isEqual(nodeSnapshot(a), nodeSnapshot(b));
}

function edgesEqual(a: EdgeType, b: EdgeType): boolean {
  return isEqual(edgeSnapshot(a), edgeSnapshot(b));
}

export function buildGraphDiffOperations(
  prevNodes: AllNodeType[],
  prevEdges: EdgeType[],
  nextNodes: AllNodeType[],
  nextEdges: EdgeType[],
): FlowOperation[] {
  const operations: FlowOperation[] = [];

  const prevNodeMap = new Map(prevNodes.map((node) => [node.id, node]));
  const nextNodeMap = new Map(nextNodes.map((node) => [node.id, node]));

  const addedNodes: AllNodeType[] = [];
  const updatedNodes: AllNodeType[] = [];
  const deletedNodeIds: string[] = [];

  for (const node of nextNodes) {
    const previous = prevNodeMap.get(node.id);
    if (!previous) {
      addedNodes.push(cloneDeep(node));
      continue;
    }
    if (!nodesEqual(previous, node)) {
      updatedNodes.push(cloneDeep(node));
    }
  }

  for (const node of prevNodes) {
    if (!nextNodeMap.has(node.id)) {
      deletedNodeIds.push(node.id);
    }
  }

  if (addedNodes.length > 0) {
    operations.push({ type: "add_nodes", nodes: addedNodes });
  }
  if (updatedNodes.length > 0) {
    operations.push({ type: "update_nodes", nodes: updatedNodes });
  }
  if (deletedNodeIds.length > 0) {
    operations.push({
      type: "delete_nodes",
      ids: coalesceDeleteIds(deletedNodeIds),
    });
  }

  const prevEdgeMap = new Map(prevEdges.map((edge) => [edge.id, edge]));
  const nextEdgeMap = new Map(nextEdges.map((edge) => [edge.id, edge]));

  const addedEdges: EdgeType[] = [];
  const deletedEdgeIds: string[] = [];

  for (const edge of nextEdges) {
    const previous = prevEdgeMap.get(edge.id);
    if (!previous) {
      addedEdges.push(cloneDeep(edge));
      continue;
    }
    if (!edgesEqual(previous, edge)) {
      deletedEdgeIds.push(edge.id);
      addedEdges.push(cloneDeep(edge));
    }
  }

  for (const edge of prevEdges) {
    if (!nextEdgeMap.has(edge.id)) {
      deletedEdgeIds.push(edge.id);
    }
  }

  if (deletedEdgeIds.length > 0) {
    operations.push({
      type: "delete_edges",
      ids: coalesceDeleteIds(deletedEdgeIds),
    });
  }
  if (addedEdges.length > 0) {
    operations.push({ type: "add_edges", edges: addedEdges });
  }

  return operations;
}

export function buildUpdateNodesOperation(nodes: AllNodeType[]): FlowOperation {
  return {
    type: "update_nodes",
    nodes: nodes.map((node) => cloneDeep(node)),
  };
}

export function buildUpdateMetadataOperation(
  previousData: Record<string, unknown> | null | undefined,
  nextData: Record<string, unknown> | null | undefined,
): UpdateMetadataOp | null {
  const previous = previousData ?? {};
  const next = nextData ?? {};
  const fields: Record<string, unknown> = {};
  const deleteKeys: string[] = [];
  const ignoredKeys = new Set(["nodes", "edges", "viewport"]);

  for (const [key, value] of Object.entries(next)) {
    if (ignoredKeys.has(key)) {
      continue;
    }
    if (!isEqual(previous[key], value)) {
      fields[key] = cloneDeep(value);
    }
  }

  for (const key of Object.keys(previous)) {
    if (ignoredKeys.has(key)) {
      continue;
    }
    if (!(key in next)) {
      deleteKeys.push(key);
    }
  }

  if (Object.keys(fields).length === 0 && deleteKeys.length === 0) {
    return null;
  }

  return {
    type: "update_metadata",
    fields,
    delete_keys: coalesceDeleteIds(deleteKeys),
  };
}
