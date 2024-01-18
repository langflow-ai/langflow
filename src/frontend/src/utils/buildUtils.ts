import { AxiosError } from "axios";
import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import { FlowType } from "../types/flow";

type BuildVerticesParams = {
  flow: FlowType; // Assuming FlowType is the type for your flow
  nodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  onProgressUpdate?: (progress: number) => void; // Replace number with the actual type if it's not a number
  onBuildUpdate?: (data: any) => void; // Replace any with the actual type of data
  onBuildComplete?: (allNodesValid: boolean) => void;
  onBuildError?: (title, list) => void;
};

export async function buildVertices({
  flow,
  nodeId = null,
  onProgressUpdate,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
}: BuildVerticesParams) {
  try {
    // Step 1: Get vertices order
    console.log(JSON.parse(JSON.stringify(flow)));
    let orderResponse = await getVerticesOrder(flow.id);
    console.log(orderResponse);
    let verticesOrder: Array<Array<string>> = orderResponse.data.ids;
    console.log('order', verticesOrder);

    // Determine the range of vertices to build
    let vertexIndex: number | null = null;
    if (nodeId) {
      vertexIndex = verticesOrder.findIndex((ids) => ids.includes(nodeId));
    }
    let buildRange =
      vertexIndex !== null ? verticesOrder.slice(0, vertexIndex + 1) : verticesOrder;
    console.log(buildRange);

    const buildResults: boolean[] = [];
    await buildRange.reduce(async (previousPromise, idArray) => {
      await previousPromise;
      return Promise.all(
        idArray.map(async (vertexId) => {
          try {
            const buildResponse = await postBuildVertex(flow, vertexId);
            const buildData = buildResponse.data;
            if (onProgressUpdate) {
              const progress =
                verticesOrder
                  .map((ids) => ids.indexOf(vertexId))
                  .filter((index) => index !== -1)[0] /
                verticesOrder.flat().length;
              onProgressUpdate(progress);
            }
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
              onBuildError(
                "Error Building Component",
                [(error as AxiosError<any>).response?.data?.detail ?? "Unknown Error"]
              );
            }
          }
        })
      );
    }, Promise.resolve());

    // Callback for when all vertices have been built
    if (onBuildComplete) {
      const allNodesValid = buildResults.every((result) => result);
      onBuildComplete(allNodesValid);
    }
  } catch (error) {
    // Callback for handling errors
    if (onBuildError) {
      onBuildError(
        "Error Building Component",
        [(error as AxiosError<any>).response?.data?.detail ?? "Unknown Error"]
      );
    }
  }
}
