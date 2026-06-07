import { cloneDeep, isEqual } from "lodash";
import type { AllNodeType, EdgeType } from "@/types/flow";
import type {
  FlowOperation,
  NodeFieldPath,
  UpdateMetadataOp,
  UpdateNodeEntry,
  UpdateNodesOp,
} from "@/types/flow-operations";
import {
  deleteValueAtPath,
  getValueAtPath,
  setValueAtPath,
} from "./flow-operation-path";

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

export function nodeSnapshotForFlowOperation(node: AllNodeType): AllNodeType {
  const {
    selected: _selected,
    measured: _measured,
    dragging: _dragging,
    ...rest
  } = node;
  return cloneDeep(rest) as AllNodeType;
}

export function edgeSnapshotForFlowOperation(edge: EdgeType): EdgeType {
  const { selected: _selected, ...rest } = edge;
  return cloneDeep(rest) as EdgeType;
}

function nodesEqual(a: AllNodeType, b: AllNodeType): boolean {
  return isEqual(
    nodeSnapshotForFlowOperation(a),
    nodeSnapshotForFlowOperation(b),
  );
}

function edgesEqual(a: EdgeType, b: EdgeType): boolean {
  return isEqual(
    edgeSnapshotForFlowOperation(a),
    edgeSnapshotForFlowOperation(b),
  );
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function buildSetNodeFieldUpdate(
  id: string,
  path: NodeFieldPath,
  value: unknown,
): UpdateNodeEntry {
  return { id, op: "set_field", path: [...path], value: cloneDeep(value) };
}

export function buildDeleteNodeFieldUpdate(
  id: string,
  path: NodeFieldPath,
): UpdateNodeEntry {
  return { id, op: "delete_field", path: [...path] };
}

export function buildNodeFieldDiffUpdates(
  id: string,
  previous: Record<string, unknown>,
  next: Record<string, unknown>,
  pathPrefix: NodeFieldPath = [],
): UpdateNodeEntry[] {
  const updates: UpdateNodeEntry[] = [];
  const previousKeyList = Object.keys(previous);
  const nextKeyList = Object.keys(next);
  const previousKeys = new Set(previousKeyList);
  const nextKeys = new Set(nextKeyList);

  for (const key of nextKeyList) {
    if (key === "id" && pathPrefix.length === 0) {
      continue;
    }

    const childPath: NodeFieldPath = [...pathPrefix, key];
    const previousValue = previous[key];
    const nextValue = next[key];

    if (!previousKeys.has(key)) {
      updates.push(buildSetNodeFieldUpdate(id, childPath, nextValue));
      continue;
    }

    if (isPlainObject(previousValue) && isPlainObject(nextValue)) {
      updates.push(
        ...buildNodeFieldDiffUpdates(id, previousValue, nextValue, childPath),
      );
      continue;
    }

    if (!isEqual(previousValue, nextValue)) {
      updates.push(buildSetNodeFieldUpdate(id, childPath, nextValue));
    }
  }

  for (const key of previousKeyList) {
    if (key === "id" && pathPrefix.length === 0) {
      continue;
    }
    if (!nextKeys.has(key)) {
      updates.push(buildDeleteNodeFieldUpdate(id, [...pathPrefix, key]));
    }
  }

  return updates;
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
  const updatedNodes: UpdateNodeEntry[] = [];
  const deletedNodeIds: string[] = [];

  for (const node of nextNodes) {
    const previous = prevNodeMap.get(node.id);
    if (!previous) {
      addedNodes.push(nodeSnapshotForFlowOperation(node));
      continue;
    }
    if (!nodesEqual(previous, node)) {
      updatedNodes.push(
        ...buildNodeFieldDiffUpdates(
          node.id,
          nodeSnapshotForFlowOperation(previous) as Record<string, unknown>,
          nodeSnapshotForFlowOperation(node) as Record<string, unknown>,
        ),
      );
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
    operations.push({ type: "update_nodes", updates: updatedNodes });
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
      addedEdges.push(edgeSnapshotForFlowOperation(edge));
      continue;
    }
    if (!edgesEqual(previous, edge)) {
      deletedEdgeIds.push(edge.id);
      addedEdges.push(edgeSnapshotForFlowOperation(edge));
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

export function buildUpdateNodeFieldsOperation(
  updates: UpdateNodeEntry[],
): UpdateNodesOp | null {
  if (updates.length === 0) {
    return null;
  }
  return {
    type: "update_nodes",
    updates: updates.map((update) => cloneDeep(update)),
  };
}

function getNodeMap(nodes: AllNodeType[]): Map<string, AllNodeType> {
  return new Map(nodes.map((node) => [node.id, node]));
}

function getEdgeMap(edges: EdgeType[]): Map<string, EdgeType> {
  return new Map(edges.map((edge) => [edge.id, edge]));
}

function appendOperation(
  groups: FlowOperation[][],
  operation: FlowOperation | null,
): void {
  if (!operation) {
    return;
  }
  switch (operation.type) {
    case "add_nodes":
      if (operation.nodes.length > 0) groups.push([operation]);
      return;
    case "update_nodes":
      if (operation.updates.length > 0) groups.push([operation]);
      return;
    case "delete_nodes":
      if (operation.ids.length > 0) groups.push([operation]);
      return;
    case "add_edges":
      if (operation.edges.length > 0) groups.push([operation]);
      return;
    case "delete_edges":
      if (operation.ids.length > 0) groups.push([operation]);
      return;
    case "update_metadata":
      if (
        Object.keys(operation.fields).length > 0 ||
        (operation.delete_keys?.length ?? 0) > 0
      ) {
        groups.push([operation]);
      }
      return;
    default:
      return;
  }
}

function applyGraphOperationToState(
  nodes: AllNodeType[],
  edges: EdgeType[],
  operation: FlowOperation,
): { nodes: AllNodeType[]; edges: EdgeType[] } {
  switch (operation.type) {
    case "add_nodes": {
      const existingIds = new Set(nodes.map((node) => node.id));
      return {
        nodes: [
          ...nodes,
          ...operation.nodes
            .filter((node) => !existingIds.has(node.id))
            .map((node) => cloneDeep(node)),
        ],
        edges,
      };
    }
    case "update_nodes": {
      const updatedById = getNodeMap(nodes.map((node) => cloneDeep(node)));
      for (const update of operation.updates) {
        const currentNode = updatedById.get(update.id);
        if (!currentNode) {
          continue;
        }
        if (update.op === "set_field") {
          setValueAtPath(currentNode, update.path, update.value);
        } else {
          deleteValueAtPath(currentNode, update.path);
        }
      }
      return {
        nodes: Array.from(updatedById.values()),
        edges,
      };
    }
    case "delete_nodes": {
      const nodeIds = new Set(coalesceDeleteIds(operation.ids));
      return {
        nodes: nodes.filter((node) => !nodeIds.has(node.id)),
        edges: edges.filter(
          (edge) => !nodeIds.has(edge.source) && !nodeIds.has(edge.target),
        ),
      };
    }
    case "add_edges": {
      const existingIds = new Set(edges.map((edge) => edge.id));
      return {
        nodes,
        edges: [
          ...edges,
          ...operation.edges
            .filter((edge) => !existingIds.has(edge.id))
            .map((edge) => cloneDeep(edge)),
        ],
      };
    }
    case "delete_edges": {
      const edgeIds = new Set(coalesceDeleteIds(operation.ids));
      return {
        nodes,
        edges: edges.filter((edge) => !edgeIds.has(edge.id)),
      };
    }
    case "update_metadata":
      return { nodes, edges };
    default:
      return { nodes, edges };
  }
}

function applyMetadataOperationToState(
  data: Record<string, unknown>,
  operation: UpdateMetadataOp,
): Record<string, unknown> {
  const nextData = { ...data };
  for (const [key, value] of Object.entries(operation.fields)) {
    if (key !== "nodes" && key !== "edges") {
      nextData[key] = cloneDeep(value);
    }
  }
  for (const key of operation.delete_keys ?? []) {
    if (key !== "nodes" && key !== "edges") {
      delete nextData[key];
    }
  }
  return nextData;
}

function buildInverseMetadataOperation(
  data: Record<string, unknown>,
  operation: UpdateMetadataOp,
): UpdateMetadataOp | null {
  const fields: Record<string, unknown> = {};
  const deleteKeys: string[] = [];
  const touchedKeys = new Set([
    ...Object.keys(operation.fields),
    ...(operation.delete_keys ?? []),
  ]);

  touchedKeys.forEach((key) => {
    if (key === "nodes" || key === "edges") {
      return;
    }
    if (Object.hasOwn(data, key)) {
      fields[key] = cloneDeep(data[key]);
    } else {
      deleteKeys.push(key);
    }
  });

  if (Object.keys(fields).length === 0 && deleteKeys.length === 0) {
    return null;
  }

  return {
    type: "update_metadata",
    fields,
    delete_keys: coalesceDeleteIds(deleteKeys),
  };
}

export function buildInverseFlowOperations(
  previousNodes: AllNodeType[],
  previousEdges: EdgeType[],
  previousData: Record<string, unknown> | null | undefined,
  forwardOps: FlowOperation[],
): FlowOperation[] {
  let currentNodes = cloneDeep(previousNodes);
  let currentEdges = cloneDeep(previousEdges);
  let currentData = { ...(previousData ?? {}) };
  const inverseGroups: FlowOperation[][] = [];

  for (const operation of forwardOps) {
    switch (operation.type) {
      case "add_nodes": {
        appendOperation(inverseGroups, {
          type: "delete_nodes",
          ids: coalesceDeleteIds(operation.nodes.map((node) => node.id)),
        });
        break;
      }
      case "update_nodes": {
        const inverseUpdates: UpdateNodeEntry[] = [];
        for (const update of operation.updates) {
          const currentNode = getNodeMap(currentNodes).get(update.id);
          if (!currentNode) {
            continue;
          }

          if (update.op === "set_field") {
            const previous = getValueAtPath(currentNode, update.path);
            inverseUpdates.unshift(
              previous.exists
                ? buildSetNodeFieldUpdate(
                    update.id,
                    update.path,
                    previous.value,
                  )
                : buildDeleteNodeFieldUpdate(update.id, update.path),
            );
          } else {
            const previous = getValueAtPath(currentNode, update.path);
            if (previous.exists) {
              inverseUpdates.unshift(
                buildSetNodeFieldUpdate(update.id, update.path, previous.value),
              );
            }
          }

          const nextGraph = applyGraphOperationToState(
            currentNodes,
            currentEdges,
            {
              type: "update_nodes",
              updates: [update],
            },
          );
          currentNodes = nextGraph.nodes;
          currentEdges = nextGraph.edges;
        }
        appendOperation(inverseGroups, {
          type: "update_nodes",
          updates: inverseUpdates,
        });
        break;
      }
      case "delete_nodes": {
        const ids = new Set(coalesceDeleteIds(operation.ids));
        const deletedNodes = currentNodes
          .filter((node) => ids.has(node.id))
          .map((node) => cloneDeep(node));
        const deletedEdges = currentEdges
          .filter((edge) => ids.has(edge.source) || ids.has(edge.target))
          .map((edge) => cloneDeep(edge));
        const inverseGroup: FlowOperation[] = [];
        if (deletedNodes.length > 0) {
          inverseGroup.push({ type: "add_nodes", nodes: deletedNodes });
        }
        if (deletedEdges.length > 0) {
          inverseGroup.push({ type: "add_edges", edges: deletedEdges });
        }
        if (inverseGroup.length > 0) {
          inverseGroups.push(inverseGroup);
        }
        break;
      }
      case "add_edges": {
        appendOperation(inverseGroups, {
          type: "delete_edges",
          ids: coalesceDeleteIds(operation.edges.map((edge) => edge.id)),
        });
        break;
      }
      case "delete_edges": {
        const currentEdgeMap = getEdgeMap(currentEdges);
        const deletedEdges = coalesceDeleteIds(operation.ids)
          .map((id) => currentEdgeMap.get(id))
          .filter((edge): edge is EdgeType => Boolean(edge))
          .map((edge) => cloneDeep(edge));
        appendOperation(inverseGroups, {
          type: "add_edges",
          edges: deletedEdges,
        });
        break;
      }
      case "update_metadata": {
        appendOperation(
          inverseGroups,
          buildInverseMetadataOperation(currentData, operation),
        );
        currentData = applyMetadataOperationToState(currentData, operation);
        break;
      }
      default:
        break;
    }

    if (operation.type !== "update_nodes") {
      const nextGraph = applyGraphOperationToState(
        currentNodes,
        currentEdges,
        operation,
      );
      currentNodes = nextGraph.nodes;
      currentEdges = nextGraph.edges;
    }
  }

  return inverseGroups.reverse().flat();
}

export type FlowOperationTouchSet = {
  nodeIds: Set<string>;
  nodeFieldNodeIds: Set<string>;
  nodeFieldPaths: Set<string>;
  edgeIds: Set<string>;
  edgeEndpointNodeIds: Set<string>;
  metadataKeys: Set<string>;
};

export function collectFlowOperationTouches(
  operations: FlowOperation[],
): FlowOperationTouchSet {
  const touches: FlowOperationTouchSet = {
    nodeIds: new Set(),
    nodeFieldNodeIds: new Set(),
    nodeFieldPaths: new Set(),
    edgeIds: new Set(),
    edgeEndpointNodeIds: new Set(),
    metadataKeys: new Set(),
  };

  for (const operation of operations) {
    switch (operation.type) {
      case "add_nodes":
        for (const node of operation.nodes) {
          touches.nodeIds.add(node.id);
        }
        break;
      case "update_nodes":
        for (const update of operation.updates) {
          touches.nodeFieldNodeIds.add(update.id);
          touches.nodeFieldPaths.add(
            `${update.id}:${JSON.stringify(update.path)}`,
          );
        }
        break;
      case "delete_nodes":
        for (const id of operation.ids) {
          touches.nodeIds.add(id);
        }
        break;
      case "add_edges":
        for (const edge of operation.edges) {
          touches.edgeIds.add(edge.id);
          touches.edgeEndpointNodeIds.add(edge.source);
          touches.edgeEndpointNodeIds.add(edge.target);
        }
        break;
      case "delete_edges":
        for (const id of operation.ids) {
          touches.edgeIds.add(id);
        }
        break;
      case "update_metadata":
        for (const key of Object.keys(operation.fields)) {
          touches.metadataKeys.add(key);
        }
        for (const key of operation.delete_keys ?? []) {
          touches.metadataKeys.add(key);
        }
        break;
      default:
        break;
    }
  }

  return touches;
}

function setsIntersect(a: Set<string>, b: Set<string>): boolean {
  for (const value of Array.from(a)) {
    if (b.has(value)) {
      return true;
    }
  }
  return false;
}

function parseNodeFieldPathKey(
  key: string,
): { nodeId: string; path: NodeFieldPath } | null {
  const separatorIndex = key.indexOf(":");
  if (separatorIndex === -1) {
    return null;
  }
  try {
    const path = JSON.parse(key.slice(separatorIndex + 1));
    return Array.isArray(path)
      ? { nodeId: key.slice(0, separatorIndex), path }
      : null;
  } catch {
    return null;
  }
}

function pathIsPrefix(left: NodeFieldPath, right: NodeFieldPath): boolean {
  if (left.length > right.length) {
    return false;
  }
  return left.every((segment, index) => segment === right[index]);
}

function nodeFieldPathsIntersect(a: Set<string>, b: Set<string>): boolean {
  for (const leftKey of Array.from(a)) {
    const left = parseNodeFieldPathKey(leftKey);
    if (!left) {
      continue;
    }
    for (const rightKey of Array.from(b)) {
      const right = parseNodeFieldPathKey(rightKey);
      if (!right || left.nodeId !== right.nodeId) {
        continue;
      }
      if (
        pathIsPrefix(left.path, right.path) ||
        pathIsPrefix(right.path, left.path)
      ) {
        return true;
      }
    }
  }
  return false;
}

export function flowOperationTouchesIntersect(
  left: FlowOperationTouchSet,
  right: FlowOperationTouchSet,
): boolean {
  return (
    setsIntersect(left.nodeIds, right.nodeIds) ||
    setsIntersect(left.nodeIds, right.nodeFieldNodeIds) ||
    setsIntersect(left.nodeFieldNodeIds, right.nodeIds) ||
    setsIntersect(left.nodeIds, right.edgeEndpointNodeIds) ||
    setsIntersect(left.edgeEndpointNodeIds, right.nodeIds) ||
    nodeFieldPathsIntersect(left.nodeFieldPaths, right.nodeFieldPaths) ||
    setsIntersect(left.edgeIds, right.edgeIds) ||
    setsIntersect(left.metadataKeys, right.metadataKeys)
  );
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
