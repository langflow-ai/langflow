import { BASE_URL_API } from "@/constants/constants";
import { performStreamingRequest } from "@/controllers/API/api";
import { useMessagesStore } from "@/stores/messagesStore";
import { AxiosError } from "axios";
import { timeStamp } from "console";
import { flushSync } from "react-dom";
import { Edge, Node } from "reactflow";
import { BuildStatus } from "../constants/enums";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import useFlowStore from "../stores/flowStore";
import { VertexBuildTypeAPI } from "../types/api";
import { isErrorLogType } from "../types/utils/typeCheckingUtils";
import { VertexLayerElementType } from "../types/zustand/flow";
import { isStringArray, tryParseJson } from "./utils";

type BuildVerticesParams = {
  setLockChat?: (lock: boolean) => void;
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
  setLockChat?: (lock: boolean) => void,
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
      setLockChat && setLockChat(false);
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
    return await buildFlowVertices(params);
  } catch (e: any) {
    if (e.message === "Endpoint not available") {
      return await buildVertices(params);
    }
    throw e;
  }
}

const MIN_VISUAL_BUILD_TIME_MS = 300;

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
  setLockChat,
  session,
}: BuildVerticesParams) {
  const inputs = {};
  let url = `${BASE_URL_API}build/${flowId}/flow?`;
  if (startNodeId) {
    url = `${url}&start_component_id=${startNodeId}`;
  }
  if (stopNodeId) {
    url = `${url}&stop_component_id=${stopNodeId}`;
  }
  if (logBuilds !== undefined) {
    url = `${url}&log_builds=${logBuilds}`;
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

  const buildResults: Array<boolean> = [];

  const verticesStartTimeMs: Map<string, number> = new Map();

  const onEvent = async (type, data): Promise<boolean> => {
    const onStartVertices = (ids: Array<string>) => {
      useFlowStore.getState().updateBuildStatus(ids, BuildStatus.TO_BUILD);
      if (onBuildStart)
        onBuildStart(ids.map((id) => ({ id: id, reference: id })));
      ids.forEach((id) => verticesStartTimeMs.set(id, Date.now()));
    };

    switch (type) {
      case "vertices_sorted": {
        const verticesToRun = data.to_run;
        const verticesIds = data.ids;

        onStartVertices(verticesIds);

        let verticesLayers: Array<Array<VertexLayerElementType>> =
          verticesIds.map((id: string) => {
            return [{ id: id, reference: id }];
          });

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
            setLockChat && setLockChat(false);
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
            // this is a visual trick to make the build process look more natural
            await new Promise((resolve) =>
              setTimeout(resolve, MIN_VISUAL_BUILD_TIME_MS - delta),
            );
          }
        }

        if (onBuildUpdate) {
          if (!buildData.valid) {
            // lots is a dictionary with the key the output field name and the value the log object
            // logs: { [key: string]: { message: any; type: string }[] };
            const errorMessages = Object.keys(buildData.data.outputs).map(
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
            onBuildError!("Error Building Component", errorMessages, [
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
              .setCurrentBuildingNodeId(buildData?.next_vertices_ids ?? []);
            useFlowStore
              .getState()
              .updateEdgesRunningByNodes(
                buildData?.next_vertices_ids ?? [],
                true,
              );
          }
          onStartVertices(buildData.next_vertices_ids);
        }
        return true;
      }
      case "message": {
        //adds a message to the messsage table
        useMessagesStore.getState().addMessage(data);
        return true;
      }
      case "token": {
        // flushSync and timeout is needed to avoid react batched updates
        setTimeout(() => {
          flushSync(() => {
            useMessagesStore.getState().updateMessageText(data.id, data.chunk);
          });
        }, 10);
        return true;
      }
      case "end": {
        const allNodesValid = buildResults.every((result) => result);
        onBuildComplete!(allNodesValid);
        useFlowStore.getState().setIsBuilding(false);
        return true;
      }
      case "error": {
        useFlowStore.getState().setIsBuilding(false);
        if (data.category === "error") {
          useMessagesStore.getState().addMessage(data);
        }
        buildResults.push(false);
        return true;
      }
      default:
        return true;
    }
    return true;
  };
  return performStreamingRequest({
    method: "POST",
    url,
    body: postData,
    onData: async (event) => {
      const type = event["event"];
      const data = event["data"];
      return await onEvent(type, data);
    },
    onError: (statusCode) => {
      if (statusCode === 404) {
        throw new Error("Endpoint not available");
      }
      throw new Error("Error Building Component");
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
  setLockChat,
}: BuildVerticesParams) {
  // if startNodeId and stopNodeId are provided
  // something is wrong
  if (startNodeId && stopNodeId) {
    return;
  }
  let verticesOrderResponse = await updateVerticesOrder(
    flowId,
    setLockChat,
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
      setLockChat && setLockChat(false);
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
