import { useCallback, useEffect, useRef, useState } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { getLayoutedNodes } from "@/utils/layoutUtils";

export default function useAutoArrange() {
  const nodesCount = useFlowStore((state) => state.nodes.length);
  const [isArranging, setIsArranging] = useState(false);

  const isArrangingRef = useRef(false);
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const canArrange = nodesCount > 1;

  const handleAutoArrange = useCallback(async () => {
    if (isArrangingRef.current) return;
    const { nodes, edges, currentFlow } = useFlowStore.getState();
    if (nodes.length < 2) return;
    const flowId = currentFlow?.id;

    isArrangingRef.current = true;
    setIsArranging(true);
    try {
      const layoutedNodes = await getLayoutedNodes(nodes, edges);
      if (!isMountedRef.current) return;
      if (useFlowStore.getState().currentFlow?.id !== flowId) return;

      // Merge by id into the current nodes instead of replacing them
      // wholesale, so a node added/edited while layout was computing
      // isn't reverted to its pre-layout snapshot.
      const positionById = new Map(
        layoutedNodes.map((node) => [node.id, node.position]),
      );
      const { nodes: currentNodes, setNodes } = useFlowStore.getState();
      const mergedNodes = currentNodes.map((node) =>
        positionById.has(node.id)
          ? { ...node, position: positionById.get(node.id)! }
          : node,
      );

      useFlowsManagerStore.getState().takeSnapshot();
      setNodes(mergedNodes);
    } catch (error) {
      console.error("Failed to auto-arrange nodes", error);
    } finally {
      isArrangingRef.current = false;
      if (isMountedRef.current) setIsArranging(false);
    }
  }, []);

  return {
    isArranging,
    canArrange,
    handleAutoArrange,
  };
}
