import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemoryInfo } from "./use-get-memories";

interface UpdateMemoryKBParams {
  memoryId: string;
}

export const useUpdateMemoryKB: useMutationFunctionType<
  undefined,
  UpdateMemoryKBParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateMemoryKBFn = async (
    params: UpdateMemoryKBParams,
  ): Promise<MemoryInfo> => {
    const response = await api.post<MemoryInfo>(
      `${getURL("MEMORIES")}/${params.memoryId}/update`,
    );
    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<MemoryInfo, any, UpdateMemoryKBParams> =
    mutate(["useUpdateMemoryKB"], updateMemoryKBFn, options);

  return mutation;
};
