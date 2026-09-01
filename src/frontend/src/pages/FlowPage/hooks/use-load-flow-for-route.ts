import { useEffect, useRef } from "react";
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
  const activeRequestRef = useRef<{ id: string } | null>(null);
  const mountedRef = useRef(true);

  // Cancellation has to outlive the effect: React re-runs the cleanup on every
  // dependency change, so a per-run flag would discard the in-flight response
  // the guard below refuses to re-request, leaving the canvas empty forever.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!flows || currentFlowId !== "" || Object.keys(types).length === 0) {
      return;
    }

    if (!id) {
      navigate("/all");
      return;
    }

    // `currentFlowId` only leaves "" once a response lands, so every render
    // until then re-enters this effect. Without an in-flight guard each of
    // those renders fires another request, and the pending mutation state
    // renders again — a loop that saturates the browser socket pool and
    // prevents the very response that would end it.
    if (activeRequestRef.current?.id === id) {
      return;
    }
    const request = { id };
    activeRequestRef.current = request;

    const storedFlow = flows.find((flow) => flow.id === id);
    const isStale = () =>
      !mountedRef.current || activeRequestRef.current !== request;

    const loadFlowToCanvas = async (flowId: string) => {
      const flow = await getFlow({ id: flowId });
      if (!isStale()) {
        applyFlowToCanvas(flow);
      }
    };

    const releaseForRetry = () => {
      if (activeRequestRef.current === request) {
        activeRequestRef.current = null;
      }
    };

    if (storedFlow) {
      void loadFlowToCanvas(storedFlow.id).catch((error) => {
        const stale = isStale();
        releaseForRetry();
        if (!stale) {
          console.error(`Failed to load flow ${id} into the canvas:`, error);
        }
      });
    } else {
      // The flows store is not authoritative here: right after
      // create-then-navigate (the "New Flow" button), an in-flight list
      // refetch snapshotted BEFORE the create can land now and rewrite the
      // store without the new flow. Confirm with the server before giving up
      // on the route.
      void loadFlowToCanvas(id).catch((error) => {
        const stale = isStale();
        releaseForRetry();
        if (stale) {
          return;
        }
        console.error(`Failed to confirm flow ${id} from the server:`, error);
        navigate("/all");
      });
    }
  }, [id, flows, currentFlowId, types, getFlow, applyFlowToCanvas, navigate]);
}
