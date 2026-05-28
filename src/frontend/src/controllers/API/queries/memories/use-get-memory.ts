import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { mapMemoryApiToMemoryInfo } from "./mappers";
import {
  MEMORIES_RETRY_MAX_ATTEMPTS,
  memoriesRetryDelay,
} from "./memoriesQueryConfig";
import type { GetMemoryParams, MemoryApiDTO, MemoryInfo } from "./types";
import { ensureRequiredParam } from "./validation";

export const useGetMemory: useQueryFunctionType<GetMemoryParams, MemoryInfo> = (
  params,
  options?,
) => {
  const { query } = UseRequestProcessor();

  const getMemoryFn = async (): Promise<MemoryInfo> => {
    ensureRequiredParam(params?.memoryId, "memoryId");

    const res = await api.get<MemoryApiDTO>(
      `${getURL("MEMORIES")}/${params.memoryId}`,
    );
    return mapMemoryApiToMemoryInfo(res.data);
  };

  const queryResult: UseQueryResult<MemoryInfo, Error> = query(
    ["useGetMemory", params?.memoryId],
    getMemoryFn,
    {
      enabled: !!params?.memoryId,
      refetchOnWindowFocus: false,
      retry: MEMORIES_RETRY_MAX_ATTEMPTS,
      retryDelay: memoriesRetryDelay,
      ...options,
    },
  );

  return queryResult;
};
