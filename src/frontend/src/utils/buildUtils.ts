import type { Edge, Node } from "@xyflow/react";
import type { AxiosError } from "axios";
import { flushSync } from "react-dom";
import { MISSED_ERROR_ALERT } from "@/constants/alerts_constants";
import {
  BUILD_POLLING_INTERVAL,
  POLLING_MESSAGES,
} from "@/constants/constants";
import { performStreamingRequest } from "@/controllers/API/api";
import {
  customBuildUrl,
  customCancelBuildUrl,
  customEventsUrl,
} from "@/customization/utils/custom-buildUtils";
import { useMessagesStore } from "@/stores/messagesStore";
import { BuildStatus, EventDeliveryType } from "../constants/enums";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import useFlowStore from "../stores/flowStore";
import type { VertexBuildTypeAPI } from "../types/api";
import { isErrorLogType } from "../types/utils/typeCheckingUtils";
import type { VertexLayerElementType } from "../types/zustand/flow";
import { isStringArray, tryParseJson } from "./utils";

type BuildVerticesParams = {
  flowId: string; // Assuming FlowType is the type for your flow
  input_value?: any; // Replace any with the actual type if it's not any
  files?: string[];
  startNodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  stopNodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  onGetOrderSuccess?: () => void;
  onBuildUpdate?: (
    data: VertexBuildTypeAPI,
    status: BuildStatus,
    buildId: string,
  ) => void; // Replace any with the actual type if it's not any
  onBuildComplete?: (allNodesValid: boolean) => void;
  onBuildError?: (title, list, idList?: VertexLayerElementType[]) => void;
  onBuildStopped?: () => void;
  onBuildStart?: (idList: VertexLayerElementType[]) => void;
  onValidateNodes?: (nodes: string[]) => void;
  nodes?: Node[];
  edges?: Edge[];
  logBuilds?: boolean;
  session?: string;
  playgroundPage?: boolean;
  eventDelivery: EventDeliveryType;
};

function getInactiveVertexData(vertexId: string): VertexBuildTypeAPI {
  // Build VertexBuildTypeAPI
  const inactiveData = {
    results: {},
    outputs: {},
    messages: [],
    logs: {},
    inactive: true,
  };
  const inactiveVertexData = {
    id: vertexId,
    data: inactiveData,
    inactivated_vertices: null,
    run_id: "",
    next_vertices_ids: [],
    top_level_vertices: [],
    inactive_vertices: null,
    valid: false,
    params: null,
    messages: [],
    artifacts: null,
    timestamp: new Date().toISOString(),
  };

  return inactiveVertexData;
}

function logFlowLoad(message: string, data?: any) {
  console.warn(`[FlowLoad] ${message}`, data || "");
}

export async function updateVerticesOrder(
  flowId: string,
  startNodeId?: string | null,
  stopNodeId?: string | null,
  nodes?: Node[],
  edges?: Edge[],
): Promise<{
  verticesLayers: VertexLayerElementType[][];
  verticesIds: string[];
  runId?: string;
  verticesToRun: string[];
}> {
  logFlowLoad("Updating vertices order");
  return new Promise(async (resolve, reject) => {
    const setErrorData = useAlertStore.getState().setErrorData;
    let orderResponse;
    try {
      orderResponse = await getVerticesOrder(
        flowId,
        startNodeId,
        stopNodeId,
        nodes,
        edges,
      );
      logFlowLoad("Got vertices order response:", orderResponse);
    } catch (error: any) {
      logFlowLoad("Error getting vertices order:", error);
      setErrorData({
        title: MISSED_ERROR_ALERT,
        list: [error.response?.data?.detail ?? "Unknown Error"],
      });
      useFlowStore.getState().setIsBuilding(false);
      throw new Error("Invalid components");
    }
    // orderResponse.data.ids,
    // for each id we need to build the VertexLayerElementType object as
    // {id: id, reference: id}
    const verticesLayers: Array<Array<VertexLayerElementType>> =
      orderResponse.data.ids.map((id: string) => {
        return [{ id: id, reference: id }];
      });

    const runId = orderResponse.data.run_id;
    const verticesToRun = orderResponse.data.vertices_to_run;

    useFlowStore
      .getState()
      .updateBuildStatus(verticesToRun, BuildStatus.TO_BUILD);

    const verticesIds = orderResponse.data.ids;
    useFlowStore.getState().updateVerticesBuild({
      verticesLayers,
      verticesIds,
      runId,
      verticesToRun,
    });
    resolve({ verticesLayers, verticesIds, runId, verticesToRun });
  });
}

