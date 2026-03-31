import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { GetMemoryParams, MemoryApiDTO, MemoryInfo } from "./types";
import { mapMemoryApiToMemoryInfo } from "./mappers";

export const useGetMemory: useQueryFunctionType<GetMemoryParams, MemoryInfo> = (
  params,
  options?,
) => {
  const { query } = UseRequestProcessor();

  const getMemoryFn = async (): Promise<MemoryInfo> => {
    if (!params?.memoryId) {
      throw new Error("memoryId is required");
    }

    const res = await api.get<MemoryApiDTO>(
      `${getURL("MEMORIES")}/${params.memoryId}`,
    );
    return mapMemoryApiToMemoryInfo(res.data);
  };

  const queryResult: UseQueryResult<MemoryInfo, any> = query(
    ["useGetMemory", params?.memoryId],
    getMemoryFn,
    {
      enabled: !!params?.memoryId,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
