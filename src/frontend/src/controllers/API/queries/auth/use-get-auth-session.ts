import type { UseQueryResult } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { isExternalAuthMaintenanceRefusal } from "../../helpers/maintenance";
import {
  getRetryAfterMs,
  UseRequestProcessor,
} from "../../services/request-processor";

export interface SessionResponse {
  authenticated: boolean;
  user?: {
    id: string;
    username: string;
    is_active: boolean;
    is_superuser: boolean;
    [key: string]: unknown;
  };
  store_api_key?: string;
}

type PausedSession = {
  authenticated?: never;
  externalAuthenticationPaused: true;
  retryAfterMs: number;
};

export type AuthSessionState = SessionResponse | PausedSession;

const SESSION_QUERY_KEY = ["useGetAuthSession"];

function isPausedSession(value: unknown): value is PausedSession {
  return (
    value !== null &&
    typeof value === "object" &&
    "externalAuthenticationPaused" in value &&
    value.externalAuthenticationPaused === true
  );
}

export const useGetAuthSession = (
  options?: Parameters<useQueryFunctionType<undefined, AuthSessionState>>[0],
): UseQueryResult<AuthSessionState> & {
  isExternalAuthenticationPaused: boolean;
} => {
  const { query, queryClient } = UseRequestProcessor();

  async function getAuthSessionFn(): Promise<AuthSessionState> {
    try {
      const response = await api.get<SessionResponse>(getURL("SESSION"));
      return response.data;
    } catch (error) {
      if (isExternalAuthMaintenanceRefusal(error)) {
        return {
          externalAuthenticationPaused: true,
          retryAfterMs: getRetryAfterMs(error) ?? 1000,
        };
      }
      const authenticationRejected =
        isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0);
      if (
        isPausedSession(queryClient.getQueryData(SESSION_QUERY_KEY)) &&
        !authenticationRejected
      ) {
        throw error;
      }
      // If the endpoint fails, return unauthenticated
      console.error("Session validation error:", error);
      return { authenticated: false };
    }
  }

  const queryResult: UseQueryResult<AuthSessionState> = query(
    SESSION_QUERY_KEY,
    getAuthSessionFn,
    {
      refetchOnWindowFocus: false,
      retry: false,
      refetchInterval: (query) =>
        isPausedSession(query.state.data)
          ? query.state.data.retryAfterMs
          : false,
      ...options,
    },
  );

  return {
    ...queryResult,
    // Cached uncertainty survives pending retries, transport failures, and
    // new observers until a response can establish the session's validity.
    isExternalAuthenticationPaused: isPausedSession(queryResult.data),
  };
};
