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
    inactivated_vertices: null,
    activated_vertices: null,
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
  let dynamicVerticesLayers: Array<Array<string>> = [...verticesLayers];

  const handleBuildUpdate = (data: VertexBuildTypeAPI, status: BuildStatus) => {
    // Handle activated vertices
    console.log("handleBuildUpdate", data, status);
    if (data.activated_vertices && data.activated_vertices.length > 0) {
      // Logic to determine the correct placement for activated vertices in dynamicVerticesLayers
      // For simplicity, this example adds them to the next layer
      // const nextLayerIndex = i + 1; i doesnt exist in this scope
      // we don't want to add the activated vertices to the last layer
      // because these vertices should be built right away
      const thisVertexLayer = dynamicVerticesLayers.findIndex((layer) =>
        layer.includes(data.id)
      );
      const nextLayerIndex = thisVertexLayer + 1;
      console.log("nextLayerIndex", nextLayerIndex);
      console.log("dynamicVerticesLayers", dynamicVerticesLayers);
      if (dynamicVerticesLayers[nextLayerIndex]) {
        // If the next layer exists, add the activated vertices to it
        // dynamicVerticesLayers[nextLayerIndex] = dynamicVerticesLayers[
        //   nextLayerIndex
        // ].concat(data.activated_vertices);
        // instead of adding them all at once, add them one by one
        // add one per layer and if the next layer doesn't exist, create it

        for (const vertex of data.activated_vertices) {
          console.log("vertex", vertex);
          if (dynamicVerticesLayers[nextLayerIndex].includes(vertex)) {
            continue;
          } else if (dynamicVerticesLayers[nextLayerIndex].length > 0) {
            dynamicVerticesLayers[nextLayerIndex].push(vertex);
          } else {
            dynamicVerticesLayers[nextLayerIndex] = [vertex];
          }
          console.log("dynamicVerticesLayers", dynamicVerticesLayers);
        }
      } else {
        dynamicVerticesLayers.push(data.activated_vertices);
        console.log(dynamicVerticesLayers);
      }
    }
    if (onBuildUpdate) onBuildUpdate(data, status, runId);
  };

  // Set each vertex state to building
  const buildResults: Array<boolean> = [];
  for (let i = 0; i < dynamicVerticesLayers.length; i++) {
    console.log(dynamicVerticesLayers);
    const layer = dynamicVerticesLayers[i];
    if (onBuildStart) onBuildStart(layer);
    for (const id of layer) {
      // Check if id is in the list of inactive nodes
      // useFlowStore because it gets updated constantly
      if (
        !useFlowStore.getState().verticesBuild?.verticesIds.includes(id) &&
        onBuildUpdate
      ) {
        // If it is, skip building and set the state to inactive
        console.log("inactive", id);
        onBuildUpdate(getInactiveVertexData(id), BuildStatus.INACTIVE, runId);
        buildResults.push(false);
        continue;
      }

      await buildVertex({
        flowId,
        id,
        input_value,
        onBuildUpdate: handleBuildUpdate,
        onBuildError,
        verticesIds,
        buildResults,
        stopBuild: () => {
          stop = true;
        },
      });
      if (stop) {
        break;
      }
    }
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
