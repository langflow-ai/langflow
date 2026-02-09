import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemoryInfo } from "./use-get-memories";

interface AddMessagesToMemoryParams {
  memoryId: string;
  message_ids: string[];
}

export const useAddMessagesToMemory: useMutationFunctionType<
  undefined,
  AddMessagesToMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const addMessagesToMemoryFn = async (
    params: AddMessagesToMemoryParams,
  ): Promise<MemoryInfo> => {
    const response = await api.post<MemoryInfo>(
      `${getURL("MEMORIES")}/${params.memoryId}/add-messages`,
      { message_ids: params.message_ids },
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
  > = mutate(["useAddMessagesToMemory"], addMessagesToMemoryFn, options);

  return mutation;
};
