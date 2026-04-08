import {
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { MemoryApiDTO, MemoryInfo, UpdateMemoryParams } from "./types";
import { mapMemoryApiToMemoryInfo } from "./mappers";
import { updateMemoryInMemoriesCache } from "./memories-cache-helpers";

export const useUpdateMemory: useMutationFunctionType<
  undefined,
  UpdateMemoryParams,
  MemoryInfo,
  unknown
> = (options?) => {
  const queryClient = useQueryClient();
  const typedOptions = options as
    | Omit<
        UseMutationOptions<MemoryInfo, unknown, UpdateMemoryParams, unknown>,
        "mutationFn" | "mutationKey"
      >
    | undefined;
  const { onSettled: userOnSettled, ...restOptions } = typedOptions ?? {};

  const updateMemoryFn = async (
    params: UpdateMemoryParams,
  ): Promise<MemoryInfo> => {
    const { memoryId, ...patch } = params;

    const response = await api.patch<MemoryApiDTO>(
      `${getURL("MEMORIES")}/${memoryId}`,
      patch,
    );

    const updated = mapMemoryApiToMemoryInfo(response.data);

    // Keep UI snappy: update caches directly instead of invalidating/refetching.
    queryClient.setQueryData(["useGetMemory", memoryId], updated);
    updateMemoryInMemoriesCache(queryClient, updated);

    return updated;
  };

  const mutation = useMutation<
    MemoryInfo,
    unknown,
    UpdateMemoryParams,
    unknown
  >({
    mutationKey: ["useUpdateMemory"],
    mutationFn: updateMemoryFn,
    ...restOptions,
    onSettled: (data, error, variables, onMutateResult, context) => {
      userOnSettled?.(data, error, variables, onMutateResult, context);
    },
    retry: restOptions.retry ?? 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  return mutation;
};
