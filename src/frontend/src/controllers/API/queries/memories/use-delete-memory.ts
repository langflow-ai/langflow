import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteMemoryParams {
  memoryId: string;
}

export const useDeleteMemory: useMutationFunctionType<
  undefined,
  DeleteMemoryParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteMemoryFn = async (
    params: DeleteMemoryParams,
  ): Promise<void> => {
    await api.delete(`${getURL("MEMORIES")}/${params.memoryId}`);
    queryClient.invalidateQueries({ queryKey: ["useGetMemories"] });
  };

  const mutation: UseMutationResult<void, any, DeleteMemoryParams> = mutate(
    ["useDeleteMemory"],
    deleteMemoryFn,
    options,
  );

  return mutation;
};
