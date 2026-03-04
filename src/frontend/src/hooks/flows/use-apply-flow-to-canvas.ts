import { cloneDeep } from "lodash";
import { useCallback } from "react";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import type { FlowType } from "@/types/flow";
import { processFlows } from "@/utils/reactflowUtils";

/**
 * Returns a function that applies a flow to the canvas. This is the shared
 * pipeline used by both initial flow loading and version restore:
 *   processFlows → setCurrentFlow (→ resetFlow) → refreshAllModelInputs
 *
 * The input flow is deep-cloned before processing so callers retain their
 * original reference unmodified.
 */
const useApplyFlowToCanvas = () => {
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const { refreshAllModelInputs } = useRefreshModelInputs();

  const applyFlowToCanvas = useCallback(
    (flow: FlowType) => {
      // Clone so processFlows' in-place mutations don't corrupt the caller's data.
      const clonedFlow = cloneDeep(flow);
      const hadNodes = (clonedFlow.data?.nodes?.length ?? 0) > 0;
      processFlows([clonedFlow]);
      if (hadNodes && !clonedFlow.data?.nodes?.length) {
        throw new Error(
          "useApplyFlowToCanvas: processFlows destroyed all nodes — aborting to prevent canvas wipe",
        );
      }
      setCurrentFlow(clonedFlow);
      requestAnimationFrame(() => {
        useFlowStore.getState().reactFlowInstance?.fitView();
      });
      refreshAllModelInputs({ silent: true }).catch((err) => {
        console.error(
          "useApplyFlowToCanvas: failed to refresh model inputs",
          err,
        );
      });
    },
    [setCurrentFlow, refreshAllModelInputs],
  );

  return applyFlowToCanvas;
};

export default useApplyFlowToCanvas;
