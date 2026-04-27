import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { mapMemoryApiToMemoryInfo } from "./mappers";
import { memoriesRetryDelay } from "./memoriesQueryConfig";
import type {
  AddMessagesToMemoryParams,
  MemoryApiDTO,
  MemoryInfo,
} from "./types";
import { ensureRequiredParam } from "./validation";

export const useAddMessagesToMemory: useMutationFunctionType<
  undefined,
  AddMessagesToMemoryParams,
  MemoryInfo
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addMessagesFn = async (
    params: AddMessagesToMemoryParams,
  ): Promise<MemoryInfo> => {
    ensureRequiredParam(params?.memoryId, "memoryId");
    if (!Array.isArray(params.messageIds) || params.messageIds.length === 0) {
      throw new Error(
        "addMessagesToMemory: message_ids must be a non-empty array",
      );
    }
    const response = await api.post<MemoryApiDTO>(
      `${getURL("MEMORIES")}/${params.memoryId}/add-messages`,
      {
        message_ids: params.messageIds,
      },
    );

    queryClient.invalidateQueries({ queryKey: ["useGetMemoriesInfinite"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    return mapMemoryApiToMemoryInfo(response.data);
  };

  const mutation: UseMutationResult<
    MemoryInfo,
    Error,
    AddMessagesToMemoryParams
  > = mutate(["useAddMessagesToMemory"], addMessagesFn, {
    // POST is not safe to retry by default (risk of duplicates).
    retry: false,
    retryDelay: memoriesRetryDelay,
    ...options,
  });

  return mutation;
};
