import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { isMockMemoriesEnabled, mockMemoriesApi } from "../../mocks/memories";
import type { AddMessagesToMemoryParams, MemoryInfo } from "./types";

export const useAddMessagesToMemory: useMutationFunctionType<
  undefined,
  AddMessagesToMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addMessagesFn = async (
    params: AddMessagesToMemoryParams,
  ): Promise<MemoryInfo> => {
    if (!params?.memoryId) {
      throw new Error("addMessagesToMemory: missing memoryId");
    }
    if (!Array.isArray(params.message_ids) || params.message_ids.length === 0) {
      throw new Error(
        "addMessagesToMemory: message_ids must be a non-empty array",
      );
    }
    const response = isMockMemoriesEnabled()
      ? {
          data: await mockMemoriesApi.addMessages(
            params.memoryId,
            params.message_ids,
          ),
        }
      : await api.post<MemoryInfo>(
          `${getURL("MEMORIES")}/${params.memoryId}/add-messages`,
          {
            message_ids: params.message_ids,
          },
        );

    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<
    MemoryInfo,
    any,
    AddMessagesToMemoryParams
  > = mutate(["useAddMessagesToMemory"], addMessagesFn, options);

  return mutation;
};
