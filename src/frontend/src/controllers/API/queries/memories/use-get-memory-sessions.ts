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

    const res = await api.get<MemorySessionInfo[]>(
      `${getURL("MEMORIES")}/${params.memoryId}/sessions`,
    );

    return Array.isArray(res.data) ? res.data : [];
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
