/**
 * Hook for real-time webhook build events via Server-Sent Events (SSE).
 *
 * This hook uses the SAME logic as the normal Play button flow by calling
 * the same store functions (handleBuildUpdate pattern from flowStore).
 */

import { useEffect, useRef } from "react";
import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { VertexBuildTypeAPI } from "@/types/api";
import type { VertexLayerElementType } from "@/types/zustand/flow";

export function useWebhookEvents() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!currentFlow?.id) {
      return;
    }

    // Connect to SSE endpoint for this flow
    const flowIdentifier = currentFlow.endpoint_name || currentFlow.id;
    const sseUrl = `/api/v1/webhook-events/${flowIdentifier}`;

    console.log("[useWebhookEvents] Connecting to SSE:", sseUrl);

    const eventSource = new EventSource(sseUrl);
    eventSourceRef.current = eventSource;

    // ============================================================
    // EVENT: connected
    // ============================================================
    eventSource.addEventListener("connected", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] Connected to flow:", data);
    });

    // ============================================================
    // EVENT: vertices_sorted (same as buildUtils onEvent)
    // ============================================================
    eventSource.addEventListener("vertices_sorted", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] vertices_sorted:", data);

      const verticesIds = data.ids;
      const verticesToRun = data.to_run;

      // Build the verticesLayers structure (same as buildUtils)
      const verticesLayers: VertexLayerElementType[][] = verticesIds.map(
        (id: string) => [{ id, reference: id }]
      );

      // Update store with vertices build info
      useFlowStore.getState().updateVerticesBuild({
        verticesLayers,
        verticesIds,
        verticesToRun,
        runId: data.run_id,
      });

      // Mark all as TO_BUILD
      useFlowStore.getState().updateBuildStatus(verticesIds, BuildStatus.TO_BUILD);

      // Set building state
      useFlowStore.getState().setIsBuilding(true);
    });

    // ============================================================
    // EVENT: build_start (same as onBuildStart in flowStore)
    // ============================================================
    eventSource.addEventListener("build_start", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] build_start:", data);

      const ids = [data.id];

      // Mark as BUILDING (same as onBuildStart callback)
      useFlowStore.getState().updateBuildStatus(ids, BuildStatus.BUILDING);

      // Update edges animation
      useFlowStore.getState().updateEdgesRunningByNodes(ids, true);
      useFlowStore.getState().setCurrentBuildingNodeId(ids);
    });

    // ============================================================
    // EVENT: end_vertex (same as buildUtils onEvent case "end_vertex")
    // ============================================================
    eventSource.addEventListener("end_vertex", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] end_vertex:", data);

      const buildData: VertexBuildTypeAPI = data.build_data;
      // Duration is calculated and formatted by the backend (event_manager.py)

      // Handle inactivated vertices (same as handleBuildUpdate in flowStore)
      if (buildData.inactivated_vertices && buildData.inactivated_vertices.length > 0) {
        useFlowStore.getState().removeFromVerticesBuild(buildData.inactivated_vertices);
        useFlowStore.getState().updateBuildStatus(
          buildData.inactivated_vertices,
          BuildStatus.INACTIVE
        );
      }

      // Add data to flow pool (THIS IS THE KEY - same as handleBuildUpdate)
      useFlowStore.getState().addDataToFlowPool(
        { ...buildData, run_id: data.run_id || "" },
        buildData.id
      );

      // Update build status based on validity
      if (buildData.valid) {
        useFlowStore.getState().updateBuildStatus([buildData.id], BuildStatus.BUILT);
      } else {
        useFlowStore.getState().updateBuildStatus([buildData.id], BuildStatus.ERROR);
      }

      // Clear edge animations
      useFlowStore.getState().clearEdgesRunningByNodes();

      // Handle next vertices (same as buildUtils)
      if (buildData.next_vertices_ids && buildData.next_vertices_ids.length > 0) {
        useFlowStore.getState().setCurrentBuildingNodeId(buildData.next_vertices_ids);
        useFlowStore.getState().updateEdgesRunningByNodes(buildData.next_vertices_ids, true);
        useFlowStore.getState().updateBuildStatus(buildData.next_vertices_ids, BuildStatus.TO_BUILD);
      }
    });

    // ============================================================
    // EVENT: end (build completed)
    // ============================================================
    eventSource.addEventListener("end", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] Build completed:", data);

      // Finalize build (same as onBuildComplete)
      useFlowStore.getState().setIsBuilding(false);
      useFlowStore.getState().clearEdgesRunningByNodes();
      useFlowStore.getState().setCurrentBuildingNodeId([]);

      // Set build info for success/error popup
      if (data.success) {
        useFlowStore.getState().setBuildInfo({ success: true });
      } else {
        useFlowStore.getState().setBuildInfo({
          error: [data.error || "Build failed"],
          success: false
        });
      }

    });

    // ============================================================
    // EVENT: error
    // ============================================================
    eventSource.addEventListener("error", (eventOrError: any) => {
      if (eventOrError.data) {
        try {
          const data = JSON.parse(eventOrError.data);
          console.error("[useWebhookEvents] Build error:", data);
          useFlowStore.getState().setIsBuilding(false);
          useFlowStore.getState().clearEdgesRunningByNodes();
        } catch {
          console.error("[useWebhookEvents] SSE connection error");
        }
      }
    });

    // ============================================================
    // EVENT: heartbeat
    // ============================================================
    eventSource.addEventListener("heartbeat", () => {
      // Keep-alive ping
    });

    // Cleanup
    return () => {
      console.log("[useWebhookEvents] Disconnecting from SSE...");
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [currentFlow?.id, currentFlow?.endpoint_name]);

  return null;
}
