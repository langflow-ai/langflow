import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { isMockMemoriesEnabled, mockMemoriesApi } from "../../mocks/memories";
import type { MemoryInfo, UpdateMemoryParams } from "./types";

export const useUpdateMemory: useMutationFunctionType<
  undefined,
  UpdateMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateMemoryFn = async (
    params: UpdateMemoryParams,
  ): Promise<MemoryInfo> => {
    const { memoryId, ...patch } = params;

    const response = isMockMemoriesEnabled()
      ? { data: await mockMemoriesApi.update(memoryId, patch) }
      : await api.put<MemoryInfo>(`${getURL("MEMORIES")}/${memoryId}`, patch);

    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    queryClient.invalidateQueries({ queryKey: ["useGetMemory", memoryId] });
    return response.data;
  };

  const mutation: UseMutationResult<MemoryInfo, any, UpdateMemoryParams> =
    mutate(["useUpdateMemory"], updateMemoryFn, options);

  return mutation;
};
