import { useEffect } from "react";
import type { FlowType } from "@/types/flow";

type GetFlow = (payload: { id: string }) => Promise<FlowType>;

type UseLoadFlowForRouteProps = {
  id?: string;
  flows?: FlowType[];
  currentFlowId: string;
  types: Record<string, string>;
  getFlow: GetFlow;
  applyFlowToCanvas: (flow: FlowType) => void;
  navigate: (path: string) => void;
};

export default function useLoadFlowForRoute({
  id,
  flows,
  currentFlowId,
  types,
  getFlow,
  applyFlowToCanvas,
  navigate,
}: UseLoadFlowForRouteProps): void {
  useEffect(() => {
    if (!flows || currentFlowId !== "" || Object.keys(types).length === 0) {
      return;
    }

    if (!id) {
      navigate("/all");
      return;
    }

    let cancelled = false;
    const storedFlow = flows.find((flow) => flow.id === id);

    const loadFlowToCanvas = async (flowId: string) => {
      const flow = await getFlow({ id: flowId });
      if (!cancelled) {
        applyFlowToCanvas(flow);
      }
    };

    if (storedFlow) {
      void loadFlowToCanvas(storedFlow.id);
    } else {
      // The flows store is not authoritative here: right after
      // create-then-navigate (the "New Flow" button), an in-flight list
      // refetch snapshotted BEFORE the create can land now and rewrite the
      // store without the new flow. Confirm with the server before giving up
      // on the route.
      void loadFlowToCanvas(id).catch((error) => {
        if (cancelled) {
          return;
        }
        console.error(`Failed to confirm flow ${id} from the server:`, error);
        navigate("/all");
      });
    }

    return () => {
      cancelled = true;
    };
  }, [id, flows, currentFlowId, types, getFlow, applyFlowToCanvas, navigate]);
}
