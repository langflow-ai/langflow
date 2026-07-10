import type { useQueryFunctionType } from "@/types/api";
import type {
  TritonModelConfigResponse,
  TritonModelListResponse,
} from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTritonModelsParams {
  serverId: string;
}

export const useGetTritonModels: useQueryFunctionType<
  GetTritonModelsParams,
  TritonModelListResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<TritonModelListResponse> => {
    const { data } = await api.get<TritonModelListResponse>(
      `${getURL("TRITON_SERVERS")}/${params.serverId}/models`,
    );
    return data ?? { models: [] };
  };

  return query(["useGetTritonModels", params.serverId], responseFn, {
    ...options,
    enabled: (options?.enabled ?? true) && Boolean(params.serverId),
  });
};

interface GetTritonModelConfigParams {
  serverId: string;
  modelName: string;
}

export const useGetTritonModelConfig: useQueryFunctionType<
  GetTritonModelConfigParams,
  TritonModelConfigResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async (): Promise<TritonModelConfigResponse> => {
    const { data } = await api.get<TritonModelConfigResponse>(
      `${getURL("TRITON_SERVERS")}/${params.serverId}/models/${params.modelName}/config`,
    );
    return data;
  };

  return query(
    ["useGetTritonModelConfig", params.serverId, params.modelName],
    responseFn,
    {
      ...options,
      enabled:
        (options?.enabled ?? true) &&
        Boolean(params.serverId) &&
        Boolean(params.modelName),
    },
  );
};
