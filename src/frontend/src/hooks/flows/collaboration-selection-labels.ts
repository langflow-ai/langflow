import type { AllNodeType, EdgeType } from "@/types/flow";
import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

export function getNodeDisplayLabel(node: AllNodeType): string {
  const displayName = node.data?.node?.display_name;
  if (typeof displayName === "string" && displayName.trim().length > 0) {
    return displayName;
  }
  if (typeof node.data?.type === "string" && node.data.type.length > 0) {
    return node.data.type;
  }
  return node.id;
}

export function getEdgeEndpointLabel(
  nodeId: string,
  nodesById: Map<string, AllNodeType>,
): string {
  const node = nodesById.get(nodeId);
  if (!node) {
    return nodeId;
  }
  return getNodeDisplayLabel(node);
}

export function formatEdgeSelectionLabel(
  edge: EdgeType,
  nodes: AllNodeType[],
): string {
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const sourceLabel = getEdgeEndpointLabel(edge.source, nodesById);
  const targetLabel = getEdgeEndpointLabel(edge.target, nodesById);
  return `${sourceLabel} → ${targetLabel}`;
}

export type ResolveCollaborationSelectionLabelOptions = {
  selectedNodeLabel?: (node: AllNodeType) => string;
  selectedEdgeLabel?: (edge: EdgeType, nodes: AllNodeType[]) => string;
  staleSelectionLabel?: string;
};

export function resolveCollaborationSelectionLabel(
  selected: CollaborationSelectionTarget | null,
  nodes: AllNodeType[],
  edges: EdgeType[],
  options?: ResolveCollaborationSelectionLabelOptions,
): string | null {
  if (!selected) {
    return null;
  }

  const staleLabel = options?.staleSelectionLabel ?? "Unavailable selection";

  if (selected.kind === "node") {
    const node = nodes.find((entry) => entry.id === selected.id);
    if (!node) {
      return staleLabel;
    }
    const formatNode = options?.selectedNodeLabel ?? getNodeDisplayLabel;
    return formatNode(node);
  }

  const edge = edges.find((entry) => entry.id === selected.id);
  if (!edge) {
    return staleLabel;
  }
  const formatEdge = options?.selectedEdgeLabel ?? formatEdgeSelectionLabel;
  return formatEdge(edge, nodes);
}
