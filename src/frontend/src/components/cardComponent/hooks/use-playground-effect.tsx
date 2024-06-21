import { useEffect } from "react";
import { FlowType } from "../../../types/flow";

const usePlaygroundEffect = (
  currentFlowId: string,
  playground: boolean,
  openPlayground: boolean,
  currentFlow: FlowType | undefined,
  setNodes: (value: any, value2: boolean) => void,
  setEdges: (value: any, value2: boolean) => void,
  cleanFlowPool: () => void,
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
