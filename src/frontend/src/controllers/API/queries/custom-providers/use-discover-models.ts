import type { useQueryFunctionType } from "@/types/api";
import type { DiscoverModelsResponse } from "@/types/custom-providers";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UseDiscoverModelsParams {
  providerId: string;
}

export const useDiscoverModels: useQueryFunctionType<
  UseDiscoverModelsParams,
  DiscoverModelsResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const discoverModelsFn = async (): Promise<DiscoverModelsResponse> => {
    if (!params?.providerId) {
      throw new Error("providerId is required for model discovery");
    }
    const res = await api.get<DiscoverModelsResponse>(
      `${getURL("CUSTOM_PROVIDERS")}/${params.providerId}/discover-models`,
    );
    return res.data;
  };

  const queryResult = query(
    ["useDiscoverModels", params?.providerId],
    discoverModelsFn,
    {
      refetchOnWindowFocus: false,
      enabled: false,
      ...options,
    },
  );

  return queryResult;
};
