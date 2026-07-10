import type { useQueryFunctionType } from "@/types/api";
import type { TritonServerMetadata } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTritonServerMetaParams {
  serverId: string;
}

export const useGetTritonServerMeta: useQueryFunctionType<
  GetTritonServerMetaParams,
  TritonServerMetadata
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<TritonServerMetadata> => {
    const { data } = await api.get<TritonServerMetadata>(
      `${getURL("TRITON_SERVERS")}/${params.serverId}/metadata`,
    );
    return data;
  };

  return query(["useGetTritonServerMeta", params.serverId], responseFn, {
    ...options,
    enabled: (options?.enabled ?? true) && Boolean(params.serverId),
  });
};
