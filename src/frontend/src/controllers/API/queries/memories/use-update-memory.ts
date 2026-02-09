import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemoryInfo } from "./use-get-memories";

interface UpdateMemoryParams {
  memoryId: string;
  name?: string;
  description?: string;
  is_active?: boolean;
}

export const useUpdateMemory: useMutationFunctionType<
  undefined,
  UpdateMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateMemoryFn = async (
    params: UpdateMemoryParams,
  ): Promise<MemoryInfo> => {
    const response = await api.put<MemoryInfo>(
      `${getURL("MEMORIES")}/${params.memoryId}`,
      {
        name: params.name,
        description: params.description,
        is_active: params.is_active,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<MemoryInfo, any, UpdateMemoryParams> =
    mutate(["useUpdateMemory"], updateMemoryFn, options);

  return mutation;
};
