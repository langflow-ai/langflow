import { getVerticesOrder, postBuildVertex } from "../controllers/API";
import { FlowType } from "../types/flow";

type BuildVerticesParams = {
  flow: FlowType; // Assuming FlowType is the type for your flow
  nodeId?: string | null; // Assuming nodeId is of type string, and it's optional
  onProgressUpdate?: (progress: number) => void; // Replace number with the actual type if it's not a number
  onBuildUpdate?: (data: any) => void; // Replace any with the actual type of data
  onBuildComplete?: (allNodesValid: boolean) => void;
  onBuildError?: (error: Error) => void;
};

export async function buildVertices({
  flow,
  // nodeId should be optional
  nodeId = null,
  onProgressUpdate,
  onBuildUpdate,
  onBuildComplete,
  onBuildError,
}: BuildVerticesParams) {
  try {
    // Step 1: Get vertices order
    let orderResponse = await getVerticesOrder(flow.id);
    let verticesOrder = orderResponse.data.ids;
    // Determine the range of vertices to build
    let vertexIndex: number | null = null;
    if (nodeId !== null) {
      vertexIndex = verticesOrder.indexOf(nodeId);
    }
    let buildRange =
      vertexIndex !== null
        ? verticesOrder.slice(0, vertexIndex + 1)
        : verticesOrder;

    const buildResults: boolean[] = [];
    for (let vertexId of buildRange) {
      const buildResponse = await postBuildVertex(flow, vertexId);
      const buildData = buildResponse.data;
      if (onProgressUpdate) {
        onProgressUpdate(
          (prevProgress) => prevProgress + 1 / verticesOrder.length
        );
      }
      // Update SSE data
      if (onBuildUpdate) {
        onBuildUpdate({ [buildData.id]: buildData });
      }
      buildResults.push(buildData.valid);
    }
    // Callback for when all vertices have been built
    if (onBuildComplete) {
      const allNodesValid = buildResults.every((result) => result);
      onBuildComplete(allNodesValid);
    }
  } catch (error) {
    // Callback for handling errors
    if (onBuildError) {
      onBuildError(error);
    }
  }
}
