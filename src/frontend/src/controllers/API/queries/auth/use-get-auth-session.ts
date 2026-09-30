import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SessionResponse {
  authenticated: boolean;
  user?: {
    id: string;
    username: string;
    is_active: boolean;
    is_superuser: boolean;
    [key: string]: any;
  };
  store_api_key?: string;
}

export const useGetAuthSession: useQueryFunctionType<
  undefined,
  SessionResponse
> = (options?) => {
  const { query } = UseRequestProcessor();

  async function getAuthSessionFn(): Promise<SessionResponse> {
    try {
      const response = await api.get<SessionResponse>(getURL("SESSION"));
      return response.data;
    } catch (error) {
      // If the endpoint fails, return unauthenticated
      console.error("Session validation error:", error);
      return { authenticated: false };
    }
  }

  const queryResult: UseQueryResult<SessionResponse> = query(
    ["useGetAuthSession"],
    getAuthSessionFn,
    {
      refetchOnWindowFocus: false,
      retry: false,
      ...options,
    },
  );

  return queryResult;
};
