import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type TritonHealthKind = "live" | "ready";

interface GetTritonHealthParams {
  serverId: string;
  kind: TritonHealthKind;
}

export type GetTritonHealthResponse = {
  kind: TritonHealthKind;
  ok: boolean;
  status: number;
};

export const useGetTritonHealth: useQueryFunctionType<
  GetTritonHealthParams,
  GetTritonHealthResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<GetTritonHealthResponse> => {
    const { data } = await api.get<GetTritonHealthResponse>(
      `${getURL("TRITON_SERVERS")}/${params.serverId}/health/${params.kind}`,
    );
    return data;
  };

  return query(
    ["useGetTritonHealth", params.serverId, params.kind],
    responseFn,
    {
      ...options,
      enabled: (options?.enabled ?? true) && Boolean(params.serverId),
    },
  );
};
