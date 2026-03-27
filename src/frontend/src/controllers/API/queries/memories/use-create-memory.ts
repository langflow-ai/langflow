import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { isMockMemoriesEnabled, mockMemoriesApi } from "../../mocks/memories";
import type { CreateMemoryPayload, MemoryInfo } from "./types";

export const useCreateMemory: useMutationFunctionType<
  MemoryInfo,
  CreateMemoryPayload
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createMemoryFn = async (
    params: CreateMemoryPayload,
  ): Promise<MemoryInfo> => {
    const response = isMockMemoriesEnabled()
      ? { data: await mockMemoriesApi.create(params) }
      : await api.post<MemoryInfo>(`${getURL("MEMORIES")}/`, params);

    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    return response.data;
  };

  const mutation: UseMutationResult<MemoryInfo, any, CreateMemoryPayload> =
    mutate(["useCreateMemory"], createMemoryFn, options);

  return mutation;
};
