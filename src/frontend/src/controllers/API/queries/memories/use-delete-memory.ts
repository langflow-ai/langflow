import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { isMockMemoriesEnabled, mockMemoriesApi } from "../../mocks/memories";
import type { DeleteMemoryParams } from "./types";

export const useDeleteMemory: useMutationFunctionType<
  undefined,
  DeleteMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteMemoryFn = async (params: DeleteMemoryParams): Promise<void> => {
    if (isMockMemoriesEnabled()) {
      await mockMemoriesApi.remove(params.memoryId);
    } else {
      await api.delete(`${getURL("MEMORIES")}/${params.memoryId}`);
    }

    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
  };

  const mutation: UseMutationResult<void, any, DeleteMemoryParams> = mutate(
    ["useDeleteMemory"],
    deleteMemoryFn,
    options,
  );

  return mutation;
};
