import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelProviderInfo {
  provider: string;
  models: Array<{
    model_name: string;
    metadata: Record<string, any>;
  }>;
  is_enabled: boolean;
}

export interface ModelProviderWithStatus extends ModelProviderInfo {
  icon?: string;
  documentation_url?: string;
}

export interface GetModelProvidersParams {
  includeDeprecated?: boolean;
  includeUnsupported?: boolean;
}

export const useGetModelProviders: useQueryFunctionType<
  GetModelProvidersParams | undefined,
  ModelProviderWithStatus[]
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getModelProvidersFn = async (): Promise<ModelProviderWithStatus[]> => {
    try {
      // Build query params
      const queryParams = new URLSearchParams();
      if (params?.includeDeprecated) {
        queryParams.append("include_deprecated", "true");
      }
      if (params?.includeUnsupported) {
        queryParams.append("include_unsupported", "true");
      }

      const url = `${getURL("MODELS")}${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`;

      // Fetch the models with provider information including is_enabled status from server
      const response = await api.get<ModelProviderInfo[]>(url);
      const providersData = response.data;

      return providersData.map((providerInfo) => ({
        ...providerInfo,
      }));
    } catch (error) {
      console.error("Error fetching model providers:", error);
      return [];
    }
  };

  const queryResult = query(
    [
      "useGetModelProviders",
      params?.includeDeprecated,
      params?.includeUnsupported,
    ],
    getModelProvidersFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
      ...options,
    },
  );

  return queryResult;
};
