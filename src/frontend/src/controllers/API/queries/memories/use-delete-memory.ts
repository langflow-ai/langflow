import {
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
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
  const { onSettled: userOnSettled, ...restOptions } = typedOptions ?? {};

  const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

  const getStringId = (value: unknown): string | undefined => {
    if (!isRecord(value)) return undefined;
    const id = value.id;
    return typeof id === "string" ? id : undefined;
  };

  const deleteMemoryFn = async (params: DeleteMemoryParams): Promise<void> => {
    await api.delete(`${getURL("MEMORIES")}/${params.memoryId}`);

    // Avoid refetching a resource that no longer exists.
    await queryClient.cancelQueries({
      queryKey: ["useGetMemory", params.memoryId],
    });
    queryClient.removeQueries({ queryKey: ["useGetMemory", params.memoryId] });

    // Keep cached lists consistent without forcing a refetch.
    queryClient.setQueriesData(
      { queryKey: ["useGetMemoriesInfinite"] },
      (old: unknown) => {
        if (!isRecord(old)) return old;

        // InfiniteQuery shape: { pages: [{ items: [...] }, ...], pageParams: [...] }
        if (Array.isArray(old.pages)) {
          const pages = old.pages;
          let removedCount = 0;
          const nextPages = pages.map((page) => {
            if (!isRecord(page)) return page;

            const items = page.items;
            if (!Array.isArray(items)) return page;

            const beforeLen = items.length;
            const nextItems = items.filter(
              (item) => getStringId(item) !== params.memoryId,
            );
            const removedInPage = beforeLen - nextItems.length;
            removedCount += removedInPage;

            const total = page.total;
            const nextTotal =
              typeof total === "number"
                ? Math.max(0, total - removedInPage)
                : total;

            return { ...page, items: nextItems, total: nextTotal };
          });

          // If nothing was removed, return original cache object.
          if (removedCount === 0) return old;
          return { ...old, pages: nextPages };
        }

        // Legacy/non-infinite shape: { items: [...] }
        if (!Array.isArray(old.items)) return old;

        const items = old.items;

        const nextItems = items.filter(
          (item) => getStringId(item) !== params.memoryId,
        );

        const removedCount = items.length - nextItems.length;
        const nextTotal =
          typeof old.total === "number"
            ? Math.max(0, old.total - removedCount)
            : old.total;

        return { ...old, items: nextItems, total: nextTotal };
      },
    );
  };

  const mutation = useMutation<void, unknown, DeleteMemoryParams, unknown>({
    mutationKey: ["useDeleteMemory"],
    mutationFn: deleteMemoryFn,
    ...restOptions,
    onSettled: (data, error, variables, onMutateResult, context) => {
      queryClient.invalidateQueries({ queryKey: ["useDeleteMemory"] });
      userOnSettled?.(data, error, variables, onMutateResult, context);
    },
    retry: restOptions.retry ?? 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  return mutation;
};
