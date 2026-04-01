import { ReactFlowState } from "@xyflow/react";
import { getOS } from "@/utils/utils";

export const getModifierKey = (): string => {
  const os = getOS();
  return os === "macos" ? "⌘" : "Ctrl";
};

export const formatZoomPercentage = (zoom: number): string =>
  `${Math.round(zoom * 100)}%`;

export const reactFlowSelector = (s: ReactFlowState) => ({
  isInteractive: s.nodesDraggable || s.nodesConnectable || s.elementsSelectable,
  minZoomReached: s.transform[2] <= s.minZoom,
  maxZoomReached: s.transform[2] >= s.maxZoom,
  zoom: s.transform[2],
});
