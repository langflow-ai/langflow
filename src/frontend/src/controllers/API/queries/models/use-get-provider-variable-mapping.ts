import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type ProviderVariableMapping = Record<string, string>;

export const useGetProviderVariableMapping: useQueryFunctionType<
  undefined,
  ProviderVariableMapping
> = (options) => {
  const { query } = UseRequestProcessor();

  const getProviderVariableMappingFn =
    async (): Promise<ProviderVariableMapping> => {
      try {
        const url = `${getURL("MODELS")}/provider-variable-mapping`;
        const response = await api.get<ProviderVariableMapping>(url);
        return response.data;
      } catch (error) {
        console.error("Error fetching provider variable mapping:", error);
        return {};
      }
    };

  const queryResult = query(
    ["useGetProviderVariableMapping"],
    getProviderVariableMappingFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
      ...options,
    },
  );

  return queryResult;
};
