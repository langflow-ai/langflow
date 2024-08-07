import { useEffect } from "react";
import { FlowType } from "../../../types/flow";

const usePlaygroundEffect = (
  currentFlowId: string,
  playground: boolean,
  openPlayground: boolean,
  currentFlow: FlowType | undefined,
  setNodes: (value: any) => void,
  setEdges: (value: any) => void,
  cleanFlowPool: () => void,
) => {
  useEffect(() => {
    if (currentFlowId && playground) {
      if (openPlayground) {
        setNodes(currentFlow?.data?.nodes ?? []);
        setEdges(currentFlow?.data?.edges ?? []);
      } else {
        setNodes([]);
        setEdges([]);
      }
      cleanFlowPool();
    }
  }, [openPlayground]);
};

export default usePlaygroundEffect;
