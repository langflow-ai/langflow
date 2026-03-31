import {
  useMutation,
  useQueryClient,
  type UseMutationOptions,
  type UseMutationResult,
} from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { CreateMemoryPayload, MemoryApiDTO, MemoryInfo } from "./types";
import { mapMemoryApiToMemoryInfo } from "./mappers";

export const useCreateMemory: useMutationFunctionType<
  undefined,
  CreateMemoryPayload,
  MemoryInfo
> = (options?) => {
  const queryClient = useQueryClient();
  const typedOptions = options as
    | Omit<
        UseMutationOptions<MemoryInfo, any, CreateMemoryPayload, unknown>,
        "mutationFn" | "mutationKey"
      >
    | undefined;
  const { onSettled: userOnSettled, onSuccess: userOnSuccess, ...restOptions } =
    typedOptions ?? {};

  const createMemoryFn = async (
    params: CreateMemoryPayload,
  ): Promise<MemoryInfo> => {
    const response = await api.post<MemoryApiDTO>(
      `${getURL("MEMORIES")}/`,
      params,
    );
    return mapMemoryApiToMemoryInfo(response.data);
  };

  const mutation: UseMutationResult<MemoryInfo, any, CreateMemoryPayload> =
    useMutation<MemoryInfo, any, CreateMemoryPayload>({
      mutationKey: ["useCreateMemory"],
      mutationFn: createMemoryFn,
      ...restOptions,
      onSuccess: (data, variables, onMutateResult, context) => {
        // Seed the details cache for immediate render.
        queryClient.setQueryData(["useGetMemory", data.id], data);

        // Patch any cached lists without forcing a refetch.
        const queries = queryClient.getQueriesData({
          queryKey: ["useGetMemoriesInfinite"],
        });

        for (const [queryKey, old] of queries) {
          const flowIdInKey = Array.isArray(queryKey)
            ? (queryKey[1] as string | undefined)
            : undefined;

          // Update only the relevant flow list, and any unfiltered list.
          if (flowIdInKey !== undefined && flowIdInKey !== data.flow_id) {
            continue;
          }

          if (!old || typeof old !== "object") continue;
          const anyOld = old as any;

          // InfiniteQuery shape: { pages: [{ items: [...] }, ...], pageParams: [...] }
          if (Array.isArray(anyOld.pages)) {
            const pages = anyOld.pages as any[];
            if (pages.length === 0) continue;

            const alreadyPresent = pages.some((p) =>
              Array.isArray(p?.items)
                ? p.items.some((item: any) => item?.id === data.id)
                : false,
            );
            if (alreadyPresent) continue;

            const firstPage = pages[0];
            if (!firstPage || typeof firstPage !== "object" || !Array.isArray(firstPage.items)) {
              continue;
            }

            const nextFirstItems = [data, ...firstPage.items];
            const nextFirstTotal =
              typeof firstPage.total === "number" ? firstPage.total + 1 : firstPage.total;

            const nextPages = [
              { ...firstPage, items: nextFirstItems, total: nextFirstTotal },
              ...pages.slice(1).map((p) => {
                if (!p || typeof p !== "object") return p;
                const nextTotal =
                  typeof p.total === "number" ? p.total + 1 : p.total;
                return { ...p, total: nextTotal };
              }),
            ];

            queryClient.setQueryData(queryKey, { ...anyOld, pages: nextPages });
            continue;
          }

          // Legacy/non-infinite shape: { items: [...] }
          if (!Array.isArray(anyOld.items)) continue;

          const alreadyPresent = anyOld.items.some((item: any) => item?.id === data.id);
          if (alreadyPresent) continue;

          const nextItems = [data, ...anyOld.items];
          const nextTotal =
            typeof anyOld.total === "number" ? anyOld.total + 1 : anyOld.total;

          queryClient.setQueryData(queryKey, {
            ...anyOld,
            items: nextItems,
            total: nextTotal,
          });
        }

        userOnSuccess?.(data, variables, onMutateResult, context);
      },
      onSettled: (data, error, variables, onMutateResult, context) => {
        // Keep parity with other mutations that used to invalidate onSettled.
        queryClient.invalidateQueries({ queryKey: ["useCreateMemory"] });
        userOnSettled?.(data, error, variables, onMutateResult, context);
      },
      retry: restOptions.retry ?? 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    });

  return mutation;
};
