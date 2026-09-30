import { useUpdateNodeInternals } from "@xyflow/react";
import { useCallback, useMemo } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType } from "@/types/flow";

export default function useMinimizeAllAndAlign() {
  const nodes = useFlowStore((state) => state.nodes);
  const setNodes = useFlowStore((state) => state.setNodes);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const updateNodeInternals = useUpdateNodeInternals();

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

  // LE-1810 review round (reporter): minimize-all ONLY toggles showNode —
  // no re-layout, no viewport change. Components keep their positions.
  const setAllShowNode = useCallback(
    (showNode: boolean) => {
      takeSnapshot();
      setNodes(
        nodes.map((node) =>
          node.type === "genericNode"
            ? ({
                ...node,
                data: { ...node.data, showNode },
              } as AllNodeType)
            : node,
        ),
      );
      updateNodeInternals(genericNodeIds);
    },
    [nodes, genericNodeIds, setNodes, takeSnapshot, updateNodeInternals],
  );

  const toggleMinimizeAllAndAlign = useCallback(() => {
    setAllShowNode(allMinimized);
  }, [allMinimized, setAllShowNode]);

  return {
    allMinimized,
    hasGenericNodes: genericNodeIds.length > 0,
    toggleMinimizeAllAndAlign,
  };
}
