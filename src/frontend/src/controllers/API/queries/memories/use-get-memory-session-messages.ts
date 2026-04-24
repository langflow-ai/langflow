import {
  useInfiniteQuery,
  type InfiniteData,
  type UseInfiniteQueryOptions,
  type UseInfiniteQueryResult,
} from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { MEMORIES_PAGE_SIZE } from "@/pages/FlowPage/components/MemoriesMainContent/MemoriesMainContent.constants";

export type MemorySessionMessageApiItem = {
  timestamp: string;
  sender: string;
  sender_name?: string;
  ingestion_job_id?: string;
  ingestion_timestamp?: string;
  session_id: string;
  text: string;
  content_blocks?: unknown[];
};

export type GetMemorySessionMessagesApiResponse = {
  items: MemorySessionMessageApiItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
};

export type GetMemorySessionMessagesParams = {
  memoryId: string;
  sessionId: string;
  size?: number;
};

type MessagesPage = GetMemorySessionMessagesApiResponse;

const MESSAGES_INFINITE_QUERY_KEY = "useGetMemorySessionMessagesInfinite";

type MessagesQueryKey = readonly [
  typeof MESSAGES_INFINITE_QUERY_KEY,
  string,
  string,
  number,
];

export const useGetMemorySessionMessages = (
  params: GetMemorySessionMessagesParams,
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
  const sessionId = params?.sessionId;
  const size = params?.size ?? MEMORIES_PAGE_SIZE;

  const getMessagesPage = async ({
    pageParam,
  }: {
    pageParam: number;
  }): Promise<MessagesPage> => {
    if (!memoryId) {
      throw new Error("memoryId is required");
    }
    if (!sessionId) {
      throw new Error("sessionId is required");
    }

    const baseUrl = `${getURL("MEMORIES")}/${memoryId}/sessions/${sessionId}/messages`;
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set("page", String(pageParam));
    url.searchParams.set("size", String(size));

    const res = await api.get<GetMemorySessionMessagesApiResponse>(
      url.toString(),
    );

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
    queryKey: [MESSAGES_INFINITE_QUERY_KEY, memoryId, sessionId, size] as const,
    queryFn: getMessagesPage,
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.pages ? lastPage.page + 1 : undefined,
    refetchOnWindowFocus: false,
    retry: false,
    enabled: !!memoryId && !!sessionId,
    ...(options ?? {}),
  });
};
