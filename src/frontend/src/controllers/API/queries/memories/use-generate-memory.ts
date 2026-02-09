import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemoryInfo } from "./use-get-memories";

interface GenerateMemoryParams {
  memoryId: string;
}

export const useGenerateMemory: useMutationFunctionType<
  undefined,
  GenerateMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const generateMemoryFn = async (
    params: GenerateMemoryParams,
  ): Promise<MemoryInfo> => {
    const response = await api.post<MemoryInfo>(
      `${getURL("MEMORIES")}/${params.memoryId}/generate`,
    );
    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<MemoryInfo, any, GenerateMemoryParams> =
    mutate(["useGenerateMemory"], generateMemoryFn, options);

  return mutation;
};
