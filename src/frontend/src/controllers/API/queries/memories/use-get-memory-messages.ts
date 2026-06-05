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

export type MemoryMessageApiItem = {
  timestamp: string;
  sender: string;
  sender_name?: string;
  job_id?: string;
  ingestion_timestamp?: string;
  session_id: string;
  text: string;
  content_blocks?: unknown[];
};

export type GetMemoryMessagesApiResponse = {
  items: MemoryMessageApiItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

export type GetMemoryMessagesParams = {
  memoryId: string;
  sessionId?: string | null;
  size?: number;
};

type MessagesPage = GetMemoryMessagesApiResponse;

const MESSAGES_INFINITE_QUERY_KEY = "useGetMemoryMessagesInfinite";
const ALL_SESSIONS_KEY = "__all__";

type MessagesQueryKey = readonly [
  typeof MESSAGES_INFINITE_QUERY_KEY,
  string,
  string,
  number,
];

export const useGetMemoryMessages = (
  params: GetMemoryMessagesParams,
  options?: Omit<
    UseInfiniteQueryOptions<
      MessagesPage,
      unknown,
      InfiniteData<MessagesPage, number>,
      MessagesQueryKey,
      number
    >,
    "queryKey" | "queryFn" | "initialPageParam" | "getNextPageParam"
  >,
): UseInfiniteQueryResult<InfiniteData<MessagesPage, number>, unknown> => {
  const memoryId = params?.memoryId;
  const sessionId = params?.sessionId ?? null;
  const size = params?.size ?? MEMORIES_PAGE_SIZE;

  const getMessagesPage = async ({
    pageParam,
  }: {
    pageParam: number;
  }): Promise<MessagesPage> => {
    if (!memoryId) {
      throw new Error("memoryId is required");
    }

    const baseUrl = `${getURL("MEMORIES")}/${memoryId}/messages`;
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set("page", String(pageParam));
    url.searchParams.set("size", String(size));
    if (sessionId) {
      url.searchParams.set("session_id", sessionId);
    }

    const res = await api.get<GetMemoryMessagesApiResponse>(url.toString());

    return {
      items: Array.isArray(res.data?.items) ? res.data.items : [],
      total: Number(res.data?.total ?? 0),
      page: Number(res.data?.page ?? pageParam),
      size: Number(res.data?.size ?? size),
      pages: Number(res.data?.pages ?? 1),
    };
  };

  return useInfiniteQuery<
    MessagesPage,
    unknown,
    InfiniteData<MessagesPage, number>,
    MessagesQueryKey,
    number
  >({
    queryKey: [
      MESSAGES_INFINITE_QUERY_KEY,
      memoryId,
      sessionId ?? ALL_SESSIONS_KEY,
      size,
    ] as const,
    queryFn: getMessagesPage,
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
