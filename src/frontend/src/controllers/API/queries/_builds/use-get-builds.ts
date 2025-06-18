import useFlowStore from "@/stores/flowStore";
import { FlowPoolType } from "@/types/zustand/flow";
import { keepPreviousData } from "@tanstack/react-query";
import { AxiosResponse } from "axios";
import { useParams } from "react-router-dom";
import { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface BuildsQueryParams {
  flowId?: string;
}

export const useGetBuildsQuery: useQueryFunctionType<
  BuildsQueryParams,
  AxiosResponse<{ vertex_builds: FlowPoolType }>
> = (params) => {
  const { query } = UseRequestProcessor();
  const { id: routeFlowId } = useParams();

  const setFlowPool = useFlowStore((state) => state.setFlowPool);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const responseFn = async () => {
    const config = {};
    config["params"] = {
      flow_id:
        !params.flowId || params.flowId === "" ? routeFlowId : params.flowId,
    };

    const response = await api.get<any>(`${getURL("BUILDS")}`, config);

    if (currentFlow) {
      const flowPool = response.data.vertex_builds;
      setFlowPool(flowPool);
    }

    return response;
  };

  const queryResult = query(
    ["useGetBuildsQuery", { key: params.flowId }],
    responseFn,
    {
      placeholderData: keepPreviousData,
      refetchOnWindowFocus: false,
      retry: 0,
      retryDelay: 0,
    },
  );

  return queryResult;
};
