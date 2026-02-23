import { useCallback } from "react";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";

/**
 * Returns a function that applies a flow to the canvas. This is the shared
 * pipeline used by both initial flow loading and version restore:
 *   processFlows → setCurrentFlow (→ resetFlow) → refreshAllModelInputs
 */
const useApplyFlowToCanvas = () => {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const { refreshAllModelInputs } = useRefreshModelInputs();

  const applyFlowToCanvas = useCallback(
    (flow: FlowType) => {
      processFlows([flow]);
      setCurrentFlow(flow);
      refreshAllModelInputs({ silent: true });
    },
    [setCurrentFlow, refreshAllModelInputs],
  );

  return applyFlowToCanvas;
};

export default useApplyFlowToCanvas;
