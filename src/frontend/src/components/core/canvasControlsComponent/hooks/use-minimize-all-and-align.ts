import { useReactFlow, useUpdateNodeInternals } from "@xyflow/react";
import { useCallback, useMemo } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType } from "@/types/flow";
import { getLayoutedNodes } from "@/utils/layoutUtils";

// Collapsed card box (w-48 + header block) used by elk when aligning
// minimized components (LE-1810 "Minimize all & align").
export const MINIMIZED_NODE_WIDTH = 192;
export const MINIMIZED_NODE_HEIGHT = 80;

export default function useMinimizeAllAndAlign() {
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNodes = useFlowStore((state) => state.setNodes);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const updateNodeInternals = useUpdateNodeInternals();
  const { fitView } = useReactFlow();

  const genericNodeIds = useMemo(
    () =>
      nodes
        .filter((node) => node.type === "genericNode")
        .map((node) => node.id),
    [nodes],
  );

  const allMinimized = useMemo(
    () =>
      genericNodeIds.length > 0 &&
      nodes
        .filter((node) => node.type === "genericNode")
        .every((node) => node.data?.showNode === false),
    [nodes, genericNodeIds],
  );

  const minimizeAllAndAlign = useCallback(async () => {
    takeSnapshot();
    const collapsed = nodes.map((node) =>
      node.type === "genericNode"
        ? ({
            ...node,
            data: { ...node.data, showNode: false },
          } as AllNodeType)
        : node,
    );
    const layouted = await getLayoutedNodes(collapsed, edges, {
      width: MINIMIZED_NODE_WIDTH,
      height: MINIMIZED_NODE_HEIGHT,
    });
    setNodes(layouted);
    updateNodeInternals(genericNodeIds);
    requestAnimationFrame(() => {
      fitView({ padding: 0.2 });
    });
  }, [
    nodes,
    edges,
    genericNodeIds,
    setNodes,
    takeSnapshot,
    updateNodeInternals,
    fitView,
  ]);

  const expandAll = useCallback(() => {
    takeSnapshot();
    setNodes((oldNodes) =>
      oldNodes.map((node) =>
        node.type === "genericNode"
          ? ({
              ...node,
              data: { ...node.data, showNode: true },
            } as AllNodeType)
          : node,
      ),
    );
    updateNodeInternals(genericNodeIds);
  }, [genericNodeIds, setNodes, takeSnapshot, updateNodeInternals]);

  const toggleMinimizeAllAndAlign = useCallback(() => {
    if (allMinimized) {
      expandAll();
      return;
    }
    void minimizeAllAndAlign();
  }, [allMinimized, expandAll, minimizeAllAndAlign]);

  return {
    allMinimized,
    hasGenericNodes: genericNodeIds.length > 0,
    toggleMinimizeAllAndAlign,
  };
}
