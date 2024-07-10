import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { ReactFlowJsonObject } from "reactflow";
import { AxiosRequestConfig } from "axios";

interface retrieveGetVerticesOrder {
  flowId: string;
  data?: ReactFlowJsonObject;
  stopNodeId?: string;
  startNodeId?: string;
}

// add types for error handling and success
export const usePostRetrieveVertexOrder: useMutationFunctionType<retrieveGetVerticesOrder> = (
  options,
) => {
  const { mutate } = UseRequestProcessor();

  const postRetrieveVertexOrder = async ({flowId,data:flow,startNodeId,stopNodeId}: retrieveGetVerticesOrder): Promise<any> => {
    // nodeId is optional and is a query parameter
    // if nodeId is not provided, the API will return all vertices
    const config: AxiosRequestConfig<any> = {};
    if (stopNodeId) {
      config["params"] = { stop_component_id: stopNodeId };
    } else if (startNodeId) {
      config["params"] = { start_component_id: startNodeId };
    }
    const data = {
      data: {},
    };
    if (flow && flow.nodes && flow.edges) {
      const { nodes, edges } = flow;
      data["data"]["nodes"] = nodes;
      data["data"]["edges"] = edges;
    }
    const response = await api.post(
      `${getURL("FILES")}/${flowId}/vertices`,
      data,
      config,
    );

    return response.data;
  };

  const mutation = mutate(["usePostRetrieveVertexOrder",], postRetrieveVertexOrder, options);

  return mutation;
};