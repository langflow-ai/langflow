import {
  BASE_URL_API,
  POLLING_INTERVAL,
  POLLING_MESSAGES,
} from "@/constants/constants";
import { performStreamingRequest } from "@/controllers/API/api";
import { useMessagesStore } from "@/stores/messagesStore";
import { Edge, Node } from "@xyflow/react";
import { AxiosError } from "axios";
import { flushSync } from "react-dom";
import { BuildStatus } from "../constants/enums";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import useFlowStore from "../stores/flowStore";
import { VertexBuildTypeAPI } from "../types/api";
import { isErrorLogType } from "../types/utils/typeCheckingUtils";
import { VertexLayerElementType } from "../types/zustand/flow";
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
  stream?: boolean;
};

function getInactiveVertexData(vertexId: string): VertexBuildTypeAPI {
  // Build VertexBuildTypeAPI
  let inactiveData = {
    results: {},
    outputs: {},
    messages: [],
    logs: {},
    inactive: true,
  };
  let inactiveVertexData = {
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
    } catch (error: any) {
      setErrorData({
        title: "Oops! Looks like you missed something",
        list: [error.response?.data?.detail ?? "Unknown Error"],
      });
      useFlowStore.getState().setIsBuilding(false);
      throw new Error("Invalid components");
    }
    // orderResponse.data.ids,
    // for each id we need to build the VertexLayerElementType object as
    // {id: id, reference: id}
    let verticesLayers: Array<Array<VertexLayerElementType>> =
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
  try {
    // Use shouldUsePolling() to determine stream mode
    return await buildFlowVertices({ ...params });
  } catch (e: any) {
    if (
      e.message === POLLING_MESSAGES.ENDPOINT_NOT_AVAILABLE ||
      e.message === POLLING_MESSAGES.STREAMING_NOT_SUPPORTED
    ) {
      // Fallback to polling
      return await buildFlowVertices({ ...params, stream: false });
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
): Promise<void> {
  let isDone = false;
  while (!isDone) {
    const response = await fetch(`${url}?stream=false`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Error polling build events");
    }

    const data = await response.json();
    if (!data.event) {
      // No event in this request, try again
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    // Process the event
    const event = JSON.parse(data.event);
    await onEvent(
      event.event,
      event.data,
      buildResults,
      verticesStartTimeMs,
      callbacks,
    );

    // Check if this was the end event or if we got a null value
    if (event.event === "end" || data.event === null) {
      isDone = true;
    }

    // Add a small delay between polls to avoid overwhelming the server
    await new Promise((resolve) => setTimeout(resolve, POLLING_INTERVAL));
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
  stream = true,
}: BuildVerticesParams) {
  const inputs = {};
  let buildUrl = `${BASE_URL_API}build/${flowId}/flow`;
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

    // Then stream the events
    const eventsUrl = `${BASE_URL_API}build/${job_id}/events`;
    const buildResults: Array<boolean> = [];
    const verticesStartTimeMs: Map<string, number> = new Map();

    if (stream) {
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
      return pollBuildEvents(
        eventsUrl,
        buildResults,
        verticesStartTimeMs,
        callbacks,
      );
    }
  } catch (error) {
    console.error("Build process error:", error);
    onBuildError!("Error Building Flow", [
      (error as Error).message || "An unexpected error occurred",
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
        } catch (e) {
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
  let verticesOrderResponse = await updateVerticesOrder(
    flowId,
    startNodeId,
    stopNodeId,
    nodes,
    edges,
  );
  if (onValidateNodes) {
    try {
      onValidateNodes(verticesOrderResponse.verticesToRun);
    } catch (e) {
      useFlowStore.getState().setIsBuilding(false);
      return;
    }
  }
  if (onGetOrderSuccess) onGetOrderSuccess();
  let verticesBuild = useFlowStore.getState().verticesBuild;

  const verticesIds = verticesBuild?.verticesIds!;
  const verticesLayers = verticesBuild?.verticesLayers!;
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
