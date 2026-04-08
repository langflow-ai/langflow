import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemorySessionInfo } from "./types";

export interface GetMemorySessionsParams {
  memoryId: string;
}

export const useGetMemorySessions: useQueryFunctionType<
  GetMemorySessionsParams,
  MemorySessionInfo[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getSessionsFn = async (): Promise<MemorySessionInfo[]> => {
    if (!params?.memoryId) {
      throw new Error("memoryId is required");
    }

    const { data } = await api.get<{ items: MemorySessionInfo[] }>(
      `${getURL("MEMORIES")}/${params.memoryId}/sessions`,
    );

    return Array.isArray(data.items) ? data.items : [];
  };

  const queryResult: UseQueryResult<MemorySessionInfo[], any> = query(
    ["useGetMemorySessions", params?.memoryId],
    getSessionsFn,
    {
      enabled: !!params?.memoryId,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
