import { getBezierPath, Position, useStore } from "@xyflow/react";
import { useCallback } from "react";
import { resolveCollaborationNodeSelectionRect } from "@/hooks/flows/collaboration-node-selection-geometry";
import type { CollaborationSelectionMarker } from "@/hooks/flows/collaboration-selection-markers";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType, EdgeType } from "@/types/flow";

type ReactFlowNodeLookup = {
  get: (
    nodeId: string,
  ) => Parameters<typeof resolveCollaborationNodeSelectionRect>[1];
};

export function resolveCollaborationEdgeSelectionTransforms({
  edgeMarkers,
  edges,
  flowNodes,
  nodeLookup,
}: {
  edgeMarkers: CollaborationSelectionMarker[];
  edges: EdgeType[];
  flowNodes: AllNodeType[];
  nodeLookup: ReactFlowNodeLookup;
}): Map<string, string> {
  const transforms = new Map<string, string>();
  if (edgeMarkers.length === 0) {
    return transforms;
  }

  for (const marker of edgeMarkers) {
    const edge = edges.find((entry) => entry.id === marker.targetId);
    if (!edge) {
      continue;
    }

    const sourceFlowNode = flowNodes.find((entry) => entry.id === edge.source);
    const targetFlowNode = flowNodes.find((entry) => entry.id === edge.target);
    const sourceNode = nodeLookup.get(edge.source);
    const targetNode = nodeLookup.get(edge.target);

    const sourceRect = resolveCollaborationNodeSelectionRect(
      sourceFlowNode,
      sourceNode,
    );
    const targetRect = resolveCollaborationNodeSelectionRect(
      targetFlowNode,
      targetNode,
    );

    if (!sourceRect || !targetRect) {
      continue;
    }

    const sourceX = sourceRect.x + sourceRect.width;
    const sourceY = sourceRect.y + sourceRect.height / 2;
    const targetX = targetRect.x;
    const targetY = targetRect.y + targetRect.height / 2;

    const [, labelX, labelY] = getBezierPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    });

    transforms.set(
      marker.targetId,
      `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
    );
  }

  return transforms;
}

export function useCollaborationEdgeSelectionTransforms(
  edgeMarkers: CollaborationSelectionMarker[],
  edges: EdgeType[],
): Map<string, string> {
  const edgeIdsKey = edgeMarkers.map((marker) => marker.targetId).join("|");
  const flowNodes = useFlowStore((state) => state.nodes);

  return useStore(
    useCallback(
      (storeState) => {
        return resolveCollaborationEdgeSelectionTransforms({
          edgeMarkers,
          edges,
          flowNodes,
          nodeLookup: storeState.nodeLookup,
        });
      },
      [edgeIdsKey, edgeMarkers, edges, flowNodes],
    ),
  );
}
