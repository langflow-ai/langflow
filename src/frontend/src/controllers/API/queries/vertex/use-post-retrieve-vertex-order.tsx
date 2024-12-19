import { useMutationFunctionType } from "@/types/api";
import { ReactFlowJsonObject } from "@xyflow/react";
import { AxiosRequestConfig } from "axios";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface retrieveGetVerticesOrder {
  flowId: string;
  data?: ReactFlowJsonObject;
  stopNodeId?: string;
  startNodeId?: string;
}

interface retrieveGetVerticesOrderResponse {
  ids: string[];
  rund_id: string;
  vertices_to_run: string[];
}

// add types for error handling and success
export const usePostRetrieveVertexOrder: useMutationFunctionType<
  undefined,
  retrieveGetVerticesOrder,
  retrieveGetVerticesOrderResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const postRetrieveVertexOrder = async ({
    flowId,
    data: flow,
    startNodeId,
    stopNodeId,
  }: retrieveGetVerticesOrder): Promise<retrieveGetVerticesOrderResponse> => {
    // nodeId is optional and is a query parameter
    // if nodeId is not provided, the API will return all vertices
    const config: AxiosRequestConfig<any> = {};
    if (stopNodeId) {
      config["params"] = { stop_component_id: decodeURIComponent(stopNodeId) };
    } else if (startNodeId) {
      config["params"] = {
        start_component_id: decodeURIComponent(startNodeId),
      };
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
      `${getURL("BUILD")}/${flowId}/vertices`,
      data,
      config,
    );

    return response.data;
  };

  const mutation = mutate(
    ["usePostRetrieveVertexOrder"],
    postRetrieveVertexOrder,
    options,
  );

  return mutation;
};
