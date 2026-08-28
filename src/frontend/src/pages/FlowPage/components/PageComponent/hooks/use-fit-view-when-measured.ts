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
 * Re-runs the canvas fit once every node has been measured.
 *
 * ReactFlow resolves a queued `fitView` on the first `updateNodeInternals`
 * batch, and `getFitViewNodes` drops any node without `measured.width/height`
 * from the bounding box — position included. Langflow's nodes are heavy enough
 * to measure across several ResizeObserver batches, so the initial fit is
 * computed over whichever subset landed first and is never recomputed: flows
 * open zoomed in on a few nodes, with the rest outside the viewport.
 *
 * `useNodesInitialized` flips to `true` only once every non-hidden node has
 * dimensions, which is exactly the point where a fit sees the whole graph.
 *
 * The fit is request-driven rather than mount-driven so that every way of
 * putting a graph on the canvas gets the same treatment. Switching flows counts
 * as a request on its own: navigating within the app reuses this canvas, and
 * `useLoadFlowForRoute` deliberately skips loading a flow the store already
 * holds — so opening a template right after creating it would otherwise be left
 * with ReactFlow's own one-shot mount fit. An explicit `requestFitView` covers
 * the cases that reuse the flow id, such as restoring a version.
 */
/**
 * How long after a fit a canvas resize is still treated as part of opening the
 * flow. The welcome overlay hides the sidebar while it is up, so the canvas
 * widens for the fit and narrows again the moment the overlay closes — the
 * graph would be framed for a viewport it no longer has. Later resizes are the
 * user's own and must not move a viewport they have since arranged.
 */
const RESIZE_CORRECTION_WINDOW_MS = 2000;
export function useFitViewWhenMeasured(fitViewOptions?: FitViewOptions) {
  const fitViewRequest = useFlowStore((state) => state.fitViewRequest);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const nodesInitialized = useNodesInitialized();
  const canvasWidth = useStore((state) => state.width);
  const canvasHeight = useStore((state) => state.height);
  const { fitView } = useReactFlow();

  // Options are rebuilt on every render at the call site; reading them through
  // a ref keeps them out of the effect's deps so a re-render can't re-fit and
  // undo a viewport the user has since panned.
  const fitViewOptionsRef = useRef(fitViewOptions);
  fitViewOptionsRef.current = fitViewOptions;

  // Identifies the graph the last fit was performed for. Requests that arrive
  // while the nodes are still being measured collapse into a single fit.
  const fitKey = `${currentFlowId}:${fitViewRequest.id}`;
  const lastFit = useRef<{
    key: string;
    width: number;
    height: number;
    at: number;
  } | null>(null);

  useEffect(() => {
    // No flow on the canvas yet: nothing to frame, and fitting now would burn
    // the request that the flow itself is about to make.
    if (!currentFlowId) return;
    if (!nodesInitialized) return;

    const previous = lastFit.current;
    const isNewRequest = previous?.key !== fitKey;
    const resizedWhileOpening =
      !isNewRequest &&
      previous !== null &&
      (previous.width !== canvasWidth || previous.height !== canvasHeight) &&
      Date.now() - previous.at < RESIZE_CORRECTION_WINDOW_MS;

    if (!isNewRequest && !resizedWhileOpening) return;

    lastFit.current = {
      key: fitKey,
      width: canvasWidth,
      height: canvasHeight,
      // Corrections keep the original request's timestamp so a canvas that
      // keeps resizing cannot extend the window indefinitely.
      at: isNewRequest ? Date.now() : previous.at,
    };
    fitView(fitViewOptionsRef.current);

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
    fitKey,
    canvasWidth,
    canvasHeight,
    fitView,
    fitViewRequest,
  ]);
}
