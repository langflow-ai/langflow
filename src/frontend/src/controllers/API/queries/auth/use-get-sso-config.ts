import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SSOProvider {
  id: string;
  type: string;
  name: string;
  enabled: boolean;
}

export interface SSOConfigResponse {
  enabled: boolean;
  providers: SSOProvider[];
}

export const useGetSSOConfig: useQueryFunctionType<
  undefined,
  SSOConfigResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  async function getSSOConfigFn(): Promise<SSOConfigResponse> {
    try {
      const response = await api.get<SSOConfigResponse>(
        `${getURL("SSO_CONFIG")}`
      );
      return response.data;
    } catch (error) {
      // If SSO is not configured, return disabled state
      return { enabled: false, providers: [] };
    }
  }

  const queryResult: UseQueryResult<SSOConfigResponse> = query(
    ["useGetSSOConfig"],
    getSSOConfigFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    }
  );

  return queryResult;
};