import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowPoolType } from "@/types/zustand/flow";
import { cleanEdges } from "@/utils/reactflowUtils";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { keepPreviousData } from "@tanstack/react-query";
import { AxiosResponse } from "axios";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface BuildsQueryParams {
  flowId?: string;
  nodeId?: string;
}

export const useGetBuildsQuery: useQueryFunctionType<
  BuildsQueryParams,
  AxiosResponse<{ vertex_builds: FlowPoolType }>
> = ({}) => {
  const { query } = UseRequestProcessor();

  const setFlowPool = useFlowStore((state) => state.setFlowPool);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);

  const getBuildsFn = async (
    params: BuildsQueryParams,
  ): Promise<AxiosResponse<{ vertex_builds: FlowPoolType }>> => {
    const config = {};
    config["params"] = { flow_id: params.flowId };

    if (params.nodeId) {
      config["params"] = { nodeId: params.nodeId };
    }

    return await api.get<any>(`${getURL("BUILDS")}`, config);
  };

  const responseFn = async () => {
    const response = await getBuildsFn({
      flowId: currentFlow!.id,
    });

    if (currentFlow) {
      const flowPool = response.data.vertex_builds;
      setFlowPool(flowPool);
    }

    return response;
  };

  const queryResult = query(["useGetBuildsQuery"], responseFn, {
    placeholderData: keepPreviousData,
  });

  return queryResult;
};
