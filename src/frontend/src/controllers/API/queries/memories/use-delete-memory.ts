import {
  type UseMutationOptions,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { removeMemoryFromMemoriesCache } from "./memories-cache-helpers";
import { memoriesRetryDelay } from "./memoriesQueryConfig";
import type { DeleteMemoryParams } from "./types";

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
  const {
    onSuccess: userOnSuccess,
    onSettled: userOnSettled,
    ...restOptions
  } = typedOptions ?? {};

  const deleteMemoryFn = async (params: DeleteMemoryParams): Promise<void> => {
    await api.delete(`${getURL("MEMORIES")}/${params.memoryId}`);
  };

  const mutation = useMutation<void, unknown, DeleteMemoryParams, unknown>({
    mutationKey: ["useDeleteMemory"],
    mutationFn: deleteMemoryFn,
    ...restOptions,
    onSuccess: (data, variables, onMutateResult, context) => {
      // Cancel in-flight fetches for the deleted resource so a 404 doesn't land after removal.
      queryClient.cancelQueries({
        queryKey: ["useGetMemory", variables.memoryId],
      });
      queryClient.removeQueries({
        queryKey: ["useGetMemory", variables.memoryId],
      });

      // Keep cached lists consistent without forcing a refetch.
      removeMemoryFromMemoriesCache(queryClient, variables.memoryId);

      userOnSuccess?.(data, variables, onMutateResult, context);
    },
    onSettled: (data, error, variables, onMutateResult, context) => {
      userOnSettled?.(data, error, variables, onMutateResult, context);
    },
    // DELETE is not safe to retry by default (may produce confusing 404s).
    retry: false,
    retryDelay: memoriesRetryDelay,
  });

  return mutation;
};
