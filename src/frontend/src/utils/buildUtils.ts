import { AxiosError } from "axios";
import { BuildStatus } from "../constants/enums";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import useFlowStore from "../stores/flowStore";
import { VertexBuildTypeAPI } from "../types/api";

type BuildVerticesParams = {
  flowId: string; // Assuming FlowType is the type for your flow
  input_value?: any; // Replace any with the actual type if it's not any
  startNodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  stopNodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  onGetOrderSuccess?: () => void;
  onBuildUpdate?: (
    data: VertexBuildTypeAPI,
    status: BuildStatus,
    buildId: string
  ) => void; // Replace any with the actual type if it's not any
  onBuildComplete?: (allNodesValid: boolean) => void;
  onBuildError?: (title, list, idList: string[]) => void;
  onBuildStart?: (idList: string[]) => void;
  validateNodes?: (nodes: string[]) => void;
};

function getInactiveVertexData(vertexId: string): VertexBuildTypeAPI {
  // Build VertexBuildTypeAPI
  let inactiveData = {
    results: {},
    artifacts: { repr: "Inactive" },
  };
  let inactiveVertexData = {
    id: vertexId,
    data: inactiveData,
    params: "Inactive",
    run_id: "",
    next_vertices_ids: [],
    inactive_vertices: null,
    valid: false,
    timestamp: new Date().toISOString(),
  };

  return inactiveVertexData;
}

export async function updateVerticesOrder(
  flowId: string,
  startNodeId?: string | null,
  stopNodeId?: string | null
): Promise<{
  verticesLayers: string[][];
  verticesIds: string[];
  runId: string;
}> {
  return new Promise(async (resolve, reject) => {
    const setErrorData = useAlertStore.getState().setErrorData;
    let orderResponse;
    try {
      orderResponse = await getVerticesOrder(flowId, startNodeId, stopNodeId);
    } catch (error: any) {
      console.log(error);
      setErrorData({
        title: "Oops! Looks like you missed something",
        list: [error.response?.data?.detail ?? "Unknown Error"],
      });
      useFlowStore.getState().setIsBuilding(false);
      throw new Error("Invalid nodes");
    }
    let verticesLayers: Array<Array<string>> = [orderResponse.data.ids];
    const runId = orderResponse.data.run_id;
    // if (nodeId) {
    //   for (let i = 0; i < verticesOrder.length; i += 1) {
    //     const innerArray = verticesOrder[i];
    //     const idIndex = innerArray.indexOf(nodeId);
    //     if (idIndex !== -1) {
    //       // If there's a nodeId, we want to run just that component and not the entire layer
    //       // because a layer contains dependencies for the next layer
    //       // and we are stopping at the layer that contains the nodeId
    //       verticesLayers.push([innerArray[idIndex]]);
    //       break; // Stop searching after finding the first occurrence
    //     }
    //     // If the targetId is not found, include the entire inner array
    //     verticesLayers.push(innerArray);
    //   }
    // } else {
    //   verticesLayers = verticesOrder;
    // }
    const verticesIds = orderResponse.data.ids;
    useFlowStore.getState().updateVerticesBuild({
      verticesLayers,
      verticesIds,
      runId,
    });
    resolve({ verticesLayers, verticesIds, runId });
  });
}

export async function buildVertices({
  flowId,
  input_value,
  startNodeId,
  stopNodeId,
  onGetOrderSuccess,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
  onBuildStart,
  validateNodes,
}: BuildVerticesParams) {
  let verticesBuild = useFlowStore.getState().verticesBuild;
  // if startNodeId and stopNodeId are provided
  // something is wrong
  if (startNodeId && stopNodeId) {
    return;
  }
  if (!verticesBuild || startNodeId || stopNodeId) {
    verticesBuild = await updateVerticesOrder(flowId, startNodeId, stopNodeId);
  }

  const verticesIds = verticesBuild?.verticesIds!;
  const verticesLayers = verticesBuild?.verticesLayers!;
  const runId = verticesBuild?.runId!;
  let stop = false;

  if (onGetOrderSuccess) onGetOrderSuccess();

  if (validateNodes) {
    try {
      validateNodes(verticesIds);
    } catch (e) {
      return;
    }
  }

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
      currentLayer.map(async (vertexId) => {
        // Check if id is in the list of inactive nodes
        if (
          !useFlowStore
            .getState()
            .verticesBuild?.verticesIds.includes(vertexId) &&
          onBuildUpdate
        ) {
          // If it is, skip building and set the state to inactive
          onBuildUpdate(
            getInactiveVertexData(vertexId),
            BuildStatus.INACTIVE,
            runId
          );
          buildResults.push(false);
          return;
        }

        // Build the vertex
        await buildVertex({
          flowId,
          id: vertexId,
          input_value,
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
      })
    );
    // Once the current layer is built, move to the next layer
    currentLayerIndex += 1;

    if (stop) {
      break;
    }

    if (onBuildComplete) {
      const allNodesValid = buildResults.every((result) => result);
      onBuildComplete(allNodesValid);
      useFlowStore.getState().setIsBuilding(false);
    }
  }
}
async function buildVertex({
  flowId,
  id,
  input_value,
  onBuildUpdate,
  onBuildError,
  verticesIds,
  buildResults,
  stopBuild,
}: {
  flowId: string;
  id: string;
  input_value: string;
  onBuildUpdate?: (data: any, status: BuildStatus) => void;
  onBuildError?: (title, list, idList: string[]) => void;
  verticesIds: string[];
  buildResults: boolean[];
  stopBuild: () => void;
}) {
  try {
    const buildRes = await postBuildVertex(flowId, id, input_value);

    const buildData: VertexBuildTypeAPI = buildRes.data;
    if (onBuildUpdate) {
      if (!buildData.valid) {
        onBuildError!(
          "Error Building Component",
          [buildData.params],
          verticesIds
        );
        stopBuild();
      }
      onBuildUpdate(buildData, BuildStatus.BUILT);
    }
    buildResults.push(buildData.valid);
  } catch (error) {
    onBuildError!(
      "Error Building Component",
      [(error as AxiosError<any>).response?.data?.detail ?? "Unknown Error"],
      verticesIds
    );
    stopBuild();
  }
}
