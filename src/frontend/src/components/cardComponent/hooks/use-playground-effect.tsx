import { useEffect } from "react";

const usePlaygroundEffect = (
  currentFlowId,
  playground,
  openPlayground,
  currentFlow,
  setNodes,
  setEdges,
  cleanFlowPool,
) => {
  useEffect(() => {
    if (currentFlowId && playground) {
      if (openPlayground) {
        setNodes(currentFlow?.data?.nodes ?? [], true);
        setEdges(currentFlow?.data?.edges ?? [], true);
      } else {
        setNodes([], true);
        setEdges([], true);
      }
      cleanFlowPool();
    }
  }, [openPlayground]);
};

export default usePlaygroundEffect;
