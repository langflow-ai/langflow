import type { useQueryFunctionType } from "@/types/api";
import type { TritonMetricsResponse } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTritonMetricsParams {
  serverId: string;
  refetchInterval?: number;
}

export const useGetTritonMetrics: useQueryFunctionType<
  GetTritonMetricsParams,
  TritonMetricsResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<TritonMetricsResponse> => {
    const { data } = await api.get<TritonMetricsResponse>(
      `${getURL("TRITON_SERVERS")}/${params.serverId}/metrics`,
    );
    return data ?? { model_stats: [] };
  };

  return query(["useGetTritonMetrics", params.serverId], responseFn, {
    ...options,
    enabled: (options?.enabled ?? true) && Boolean(params.serverId),
    refetchInterval: options?.refetchInterval ?? params.refetchInterval,
  });
};
