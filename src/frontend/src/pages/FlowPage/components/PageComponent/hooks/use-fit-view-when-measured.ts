import {
  type FitViewOptions,
  useNodesInitialized,
  useReactFlow,
  useStore,
} from "@xyflow/react";
import { useEffect, useRef } from "react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

/**
 * Performs a requested canvas fit once the whole graph has been measured.
 *
 * ReactFlow resolves a queued `fitView` on the first `updateNodeInternals`
 * batch, and `getFitViewNodes` drops any node without `measured.width/height`
 * from the bounding box — position included. Langflow's nodes are heavy enough
 * to measure across several ResizeObserver batches, so a fit issued when a flow
 * is applied runs over whichever subset landed first and is never recomputed:
 * flows open zoomed in on a few nodes, with the rest outside the viewport.
 *
 * `useNodesInitialized` flips to `true` only once every non-hidden node has
 * dimensions, which is exactly the point where a fit sees the whole graph.
 *
 * Only an explicit `requestFitView` fits. Nodes appearing on their own is not a
 * request: a user dropping the first component onto an empty canvas measures a
 * graph too, and re-framing the viewport under their cursor would move the
 * canvas mid-edit.
 */
export function useFitViewWhenMeasured(fitViewOptions?: FitViewOptions) {
  const fitViewRequest = useFlowStore((state) => state.fitViewRequest);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const nodesInitialized = useNodesInitialized();
  const canvasWidth = useStore((state) => state.width);
  const canvasHeight = useStore((state) => state.height);
  const { fitView, getViewport } = useReactFlow();

  // Options are rebuilt on every render at the call site; reading them through
  // a ref keeps them out of the effect's deps so a re-render can't re-fit and
  // undo a viewport the user has since panned.
  const fitViewOptionsRef = useRef(fitViewOptions);
  fitViewOptionsRef.current = fitViewOptions;

  // What the last fit was performed for, and what it produced. Requests that
  // arrive while the nodes are still being measured collapse into a single fit.
  const lastFit = useRef<{
    requestId: number;
    flowId: string;
    width: number;
    height: number;
    viewport: { x: number; y: number; zoom: number };
    corrected: boolean;
  } | null>(null);

  useEffect(() => {
    // No flow on the canvas yet: nothing to frame, and fitting now would burn
    // the request that the flow itself is about to make.
    if (!currentFlowId) return;
    if (!nodesInitialized) return;
    // Request 0 is the store's initial value — no one has asked for a fit.
    if (fitViewRequest.id === 0) return;

    const previous = lastFit.current;
    const isNewRequest =
      previous?.requestId !== fitViewRequest.id ||
      previous?.flowId !== currentFlowId;

    // Opening a flow can change the canvas size after the fit: the welcome
    // overlay hides the sidebar while it is up, so the canvas is wider for the
    // fit and narrows the moment the overlay closes, leaving the graph framed
    // for a viewport it no longer has. Correcting that is safe only while the
    // viewport is still exactly where the fit put it — once the user has panned
    // or zoomed, the framing is theirs and a later resize must not move it.
    const resizedBeforeUserMovedViewport =
      !isNewRequest &&
      previous !== null &&
      !previous.corrected &&
      (previous.width !== canvasWidth || previous.height !== canvasHeight) &&
      isSameViewport(getViewport(), previous.viewport);

    if (!isNewRequest && !resizedBeforeUserMovedViewport) return;

    fitView(fitViewOptionsRef.current);

    lastFit.current = {
      requestId: fitViewRequest.id,
      flowId: currentFlowId,
      width: canvasWidth,
      height: canvasHeight,
      viewport: getViewport(),
      // One correction per request: a canvas that keeps resizing is no longer
      // the flow opening.
      corrected: !isNewRequest,
    };

    const { onFitted } = fitViewRequest;
    if (onFitted) {
      // Cleared before running so a callback that requests another fit cannot
      // see itself as still pending.
      useFlowStore.setState({ fitViewRequest: { id: fitViewRequest.id } });
      onFitted();
    }
  }, [
    currentFlowId,
    nodesInitialized,
    fitViewRequest,
    canvasWidth,
    canvasHeight,
    fitView,
    getViewport,
  ]);
}

/** ReactFlow reports the viewport as floats; compare within a pixel. */
function isSameViewport(
  a: { x: number; y: number; zoom: number },
  b: { x: number; y: number; zoom: number },
): boolean {
  return (
    Math.abs(a.x - b.x) < 1 &&
    Math.abs(a.y - b.y) < 1 &&
    Math.abs(a.zoom - b.zoom) < 0.001
  );
}
