import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemoryInfo } from "./use-get-memories";

interface GetMemoryParams {
  memoryId: string;
}

export const useGetMemory: useQueryFunctionType<
  GetMemoryParams,
  MemoryInfo
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getMemoryFn = async (): Promise<MemoryInfo> => {
    const res = await api.get(
      `${getURL("MEMORIES")}/${params?.memoryId}`,
    );
    return res.data;
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
