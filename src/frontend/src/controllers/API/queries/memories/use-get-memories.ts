import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { isMockMemoriesEnabled, mockMemoriesApi } from "../../mocks/memories";
import type { GetMemoriesParams, MemoryInfo } from "./types";

export const useGetMemories: useQueryFunctionType<
  GetMemoriesParams,
  MemoryInfo[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getMemoriesFn = async (): Promise<MemoryInfo[]> => {
    if (isMockMemoriesEnabled()) {
      return await mockMemoriesApi.list(params?.flowId);
    }

    const baseUrl = getURL("MEMORIES");
    const url = new URL(baseUrl, window.location.origin);
    if (params?.flowId) {
      url.searchParams.set("flow_id", params.flowId);
    }
    const res = await api.get(url.toString());
    return res.data;
  };

  const queryResult: UseQueryResult<MemoryInfo[], any> = query(
    ["useGetMemories", params?.flowId],
    getMemoriesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
