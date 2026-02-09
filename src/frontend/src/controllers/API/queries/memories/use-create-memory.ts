import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { MemoryInfo } from "./use-get-memories";

interface CreateMemoryParams {
  name: string;
  description?: string;
  flow_id: string;
  embedding_model: string;
  embedding_provider: string;
  is_active?: boolean;
}

export const useCreateMemory: useMutationFunctionType<
  undefined,
  CreateMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createMemoryFn = async (
    params: CreateMemoryParams,
  ): Promise<MemoryInfo> => {
    const response = await api.post<MemoryInfo>(
      `${getURL("MEMORIES")}/`,
      {
        name: params.name,
        description: params.description,
        flow_id: params.flow_id,
        embedding_model: params.embedding_model,
        embedding_provider: params.embedding_provider,
        is_active: params.is_active ?? false,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
    return response.data;
  };

  const mutation: UseMutationResult<MemoryInfo, any, CreateMemoryParams> =
    mutate(["useCreateMemory"], createMemoryFn, options);

  return mutation;
};
