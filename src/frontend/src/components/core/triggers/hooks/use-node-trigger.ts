import {
  type TriggerRead,
  useTriggersQuery,
} from "@/controllers/API/queries/triggers";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

/**
 * The trigger row a canvas node was reconciled into, found by flow and node
 * id. Every trigger node on the canvas reads the same per-flow query, so one
 * poll serves them all. `undefined` until the flow has been saved.
 */
export function useNodeTrigger(
  nodeId: string,
  enabled = true,
): { trigger: TriggerRead | undefined; isLoading: boolean } {
  const flowId = useFlowsManagerStore((state) => state.currentFlowId);
  const query = useTriggersQuery(
    { flowId },
    { enabled: enabled && Boolean(flowId) },
  );
  return {
    trigger: query.data?.find((row) => row.node_id === nodeId),
    isLoading: query.isLoading,
  };
}
