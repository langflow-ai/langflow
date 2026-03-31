import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AddMessagesToMemoryParams, MemoryApiDTO, MemoryInfo } from "./types";
import { mapMemoryApiToMemoryInfo } from "./mappers";

export const useAddMessagesToMemory: useMutationFunctionType<
  undefined,
  AddMessagesToMemoryParams,
  MemoryInfo
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addMessagesFn = async (
    params: AddMessagesToMemoryParams,
  ): Promise<MemoryInfo> => {
    if (!params?.memoryId) {
      throw new Error("addMessagesToMemory: missing memoryId");
    }
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
    any,
    AddMessagesToMemoryParams
  > = mutate(["useAddMessagesToMemory"], addMessagesFn, options);

  return mutation;
};
