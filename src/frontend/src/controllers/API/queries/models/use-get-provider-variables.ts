import { ProviderVariable } from "@/constants/providerConstants";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type ProviderVariablesMapping = Record<string, ProviderVariable[]>;

/**
 * Hook to fetch provider variables mapping from the API.
 * Returns a mapping of provider names to their required variables.
 *
 * Example response:
 * {
 *   "OpenAI": [{ variable_name: "API Key", variable_key: "OPENAI_API_KEY", ... }],
 *   "IBM WatsonX": [
 *     { variable_name: "API Key", variable_key: "WATSONX_APIKEY", ... },
 *     { variable_name: "Project ID", variable_key: "WATSONX_PROJECT_ID", ... },
 *     { variable_name: "URL", variable_key: "WATSONX_URL", ... }
 *   ]
 * }
 */
export const useGetProviderVariables: useQueryFunctionType<
  undefined,
  ProviderVariablesMapping
> = (_, options) => {
  const { query } = UseRequestProcessor();

  const getProviderVariablesFn =
    async (): Promise<ProviderVariablesMapping> => {
      try {
        const url = `${getURL("MODELS")}/provider-variable-mapping`;
        const response = await api.get<ProviderVariablesMapping>(url);
        return response.data;
      } catch (error) {
        console.error("Error fetching provider variables mapping:", error);
        return {};
      }
    };

  const queryResult = query(
    ["useGetProviderVariables"],
    getProviderVariablesFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 60, // 1 hour - this data rarely changes
      ...options,
    },
  );

  return queryResult;
};
