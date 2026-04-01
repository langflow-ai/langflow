/**
 * Hook for real-time webhook build events via Server-Sent Events (SSE).
 * Provides live build feedback when webhooks are triggered externally.
 */

import { useEffect, useMemo, useRef } from "react";
import { BuildStatus } from "@/constants/enums";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { VertexBuildTypeAPI } from "@/types/api";
import type { VertexLayerElementType } from "@/types/zustand/flow";

const SSE_EVENTS = {
  CONNECTED: "connected",
  VERTICES_SORTED: "vertices_sorted",
  BUILD_START: "build_start",
  END_VERTEX: "end_vertex",
  END: "end",
  ERROR: "error",
  HEARTBEAT: "heartbeat",
} as const;

function handleVerticesSorted(event: MessageEvent): void {
  const data = JSON.parse(event.data);
  const verticesIds = data.ids;
  const verticesToRun = data.to_run;

  const verticesLayers: VertexLayerElementType[][] = verticesIds.map(
    (id: string) => [{ id, reference: id }],
  );

  const store = useFlowStore.getState();
  store.updateVerticesBuild({
    verticesLayers,
    verticesIds,
    verticesToRun,
    runId: data.run_id,
  });
  store.updateBuildStatus(verticesIds, BuildStatus.TO_BUILD);
  store.setIsBuilding(true);
}

function handleBuildStart(event: MessageEvent): void {
  const data = JSON.parse(event.data);
  const ids = [data.id];

  const store = useFlowStore.getState();
  store.updateBuildStatus(ids, BuildStatus.BUILDING);
  store.updateEdgesRunningByNodes(ids, true);
  store.setCurrentBuildingNodeId(ids);
}

function handleEndVertex(event: MessageEvent): void {
  const data = JSON.parse(event.data);
  const buildData: VertexBuildTypeAPI = data.build_data;
  const store = useFlowStore.getState();

  if (
    buildData.inactivated_vertices &&
    buildData.inactivated_vertices.length > 0
  ) {
    store.removeFromVerticesBuild(buildData.inactivated_vertices);
    store.updateBuildStatus(
      buildData.inactivated_vertices,
      BuildStatus.INACTIVE,
    );
  }

  store.addDataToFlowPool(
    { ...buildData, run_id: data.run_id || "" },
    buildData.id,
  );

  const buildStatus = buildData.valid ? BuildStatus.BUILT : BuildStatus.ERROR;
  store.updateBuildStatus([buildData.id], buildStatus);
  store.clearEdgesRunningByNodes();

  if (buildData.next_vertices_ids && buildData.next_vertices_ids.length > 0) {
    store.setCurrentBuildingNodeId(buildData.next_vertices_ids);
    store.updateEdgesRunningByNodes(buildData.next_vertices_ids, true);
    store.updateBuildStatus(buildData.next_vertices_ids, BuildStatus.TO_BUILD);
  }
}

function handleEnd(event: MessageEvent): void {
  const data = JSON.parse(event.data);
  const store = useFlowStore.getState();

  store.setIsBuilding(false);
  store.clearEdgesRunningByNodes();
  store.setCurrentBuildingNodeId([]);

  if (data.success) {
    store.setBuildInfo({ success: true });
  } else {
    store.setBuildInfo({
      error: [data.error || "Build failed"],
      success: false,
    });
  }
}

function handleError(eventOrError: Event): void {
  const messageEvent = eventOrError as MessageEvent;
  if (!messageEvent.data) {
    return;
  }

  try {
    JSON.parse(messageEvent.data);
    const store = useFlowStore.getState();
    store.setIsBuilding(false);
    store.clearEdgesRunningByNodes();
  } catch {
    // SSE connection error rather than a data event
  }
}

function hasWebhookComponent(
  flow: { data?: { nodes?: Array<{ id: string }> } } | null,
): boolean {
  if (!flow?.data?.nodes) {
    return false;
  }
  return flow.data.nodes.some((node) => node.id.includes("Webhook"));
}

export function useWebhookEvents() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const apiKey = useAuthStore((state) => state.apiKey);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Memoize webhook check to avoid reconnecting on every render
  const flowHasWebhook = useMemo(
    () => hasWebhookComponent(currentFlow),
    [currentFlow?.data?.nodes],
  );

  useEffect(() => {
    // Only connect if flow has a webhook component
    if (!currentFlow?.id || !flowHasWebhook) {
      return;
    }

    const flowIdentifier = currentFlow.endpoint_name || currentFlow.id;
    let sseUrl = `/api/v1/webhook-events/${flowIdentifier}`;

    if (apiKey) {
      sseUrl += `?x-api-key=${encodeURIComponent(apiKey)}`;
    }

    const eventSource = new EventSource(sseUrl, { withCredentials: true });
    eventSourceRef.current = eventSource;

    eventSource.onerror = () => {
      // SSE connection error - handled silently
    };

    eventSource.addEventListener(
      SSE_EVENTS.VERTICES_SORTED,
      handleVerticesSorted,
    );
    eventSource.addEventListener(SSE_EVENTS.BUILD_START, handleBuildStart);
    eventSource.addEventListener(SSE_EVENTS.END_VERTEX, handleEndVertex);
    eventSource.addEventListener(SSE_EVENTS.END, handleEnd);
    eventSource.addEventListener(SSE_EVENTS.ERROR, handleError);

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [currentFlow?.id, currentFlow?.endpoint_name, apiKey, flowHasWebhook]);
}
