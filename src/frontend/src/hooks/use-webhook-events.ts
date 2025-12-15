/**
 * Hook for real-time webhook build events via Server-Sent Events (SSE).
 * Uses the same logic as the Play button flow by calling the same store functions.
 */

import { useEffect, useRef } from "react";
import { BuildStatus } from "@/constants/enums";
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

export function useWebhookEvents() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!currentFlow?.id) {
      return;
    }

    const flowIdentifier = currentFlow.endpoint_name || currentFlow.id;
    const sseUrl = `/api/v1/webhook-events/${flowIdentifier}`;
    const eventSource = new EventSource(sseUrl);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener(SSE_EVENTS.CONNECTED, () => {
      // Connection established
    });

    eventSource.addEventListener(SSE_EVENTS.VERTICES_SORTED, (event) => {
      const data = JSON.parse(event.data);
      const verticesIds = data.ids;
      const verticesToRun = data.to_run;

      const verticesLayers: VertexLayerElementType[][] = verticesIds.map(
        (id: string) => [{ id, reference: id }]
      );

      useFlowStore.getState().updateVerticesBuild({
        verticesLayers,
        verticesIds,
        verticesToRun,
        runId: data.run_id,
      });

      useFlowStore.getState().updateBuildStatus(verticesIds, BuildStatus.TO_BUILD);
      useFlowStore.getState().setIsBuilding(true);
    });

    eventSource.addEventListener(SSE_EVENTS.BUILD_START, (event) => {
      const data = JSON.parse(event.data);
      const ids = [data.id];

      useFlowStore.getState().updateBuildStatus(ids, BuildStatus.BUILDING);
      useFlowStore.getState().updateEdgesRunningByNodes(ids, true);
      useFlowStore.getState().setCurrentBuildingNodeId(ids);
    });

    eventSource.addEventListener(SSE_EVENTS.END_VERTEX, (event) => {
      const data = JSON.parse(event.data);
      const buildData: VertexBuildTypeAPI = data.build_data;

      if (buildData.inactivated_vertices && buildData.inactivated_vertices.length > 0) {
        useFlowStore.getState().removeFromVerticesBuild(buildData.inactivated_vertices);
        useFlowStore.getState().updateBuildStatus(
          buildData.inactivated_vertices,
          BuildStatus.INACTIVE
        );
      }

      useFlowStore.getState().addDataToFlowPool(
        { ...buildData, run_id: data.run_id || "" },
        buildData.id
      );

      if (buildData.valid) {
        useFlowStore.getState().updateBuildStatus([buildData.id], BuildStatus.BUILT);
      } else {
        useFlowStore.getState().updateBuildStatus([buildData.id], BuildStatus.ERROR);
      }

      useFlowStore.getState().clearEdgesRunningByNodes();

      if (buildData.next_vertices_ids && buildData.next_vertices_ids.length > 0) {
        useFlowStore.getState().setCurrentBuildingNodeId(buildData.next_vertices_ids);
        useFlowStore.getState().updateEdgesRunningByNodes(buildData.next_vertices_ids, true);
        useFlowStore.getState().updateBuildStatus(buildData.next_vertices_ids, BuildStatus.TO_BUILD);
      }
    });

    eventSource.addEventListener(SSE_EVENTS.END, (event) => {
      const data = JSON.parse(event.data);

      useFlowStore.getState().setIsBuilding(false);
      useFlowStore.getState().clearEdgesRunningByNodes();
      useFlowStore.getState().setCurrentBuildingNodeId([]);

      if (data.success) {
        useFlowStore.getState().setBuildInfo({ success: true });
      } else {
        useFlowStore.getState().setBuildInfo({
          error: [data.error || "Build failed"],
          success: false
        });
      }
    });

    eventSource.addEventListener(SSE_EVENTS.ERROR, (eventOrError: Event) => {
      const messageEvent = eventOrError as MessageEvent;
      if (messageEvent.data) {
        try {
          JSON.parse(messageEvent.data);
          useFlowStore.getState().setIsBuilding(false);
          useFlowStore.getState().clearEdgesRunningByNodes();
        } catch {
          // SSE connection error, not a data event
        }
      }
    });

    eventSource.addEventListener(SSE_EVENTS.HEARTBEAT, () => {
      // Keep-alive ping
    });

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [currentFlow?.id, currentFlow?.endpoint_name]);
}
