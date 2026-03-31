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

  const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

  const getStringId = (value: unknown): string | undefined => {
    if (!isRecord(value)) return undefined;
    const id = value.id;
    return typeof id === "string" ? id : undefined;
  };

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
    queryClient.setQueriesData(
      { queryKey: ["useGetMemoriesInfinite"] },
      (old: unknown) => {
        if (!isRecord(old)) return old;

        // InfiniteQuery shape: { pages: [{ items: [...] }, ...], pageParams: [...] }
        if (Array.isArray(old.pages)) {
          const pages = old.pages;
          const nextPages = pages.map((page) => {
            if (!isRecord(page)) return page;
            const items = page.items;
            if (!Array.isArray(items)) return page;

            const nextItems = items.map((item) => {
              if (getStringId(item) !== updated.id) return item;
              if (!isRecord(item)) return item;
              return { ...item, ...updated };
            });

            return { ...page, items: nextItems };
          });

          return { ...old, pages: nextPages };
        }

        // Legacy/non-infinite shape: { items: [...] }
        if (!Array.isArray(old.items)) return old;
        const items = old.items;

        const nextItems = items.map((item) => {
          if (getStringId(item) !== updated.id) return item;
          if (!isRecord(item)) return item;
          return { ...item, ...updated };
        });

        return { ...old, items: nextItems };
      },
    );

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
      queryClient.invalidateQueries({ queryKey: ["useUpdateMemory"] });
      userOnSettled?.(data, error, variables, onMutateResult, context);
    },
    retry: restOptions.retry ?? 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  return mutation;
};
