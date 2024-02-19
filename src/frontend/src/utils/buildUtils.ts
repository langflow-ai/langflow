import { AxiosError } from "axios";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import { VertexBuildTypeAPI } from "../types/api";

type BuildVerticesParams = {
  flowId: string; // Assuming FlowType is the type for your flow
  nodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  onProgressUpdate?: (progress: number) => void; // Replace number with the actual type if it's not a number
  onBuildUpdate?: (data: any) => void; // Replace any with the actual type of data
  onBuildComplete?: (allNodesValid: boolean) => void;
  onBuildError?: (title, list) => void;
};

export async function buildVertices({
  flowId,
  nodeId = null,
  onProgressUpdate,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
}: BuildVerticesParams) {
  let orderResponse = await getVerticesOrder(flowId, nodeId);
  let verticesOrder: Array<Array<string>> = orderResponse.data.ids;
  let vertices: Array<Array<string>> = [];
  if (nodeId) {
    for (let i = 0; i < verticesOrder.length; i += 1) {
      const innerArray = verticesOrder[i];
      const idIndex = innerArray.indexOf(nodeId);
      if (idIndex !== -1) {
        // If there's a nodeId, we want to run just that component and not the entire layer
        // because a layer contains dependencies for the next layer
        // and we are stopping at the layer that contains the nodeId
        vertices.push([innerArray[idIndex]]);
        break; // Stop searching after finding the first occurrence
      }
      // If the targetId is not found, include the entire inner array
      vertices.push(innerArray);
    }
  } else {
    vertices = verticesOrder;
  }

  // Set each vertex state to building

  const buildResults: Array<boolean> = [];
  for (let i = 0; i < vertices.length; i += 1) {
    await Promise.all(
      vertices[i].map(async (id) => {
        try {
          // Set vertex state to building
          const buildRes = await postBuildVertex(flowId, id);
          const buildData: VertexBuildTypeAPI = buildRes.data;
          if (onBuildUpdate) {
            let data = {};
            if (!buildData.valid) {
              if (onBuildError) {
                onBuildError("Error Building Component", [buildData.params]);
              }
            }
            data[buildData.id] = buildData;
            onBuildUpdate({ data, id: buildData.id });
          }
          buildResults.push(buildData.valid);
        } catch (error) {
          if (onBuildError) {
            console.log(error);
            onBuildError("Error Building Component", [
              (error as AxiosError<any>).response?.data?.detail ??
                "Unknown Error",
            ]);
          }
        }
      })
    );
  }
  if (onBuildComplete) {
    const allNodesValid = buildResults.every((result) => result);
    onBuildComplete(allNodesValid);
  }
}
