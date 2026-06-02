import { NODE_WIDTH } from "@/constants/constants";
import type { AllNodeType } from "@/types/flow";

export type CollaborationNodeSelectionRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type ReactFlowNodeInternals = {
  internals: {
    positionAbsolute?: { x: number; y: number };
  };
  measured: {
    width?: number;
    height?: number;
  };
  width?: number;
  height?: number;
};

const DEFAULT_NODE_HEIGHT = 96;

export function resolveCollaborationNodeSelectionRect(
  flowNode: AllNodeType | undefined,
  reactFlowNode: ReactFlowNodeInternals | undefined,
): CollaborationNodeSelectionRect | null {
  const absolute = reactFlowNode?.internals.positionAbsolute;
  const x = absolute?.x ?? flowNode?.position.x;
  const y = absolute?.y ?? flowNode?.position.y;

  if (x == null || y == null) {
    return null;
  }

  return {
    x,
    y,
    width:
      reactFlowNode?.measured.width ??
      reactFlowNode?.width ??
      flowNode?.width ??
      NODE_WIDTH,
    height:
      reactFlowNode?.measured.height ??
      reactFlowNode?.height ??
      flowNode?.height ??
      DEFAULT_NODE_HEIGHT,
  };
}
