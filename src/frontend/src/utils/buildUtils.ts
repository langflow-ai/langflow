import { AxiosError } from "axios";
import { BuildStatus } from "../constants/enums";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import useFlowStore from "../stores/flowStore";
import { VertexBuildTypeAPI } from "../types/api";

type BuildVerticesParams = {
  flowId: string; // Assuming FlowType is the type for your flow
  input_value?: any; // Replace any with the actual type if it's not any
  nodeId?: string | null; // Assuming nodeId is of type string, and it's optional
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
    inactive_vertices: null,
    valid: false,
    timestamp: new Date().toISOString(),
  };

  return inactiveVertexData;
}

export async function updateVerticesOrder(
  flowId: string,
  nodeId: string | null
): Promise<{
  verticesLayers: string[][];
  verticesIds: string[];
  runId: string;
}> {
  return new Promise(async (resolve, reject) => {
    const setErrorData = useAlertStore.getState().setErrorData;
    let orderResponse;
    try {
      orderResponse = await getVerticesOrder(flowId, nodeId);
    } catch (error: any) {
      console.log(error);
      setErrorData({
        title: "Oops! Looks like you missed something",
        list: [error.response?.data?.detail ?? "Unknown Error"],
      });
      useFlowStore.getState().setIsBuilding(false);
      throw new Error("Invalid nodes");
    }
    let verticesOrder: Array<Array<string>> = orderResponse.data.ids;
    let verticesLayers: Array<Array<string>> = [];
    const runId = orderResponse.data.run_id;
    if (nodeId) {
      for (let i = 0; i < verticesOrder.length; i += 1) {
        const innerArray = verticesOrder[i];
        const idIndex = innerArray.indexOf(nodeId);
        if (idIndex !== -1) {
          // If there's a nodeId, we want to run just that component and not the entire layer
          // because a layer contains dependencies for the next layer
          // and we are stopping at the layer that contains the nodeId
          verticesLayers.push([innerArray[idIndex]]);
          break; // Stop searching after finding the first occurrence
        }
        // If the targetId is not found, include the entire inner array
        verticesLayers.push(innerArray);
      }
    } else {
      verticesLayers = verticesOrder;
    }
    const verticesIds = verticesOrder.flat();
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
  nodeId = null,
  onGetOrderSuccess,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
  onBuildStart,
  validateNodes,
}: BuildVerticesParams) {
  let verticesBuild = useFlowStore.getState().verticesBuild;

  if (!verticesBuild || nodeId) {
    verticesBuild = await updateVerticesOrder(flowId, nodeId);
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
  console.log(verticesLayers);
  while (currentLayerIndex < verticesLayers.length) {
    const currentLayer = verticesLayers[currentLayerIndex];
    if (onBuildStart) onBuildStart(currentLayer);
    await Promise.all(
      currentLayer.map(async (vertexId) => {
        // Check if id is in the list of inactive nodes
        if (!verticesIds.includes(vertexId) && onBuildUpdate) {
          // If it is, skip building and set the state to inactive
          onBuildUpdate(
            getInactiveVertexData(vertexId),
            BuildStatus.INACTIVE,
            runId
          );
          buildResults.push(false);
          return;
        }
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
