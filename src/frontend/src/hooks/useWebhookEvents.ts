/**
 * Hook for real-time webhook build events via Server-Sent Events (SSE).
 *
 * When a flow is open in the UI, this hook automatically connects to the backend
 * SSE endpoint and receives live build events triggered by webhook calls.
 *
 * This provides the same visual experience as clicking "Play" in the UI,
 * but triggered by external webhook requests.
 */

import { useEffect, useRef } from "react";
import { BuildStatus } from "@/constants/enums";
import { baseURL } from "@/customization/constants";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { VertexBuildTypeAPI } from "@/types/api";

export function useWebhookEvents() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const eventSourceRef = useRef<EventSource | null>(null);
  const updateBuildStatus = useFlowStore((state) => state.updateBuildStatus);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const updateVerticesBuild = useFlowStore((state) => state.updateVerticesBuild);
  const addDataToFlowPool = useFlowStore((state) => state.addDataToFlowPool);
  const updateEdgesRunningByNodes = useFlowStore(
    (state) => state.updateEdgesRunningByNodes,
  );
  const clearEdgesRunningByNodes = useFlowStore(
    (state) => state.clearEdgesRunningByNodes,
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setBuildInfo = useFlowStore((state) => state.setBuildInfo);
  const setFlowPool = useFlowStore((state) => state.setFlowPool);

  useEffect(() => {
    if (!currentFlow?.id) {
      return;
    }

    // Connect to SSE endpoint for this flow
    const flowIdentifier = currentFlow.endpoint_name || currentFlow.id;
    const sseUrl = `${baseURL}/api/v1/webhook-events/${flowIdentifier}`;

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
    // EVENT: vertices_sorted
    // ============================================================
    eventSource.addEventListener("vertices_sorted", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] vertices_sorted:", data);

      const verticesIds = data.ids;
      const verticesToRun = data.to_run;

      // Mark all components as TO_BUILD
      console.log("[useWebhookEvents] Calling updateBuildStatus with IDs:", verticesIds, "status:", BuildStatus.TO_BUILD);
      updateBuildStatus(verticesIds, BuildStatus.TO_BUILD);
      console.log("[useWebhookEvents] updateBuildStatus called");

      // Save execution structure
      const verticesLayers = verticesIds.map((id: string) => [
        { id, reference: id },
      ]);

      updateVerticesBuild({
        verticesLayers,
        verticesIds,
        verticesToRun,
        runId: data.run_id,
      });

      // Set global building flag
      setIsBuilding(true);
    });

    // ============================================================
    // EVENT: build_start
    // ============================================================
    eventSource.addEventListener("build_start", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] build_start:", data);

      // Mark component as BUILDING
      // This triggers the spinner animation and purple border
      updateBuildStatus([data.id], BuildStatus.BUILDING);

      // Animate edges leading to this component
      updateEdgesRunningByNodes([data.id], true);
    });

    // ============================================================
    // EVENT: end_vertex
    // ============================================================
    eventSource.addEventListener("end_vertex", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] end_vertex:", data);

      const buildData: VertexBuildTypeAPI = data.build_data;

      if (buildData.valid) {
        // ✅ Success!
        console.log("[useWebhookEvents] Calling updateBuildStatus for BUILT:", [buildData.id]);
        updateBuildStatus([buildData.id], BuildStatus.BUILT);
        console.log("[useWebhookEvents] updateBuildStatus called for BUILT");

        // Add to flow pool (results cache)
        addDataToFlowPool(buildData, buildData.id);

        // Animate edges to next components
        if (buildData.next_vertices_ids) {
          updateEdgesRunningByNodes(buildData.next_vertices_ids, true);
        }
      } else {
        // ❌ Error!
        console.log("[useWebhookEvents] Calling updateBuildStatus for ERROR:", [buildData.id]);
        updateBuildStatus([buildData.id], BuildStatus.ERROR);
        console.log("[useWebhookEvents] updateBuildStatus called for ERROR");

        // Extract error messages
        const errorMessages = Object.keys(buildData.data?.outputs || {}).flatMap(
          (key) => {
            const outputs = buildData.data.outputs[key];
            if (Array.isArray(outputs)) {
              return outputs
                .filter((log: any) => log.message?.type === "error")
                .map((log: any) => log.message?.errorMessage || "Unknown error");
            }
            return [];
          },
        );

        // Show error modal
        if (errorMessages.length > 0) {
          setErrorData({
            title: "Webhook Build Error",
            list: errorMessages,
          });
        }
      }

      // Clear animations from previous component
      clearEdgesRunningByNodes();
    });

    // ============================================================
    // EVENT: build_end
    // ============================================================
    eventSource.addEventListener("build_end", (event) => {
      const data = JSON.parse(event.data);
      console.log("[useWebhookEvents] build_end:", data);

      // Mark component as BUILT
      updateBuildStatus([data.id], BuildStatus.BUILT);
    });

    // ============================================================
    // EVENT: end
    // ============================================================
    eventSource.addEventListener("end", async (event) => {
      console.log("[useWebhookEvents] Build completed");

      const data = JSON.parse(event.data);

      // Finalize build
      setIsBuilding(false);
      clearEdgesRunningByNodes();

      // Set build info to show success/error popup
      if (data.success) {
        console.log("[useWebhookEvents] All components built successfully");
        setBuildInfo({ success: true });

        // Use vertex_builds from event if available (includes duration and full outputs)
        if (data.vertex_builds) {
          console.log("[useWebhookEvents] Setting flow pool with build data from event:", Object.keys(data.vertex_builds).length, "vertices");
          setFlowPool(data.vertex_builds);
        } else {
          // Fallback: fetch complete builds from backend if not in event
          if (currentFlow?.id) {
            try {
              console.log("[useWebhookEvents] Fetching complete builds for flow:", currentFlow.id);
              const response = await api.get(`${getURL("BUILDS")}`, {
                params: { flow_id: currentFlow.id }
              });

              if (response?.data?.vertex_builds) {
                const flowPool = response.data.vertex_builds;
                console.log("[useWebhookEvents] Setting flow pool with build data from API:", Object.keys(flowPool).length, "vertices");
                setFlowPool(flowPool);
              }
            } catch (error) {
              console.error("[useWebhookEvents] Error fetching builds:", error);
            }
          }
        }
      } else {
        console.log("[useWebhookEvents] Build failed");
        setBuildInfo({ error: [data.error || "Build failed"] });
      }
    });

    // ============================================================
    // EVENT: error
    // ============================================================
    eventSource.addEventListener("error", (eventOrError: any) => {
      // Check if this is an error event with data
      if (eventOrError.data) {
        try {
          const data = JSON.parse(eventOrError.data);
          console.error("[useWebhookEvents] Build error:", data);

          // Show error alert
          setErrorData({
            title: "Webhook Build Error",
            list: [data.message || "An error occurred during build"],
          });

          setIsBuilding(false);
          clearEdgesRunningByNodes();
        } catch {
          // If parsing fails, this is a connection error (handled below)
          console.error("[useWebhookEvents] SSE connection error");
        }
      } else {
        // This is a connection error
        // EventSource will automatically try to reconnect
        console.error("[useWebhookEvents] SSE connection error, will retry...");
      }
    });

    // ============================================================
    // EVENT: heartbeat
    // ============================================================
    eventSource.addEventListener("heartbeat", () => {
      // Keep-alive ping, just log it
      console.log("[useWebhookEvents] Heartbeat received");
    });

    // Cleanup when component unmounts or flow changes
    return () => {
      console.log("[useWebhookEvents] Disconnecting from SSE...");
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [
    currentFlow?.id,
    currentFlow?.endpoint_name,
    updateBuildStatus,
    setIsBuilding,
    updateVerticesBuild,
    addDataToFlowPool,
    updateEdgesRunningByNodes,
    clearEdgesRunningByNodes,
    setErrorData,
    setBuildInfo,
    setFlowPool,
  ]);

  return null;
}