export async function buildFlowVerticesWithFallback(
  params: BuildVerticesParams,
) {
  logFlowLoad("Starting flow load");
  try {
    // Use the event_delivery parameter directly
    return await buildFlowVertices({ ...params });
  } catch (e: any) {
    if (
      e.message === POLLING_MESSAGES.ENDPOINT_NOT_AVAILABLE ||
      e.message === POLLING_MESSAGES.STREAMING_NOT_SUPPORTED
    ) {
      // Fallback to polling
      return await buildFlowVertices({
        ...params,
        eventDelivery: EventDeliveryType.POLLING,
      });
    }
    throw e;
  }
}

const MIN_VISUAL_BUILD_TIME_MS = 300;

async function pollBuildEvents(
  url: string,
  buildResults: Array<boolean>,
  verticesStartTimeMs: Map<string, number>,
  callbacks: {
    onBuildStart?: (idList: VertexLayerElementType[]) => void;
    onBuildUpdate?: (data: any, status: BuildStatus, buildId: string) => void;
    onBuildComplete?: (allNodesValid: boolean) => void;
    onBuildError?: (
      title: string,
      list: string[],
      idList?: VertexLayerElementType[],
    ) => void;
    onGetOrderSuccess?: () => void;
    onValidateNodes?: (nodes: string[]) => void;
  },
  abortController: AbortController,
): Promise<void> {
  let isDone = false;
  while (!isDone) {
    const response = await fetch(
      `${url}?event_delivery=${EventDeliveryType.POLLING}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-ndjson",
        },
        signal: abortController.signal, // Add abort signal to fetch
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail ||
          "Langflow was not able to connect to the server. Please make sure your connection is working properly.",
      );
    }

    // Get the response text - will be NDJSON format (one JSON per line)
    const responseText = await response.text();

    // Skip if empty response
    if (!responseText.trim()) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    // Split by newlines to get individual JSON objects
    const eventLines = responseText.split("\n").filter((line) => line.trim());

    // If no events, continue polling
    if (eventLines.length === 0) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    // Process all events in the NDJSON response
    for (const eventStr of eventLines) {
      // Process the event
      const event = JSON.parse(eventStr);
      const result = await onEvent(
        event.event,
        event.data,
        buildResults,
        verticesStartTimeMs,
        callbacks,
      );

      if (!result) {
        isDone = true;
        abortController.abort();
        break;
      }

      // Check if this was the end event
      if (event.event === "end") {
        isDone = true;
        break;
      }
    }

    // Add a small delay between polls
    await new Promise((resolve) => setTimeout(resolve, BUILD_POLLING_INTERVAL));
  }
}

export async function buildFlowVertices({
  flowId,
  input_value,
  files,
  startNodeId,
  stopNodeId,
  onGetOrderSuccess,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
  onBuildStopped,
  onBuildStart,
  onValidateNodes,
  nodes,
  edges,
  logBuilds,
  session,
  playgroundPage,
  eventDelivery,
}: BuildVerticesParams) {
  const inputs = {};

  let buildUrl = customBuildUrl(flowId, playgroundPage);

  const queryParams = new URLSearchParams();

  if (startNodeId) {
    queryParams.append("start_component_id", startNodeId);
  }
  if (stopNodeId) {
    queryParams.append("stop_component_id", stopNodeId);
  }
  if (logBuilds !== undefined) {
    queryParams.append("log_builds", logBuilds.toString());
  }

  queryParams.append(
    "event_delivery",
    eventDelivery ?? EventDeliveryType.POLLING,
  );

  if (queryParams.toString()) {
    buildUrl = `${buildUrl}?${queryParams.toString()}`;
  }

  const postData = {};
  if (files) {
    postData["files"] = files;
  }
  if (nodes) {
    postData["data"] = {
      nodes,
      edges,
    };
  }
  if (typeof input_value !== "undefined") {
    inputs["input_value"] = input_value;
  }
  if (session) {
    inputs["session"] = session;
  }
  if (Object.keys(inputs).length > 0) {
    postData["inputs"] = inputs;
  }

  try {
    // If event_delivery is direct, we'll stream from the build endpoint directly
    if (eventDelivery === EventDeliveryType.DIRECT) {
      const buildController = new AbortController();
      buildController.signal.addEventListener("abort", () => {
        onBuildStopped && onBuildStopped();
      });
      useFlowStore.getState().setBuildController(buildController);

      const buildResults: Array<boolean> = [];
      const verticesStartTimeMs: Map<string, number> = new Map();

      return performStreamingRequest({
        method: "POST",
        url: buildUrl,
        body: postData,
        onData: async (event) => {
          const type = event["event"];
          const data = event["data"];
          return await onEvent(type, data, buildResults, verticesStartTimeMs, {
            onBuildStart,
            onBuildUpdate,
            onBuildComplete,
            onBuildError,
            onGetOrderSuccess,
            onValidateNodes,
          });
        },
        onError: (statusCode) => {
          if (statusCode === 404) {
            throw new Error("Flow not found");
          }
          throw new Error("Error processing build events");
        },
        onNetworkError: (error: Error) => {
          if (error.name === "AbortError") {
            onBuildStopped && onBuildStopped();
            return;
          }
          onBuildError!("Error Building Component", [
            "Network error. Please check the connection to the server.",
          ]);
        },
        buildController,
      });
    }
  } catch (e) {
    console.error(e);
  }

  try {
    // Otherwise, use the existing two-step process (job_id + events endpoint)
    // First, start the build and get the job ID
    const buildResponse = await fetch(buildUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(postData),
    });

    if (!buildResponse.ok) {
      if (buildResponse.status === 404) {
        throw new Error("Flow not found");
      }
      throw new Error("Error starting build process");
    }

    const { job_id } = await buildResponse.json();

    const cancelBuildUrl = customCancelBuildUrl(job_id);

    // Get the buildController from flowStore
    const buildController = new AbortController();
    buildController.signal.addEventListener("abort", () => {
      try {
        fetch(cancelBuildUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });
      } catch (error) {
        console.error("Error canceling build:", error);
      }
    });
    useFlowStore.getState().setBuildController(buildController);
    // Then stream the events
    const eventsUrl = customEventsUrl(job_id);
    const buildResults: Array<boolean> = [];
    const verticesStartTimeMs: Map<string, number> = new Map();

    if (eventDelivery === EventDeliveryType.STREAMING) {
      return performStreamingRequest({
        method: "GET",
        url: eventsUrl,
        onData: async (event) => {
          const type = event["event"];
          const data = event["data"];
          return await onEvent(type, data, buildResults, verticesStartTimeMs, {
            onBuildStart,
            onBuildUpdate,
            onBuildComplete,
            onBuildError,
            onGetOrderSuccess,
            onValidateNodes,
          });
        },
        onError: (statusCode) => {
          if (statusCode === 404) {
            throw new Error("Build job not found");
          }
          throw new Error("Error processing build events");
        },
        onNetworkError: (error: Error) => {
          if (error.name === "AbortError") {
            onBuildStopped && onBuildStopped();
            return;
          }
          onBuildError!("Error Building Component", [
            "Network error. Please check the connection to the server.",
          ]);
        },
        buildController,
      });
    } else {
      const callbacks = {
        onBuildStart,
        onBuildUpdate,
        onBuildComplete,
        onBuildError,
        onGetOrderSuccess,
        onValidateNodes,
      };
      return await pollBuildEvents(
        eventsUrl,
        buildResults,
        verticesStartTimeMs,
        callbacks,
        buildController,
      );
    }
  } catch (error: unknown) {
    console.error("Build process error:", error);
    if (error instanceof Error && error.name === "AbortError") {
      onBuildStopped && onBuildStopped();
      return;
    }
    onBuildError!("Error Building Flow", [
      (error as Error).message ||
        "Langflow was not able to connect to the server. Please make sure your connection is working properly.",
    ]);
    throw error;
  }
}
/**
 * Handles various build events and calls corresponding callbacks.
 *
 * @param {string} type - The event type.
 * @param {any} data - The event data.
 * @param {boolean[]} buildResults - Array tracking build results.
 * @param {Map<string, number>} verticesStartTimeMs - Map tracking start times for vertices.
 * @param {Object} callbacks - Object containing callback functions.
 * @param {(idList: VertexLayerElementType[]) => void} [callbacks.onBuildStart] - Callback when vertices start building.
 * @param {(data: any, status: BuildStatus, buildId: string) => void} [callbacks.onBuildUpdate] - Callback for build updates.
 * @param {(allNodesValid: boolean) => void} [callbacks.onBuildComplete] - Callback when build completes.
 * @param {(title: string, list: string[], idList?: VertexLayerElementType[]) => void} [callbacks.onBuildError] - Callback on build errors.
 * @param {() => void} [callbacks.onGetOrderSuccess] - Callback for successful ordering.
 * @param {(nodes: string[]) => void} [callbacks.onValidateNodes] - Callback to validate nodes.
 * @param {(lock: boolean) => void} [callbacks.setLockChat] - Callback to lock/unlock chat.
 * @returns {Promise<boolean>} Promise that resolves to true if the event was handled successfully.
 */
async function onEvent(
  type: string,
  data: any,
  buildResults: boolean[],
  verticesStartTimeMs: Map<string, number>,
  callbacks: {
    onBuildStart?: (idList: VertexLayerElementType[]) => void;
    onBuildUpdate?: (data: any, status: BuildStatus, buildId: string) => void;
    onBuildComplete?: (allNodesValid: boolean) => void;
    onBuildError?: (
      title: string,
      list: string[],
      idList?: VertexLayerElementType[],
    ) => void;
    onGetOrderSuccess?: () => void;
    onValidateNodes?: (nodes: string[]) => void;
  },
): Promise<boolean> {
  const {
    onBuildStart,
    onBuildUpdate,
    onBuildComplete,
    onBuildError,
    onGetOrderSuccess,
    onValidateNodes,
  } = callbacks;

  // Helper to update status and register start times for an array of vertex IDs.
  const onStartVertices = (ids: Array<string>) => {
    useFlowStore.getState().updateBuildStatus(ids, BuildStatus.TO_BUILD);
    if (onBuildStart) {
      onBuildStart(ids.map((id) => ({ id: id, reference: id })));
    }
    ids.forEach((id) => verticesStartTimeMs.set(id, Date.now()));
  };

  switch (type) {
    case "vertices_sorted": {
      const verticesToRun = data.to_run;
      const verticesIds = data.ids;

      onStartVertices(verticesIds);

      const verticesLayers: Array<Array<VertexLayerElementType>> =
        verticesIds.map((id: string) => [{ id: id, reference: id }]);

      useFlowStore.getState().updateVerticesBuild({
        verticesLayers,
        verticesIds,
        verticesToRun,
      });
      if (onValidateNodes) {
        try {
          onValidateNodes(data.to_run);
          if (onGetOrderSuccess) onGetOrderSuccess();
          useFlowStore.getState().setIsBuilding(true);
          return true;
        } catch (_e) {
          useFlowStore.getState().setIsBuilding(false);
          return false;
        }
      }
      return true;
    }
    case "end_vertex": {
      const buildData = data.build_data;
      const startTimeMs = verticesStartTimeMs.get(buildData.id);
      if (startTimeMs) {
        const delta = Date.now() - startTimeMs;
        if (delta < MIN_VISUAL_BUILD_TIME_MS) {
          // Ensure a minimum visual build time for a smoother UI experience.
          await new Promise((resolve) =>
            setTimeout(resolve, MIN_VISUAL_BUILD_TIME_MS - delta),
          );
        }
      }

      if (onBuildUpdate) {
        if (!buildData.valid) {
          // Aggregate error messages from the build outputs.
          const errorMessages = Object.keys(buildData.data.outputs).flatMap(
            (key) => {
              const outputs = buildData.data.outputs[key];
              if (Array.isArray(outputs)) {
                return outputs
                  .filter((log) => isErrorLogType(log.message))
                  .map((log) => log.message.errorMessage);
              }
              if (!isErrorLogType(outputs.message)) {
                return [];
              }
              return [outputs.message.errorMessage];
            },
          );
          onBuildError &&
            onBuildError("Error Building Component", errorMessages, [
              { id: buildData.id },
            ]);
          onBuildUpdate(buildData, BuildStatus.ERROR, "");
          buildResults.push(false);
          return false;
        } else {
          onBuildUpdate(buildData, BuildStatus.BUILT, "");
          buildResults.push(true);
        }
      }

      await useFlowStore.getState().clearEdgesRunningByNodes();

      if (buildData.next_vertices_ids) {
        if (isStringArray(buildData.next_vertices_ids)) {
          useFlowStore
            .getState()
            .setCurrentBuildingNodeId(buildData.next_vertices_ids ?? []);
          useFlowStore
            .getState()
            .updateEdgesRunningByNodes(buildData.next_vertices_ids ?? [], true);
        }
        onStartVertices(buildData.next_vertices_ids);
      }
      return true;
    }
    case "add_message": {
      // Add a message to the messages store.
      useMessagesStore.getState().addMessage(data);
      return true;
    }
    case "token": {
      // Use flushSync with a timeout to avoid React batching issues.
      setTimeout(() => {
        flushSync(() => {
          useMessagesStore.getState().updateMessageText(data.id, data.chunk);
        });
      }, 10);
      return true;
    }
    case "remove_message": {
      useMessagesStore.getState().removeMessage(data);
      return true;
    }
    case "end": {
      const allNodesValid = buildResults.every((result) => result);
      onBuildComplete && onBuildComplete(allNodesValid);
      useFlowStore.getState().setIsBuilding(false);
      return true;
    }
    case "error": {
      if (data?.category === "error") {
        useMessagesStore.getState().addMessage(data);
        // Use a falsy check to correctly determine if the source ID is missing.
        if (!data?.properties?.source?.id) {
          onBuildError && onBuildError("Error Building Flow", [data.text]);
        }
      }
      buildResults.push(false);
      return true;
    }
    case "build_start":
      useFlowStore
        .getState()
        .updateBuildStatus([data.id], BuildStatus.BUILDING);
      break;
    case "build_end":
      useFlowStore.getState().updateBuildStatus([data.id], BuildStatus.BUILT);
      break;
    default:
      return true;
  }
  return true;
}

export async function buildVertices({
  flowId,
  input_value,
  files,
  startNodeId,
  stopNodeId,
  onGetOrderSuccess,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
  onBuildStart,
  onValidateNodes,
  nodes,
  edges,
}: BuildVerticesParams) {
  // if startNodeId and stopNodeId are provided
  // something is wrong
  if (startNodeId && stopNodeId) {
    return;
  }
  const verticesOrderResponse = await updateVerticesOrder(
    flowId,
    startNodeId,
    stopNodeId,
    nodes,
    edges,
  );
  if (onValidateNodes) {
    try {
      onValidateNodes(verticesOrderResponse.verticesToRun);
    } catch (_e) {
      useFlowStore.getState().setIsBuilding(false);
      return;
    }
  }
  if (onGetOrderSuccess) onGetOrderSuccess();
  const verticesBuild = useFlowStore.getState().verticesBuild;

  const verticesIds = verticesBuild?.verticesIds!;
  const _verticesLayers = verticesBuild?.verticesLayers!;
  const runId = verticesBuild?.runId!;
  let stop = false;

  useFlowStore.getState().updateBuildStatus(verticesIds, BuildStatus.TO_BUILD);
  useFlowStore.getState().setIsBuilding(true);
  let currentLayerIndex = 0; // Start with the first layer
  // Set each vertex state to building
  const buildResults: Array<boolean> = [];

  // Build each layer
  while (
    currentLayerIndex <
    (useFlowStore.getState().verticesBuild?.verticesLayers! || []).length
  ) {
    // Get the current layer
    const currentLayer =
      useFlowStore.getState().verticesBuild?.verticesLayers![currentLayerIndex];
    // If there are no more layers, we are done
    if (!currentLayer) {
      if (onBuildComplete) {
        const allNodesValid = buildResults.every((result) => result);
        onBuildComplete(allNodesValid);
        useFlowStore.getState().setIsBuilding(false);
      }
      return;
    }
    // If there is a callback for the start of the build, call it
    if (onBuildStart) onBuildStart(currentLayer);
    // Build each vertex in the current layer
    await Promise.all(
      currentLayer.map(async (element) => {
        // Check if id is in the list of inactive nodes
        if (
          !useFlowStore
            .getState()
            .verticesBuild?.verticesIds.includes(element.id) &&
          !useFlowStore
            .getState()
            .verticesBuild?.verticesIds.includes(element.reference ?? "") &&
          onBuildUpdate
        ) {
          // If it is, skip building and set the state to inactive
          if (element.id) {
            onBuildUpdate(
              getInactiveVertexData(element.id),
              BuildStatus.INACTIVE,
              runId,
            );
          }
          if (element.reference) {
            onBuildUpdate(
              getInactiveVertexData(element.reference),
              BuildStatus.INACTIVE,
              runId,
            );
          }
          buildResults.push(false);
          return;
        }

        // Build the vertex
        await buildVertex({
          flowId,
          id: element.id,
          input_value,
          files,
          onBuildUpdate: (data: VertexBuildTypeAPI, status: BuildStatus) => {
            if (onBuildUpdate) onBuildUpdate(data, status, runId);
          },
          onBuildError,
          verticesIds,
          buildResults,
          stopBuild: () => {
            stop = true;
          },
        });
        if (stop) {
          return;
        }
      }),
    );
    // Once the current layer is built, move to the next layer
    currentLayerIndex += 1;

    if (stop) {
      break;
    }
  }
  if (onBuildComplete) {
    const allNodesValid = buildResults.every((result) => result);
    onBuildComplete(allNodesValid);
    useFlowStore.getState().setIsBuilding(false);
  }
}

async function buildVertex({
  flowId,
  id,
  input_value,
  files,
  onBuildUpdate,
  onBuildError,
  verticesIds,
  buildResults,
  stopBuild,
}: {
  flowId: string;
  id: string;
  input_value: string;
  files?: string[];
  onBuildUpdate?: (data: any, status: BuildStatus) => void;
  onBuildError?: (title, list, idList: VertexLayerElementType[]) => void;
  verticesIds: string[];
  buildResults: boolean[];
  stopBuild: () => void;
}) {
  try {
    const buildRes = await postBuildVertex(flowId, id, input_value, files);

    const buildData: VertexBuildTypeAPI = buildRes.data;
    if (onBuildUpdate) {
      if (!buildData.valid) {
        // lots is a dictionary with the key the output field name and the value the log object
        // logs: { [key: string]: { message: any; type: string }[] };
        const errorMessages = Object.keys(buildData.data.outputs).map((key) => {
          const outputs = buildData.data.outputs[key];
          if (Array.isArray(outputs)) {
            return outputs
              .filter((log) => isErrorLogType(log.message))
              .map((log) => log.message.errorMessage);
          }
          if (!isErrorLogType(outputs.message)) {
            return [];
          }
          return [outputs.message.errorMessage];
        });
        onBuildError!(
          "Error Building Component",
          errorMessages,
          verticesIds.map((id) => ({ id })),
        );
        stopBuild();
        onBuildUpdate(buildData, BuildStatus.ERROR);
      } else {
        onBuildUpdate(buildData, BuildStatus.BUILT);
      }
    }
    buildResults.push(buildData.valid);
  } catch (error) {
    console.error(error);
    let errorMessage: string | string[] =
      (error as AxiosError<any>).response?.data?.detail ||
      (error as AxiosError<any>).response?.data?.message ||
      "An unexpected error occurred while building the Component. Please try again.";
    errorMessage = tryParseJson(errorMessage as string) ?? errorMessage;
    if (!Array.isArray(errorMessage)) {
      errorMessage = [errorMessage];
    }
    onBuildError!(
      "Error Building Component",
      errorMessage,
      verticesIds.map((id) => ({ id })),
    );
    buildResults.push(false);
    stopBuild();
  }
}
