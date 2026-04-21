import {
  useInfiniteQuery,
  type InfiniteData,
  type UseInfiniteQueryOptions,
  type UseInfiniteQueryResult,
} from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { GetMemoriesApiResponse, GetMemoriesParams } from "./types";
import { mapGetMemoriesApiResponse } from "./mappers";
import {
  MEMORIES_PAGE_SIZE,
  MEMORIES_RETRY_BASE_DELAY_MS,
  MEMORIES_RETRY_MAX_ATTEMPTS,
  MEMORIES_RETRY_MAX_DELAY_MS,
} from "@/pages/FlowPage/components/MemoriesMainContent/MemoriesMainContent.constants";

type MemoriesPage = ReturnType<typeof mapGetMemoriesApiResponse>;

const MEMORIES_INFINITE_QUERY_KEY = "useGetMemoriesInfinite";

type MemoriesQueryKey = readonly [
  typeof MEMORIES_INFINITE_QUERY_KEY,
  string | undefined,
];

export const useGetMemories = (
  params: GetMemoriesParams,
  options?: Omit<
    UseInfiniteQueryOptions<
      MemoriesPage,
      unknown,
      InfiniteData<MemoriesPage, number>,
      MemoriesQueryKey,
      number
    >,
    "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
  >,
): UseInfiniteQueryResult<InfiniteData<MemoriesPage, number>, unknown> => {
  const flowId = params?.flowId;

  const getMemoriesPage = async ({
    pageParam,
  }: {
    pageParam: number;
  }): Promise<MemoriesPage> => {
    const baseUrl = getURL("MEMORIES");
    const url = new URL(baseUrl, window.location.origin);
    if (flowId) {
      url.searchParams.set("flow_id", flowId);
    }
    url.searchParams.set("page", String(pageParam));
    url.searchParams.set("size", String(MEMORIES_PAGE_SIZE));

    const res = await api.get<GetMemoriesApiResponse>(url.toString());
    return mapGetMemoriesApiResponse(res.data);
  };

  return useInfiniteQuery<
    MemoriesPage,
    unknown,
    InfiniteData<MemoriesPage, number>,
    MemoriesQueryKey,
    number
  >({
    queryKey: [MEMORIES_INFINITE_QUERY_KEY, flowId] as const,
    queryFn: getMemoriesPage,
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    refetchOnWindowFocus: false,
    retry: MEMORIES_RETRY_MAX_ATTEMPTS,
    retryDelay: (attemptIndex) =>
      Math.min(
        MEMORIES_RETRY_BASE_DELAY_MS * 2 ** attemptIndex,
        MEMORIES_RETRY_MAX_DELAY_MS,
      ),
    ...(options ?? {}),
  });
};
