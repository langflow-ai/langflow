import {
  type InfiniteData,
  type UseInfiniteQueryOptions,
  type UseInfiniteQueryResult,
  useInfiniteQuery,
} from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  MEMORIES_PAGE_SIZE,
  MEMORIES_RETRY_MAX_ATTEMPTS,
  memoriesRetryDelay,
} from "./memoriesQueryConfig";
import type { MemorySessionInfo } from "./types";

export interface GetMemorySessionsParams {
  memoryId: string;
  size?: number;
}

export type GetMemorySessionsApiResponse = {
  items: MemorySessionInfo[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

type SessionsPage = GetMemorySessionsApiResponse;

const SESSIONS_INFINITE_QUERY_KEY = "useGetMemorySessionsInfinite";

type SessionsQueryKey = readonly [
  typeof SESSIONS_INFINITE_QUERY_KEY,
  string,
  number,
];

export const useGetMemorySessions = (
  params: GetMemorySessionsParams,
  options?: Omit<
    UseInfiniteQueryOptions<
      SessionsPage,
      unknown,
      InfiniteData<SessionsPage, number>,
      SessionsQueryKey,
      number
    >,
    "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
  >,
): UseInfiniteQueryResult<InfiniteData<SessionsPage, number>, unknown> => {
  const memoryId = params?.memoryId;
  const size = params?.size ?? MEMORIES_PAGE_SIZE;

  const getSessionsPage = async ({
    pageParam,
  }: {
    pageParam: number;
  }): Promise<SessionsPage> => {
    if (!memoryId) {
      throw new Error("memoryId is required");
    }

    const baseUrl = `${getURL("MEMORIES")}/${memoryId}/sessions`;
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set("page", String(pageParam));
    url.searchParams.set("size", String(size));

    const res = await api.get<GetMemorySessionsApiResponse>(url.toString());

    return {
      items: Array.isArray(res.data?.items) ? res.data.items : [],
      total: Number(res.data?.total ?? 0),
      page: Number(res.data?.page ?? pageParam),
      size: Number(res.data?.size ?? size),
      pages: Number(res.data?.pages ?? 1),
    };
  };

  return useInfiniteQuery<
    SessionsPage,
    unknown,
    InfiniteData<SessionsPage, number>,
    SessionsQueryKey,
    number
  >({
    queryKey: [SESSIONS_INFINITE_QUERY_KEY, memoryId, size] as const,
    queryFn: getSessionsPage,
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    refetchOnWindowFocus: false,
    retry: MEMORIES_RETRY_MAX_ATTEMPTS,
    retryDelay: memoriesRetryDelay,
    enabled: !!memoryId,
    ...(options ?? {}),
  });
};
