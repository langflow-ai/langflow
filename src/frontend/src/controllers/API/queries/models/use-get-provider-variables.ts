import { ProviderVariable } from "@/constants/providerConstants";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
  providerScopeQueryKey,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

export type ProviderVariablesMapping = Record<string, ProviderVariable[]>;

const PROVIDER_POLICY_STALE_TIME_MS = 30_000;

export const getProviderVariablesQueryKey = (params?: ProviderScopeParams) =>
  ["useGetProviderVariables", ...providerScopeQueryKey(params)] as const;

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
  ProviderScopeParams | undefined,
  ProviderVariablesMapping
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getProviderVariablesFn =
    async (): Promise<ProviderVariablesMapping> => {
      try {
        const queryParams = new URLSearchParams();
        appendProviderScope(queryParams, params);
        const url = `${getURL("MODELS")}/provider-variable-mapping${
          queryParams.toString() ? `?${queryParams.toString()}` : ""
        }`;
        const response = await api.get<ProviderVariablesMapping>(url);
        return response.data;
      } catch (error) {
        console.error("Error fetching provider variables mapping:", error);
        throw error;
      }
    };

  const queryResult = query(
    getProviderVariablesQueryKey(params),
    getProviderVariablesFn,
    {
      refetchOnWindowFocus: true,
      staleTime: PROVIDER_POLICY_STALE_TIME_MS,
      ...options,
    },
  );

  return queryResult;
};
