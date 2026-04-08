import {
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { DeleteMemoryParams } from "./types";
import { removeMemoryFromMemoriesCache } from "./memories-cache-helpers";

export const useDeleteMemory: useMutationFunctionType<
  undefined,
  DeleteMemoryParams,
  void,
  unknown
> = (options?) => {
  const queryClient = useQueryClient();
  const typedOptions = options as
    | Omit<
        UseMutationOptions<void, unknown, DeleteMemoryParams, unknown>,
        "mutationFn" | "mutationKey"
      >
    | undefined;
  const { onSettled: userOnSettled, ...restOptions } = typedOptions ?? {};

  const deleteMemoryFn = async (params: DeleteMemoryParams): Promise<void> => {
    await api.delete(`${getURL("MEMORIES")}/${params.memoryId}`);

    // Avoid refetching a resource that no longer exists.
    await queryClient.cancelQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    queryClient.removeQueries({ queryKey: ["useGetMemory", params.memoryId] });

    // Keep cached lists consistent without forcing a refetch.
    removeMemoryFromMemoriesCache(queryClient, params.memoryId);
  };

  const mutation = useMutation<void, unknown, DeleteMemoryParams, unknown>({
    mutationKey: ["useDeleteMemory"],
    mutationFn: deleteMemoryFn,
    ...restOptions,
    onSettled: (data, error, variables, onMutateResult, context) => {
      userOnSettled?.(data, error, variables, onMutateResult, context);
    },
    retry: restOptions.retry ?? 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  return mutation;
};
