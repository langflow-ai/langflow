import { useMemo } from "react";
import type {
  MemoryDocumentItem,
  MemorySessionInfo,
} from "@/controllers/API/queries/memories/types";
import { useGetMemoryMessages } from "@/controllers/API/queries/memories/use-get-memory-messages";

type UseMemoryDocumentsArgs = {
  memoryId?: string | null;
  sessionId: string | null;
  memorySessions: MemorySessionInfo[];
};

const DEFAULT_PAGE_SIZE = 50;

export const useMemoryDocuments = ({
  memoryId,
  sessionId,
  memorySessions,
}: UseMemoryDocumentsArgs) => {
  const {
    data: memoryMessagesInfinite,
    isLoading: memoryMessagesLoading,
    fetchNextPage: fetchNextMessagesPage,
    hasNextPage: hasNextMessagesPage,
    isFetchingNextPage: isFetchingNextMessagesPage,
    refetch: refetchMessages,
  } = useGetMemoryMessages(
    {
      memoryId: memoryId ?? "",
      sessionId: sessionId ?? null,
      size: DEFAULT_PAGE_SIZE,
    },
    {
      enabled: !!memoryId,
    },
  );

  const docsData = useMemo(() => {
    const pages = memoryMessagesInfinite?.pages ?? [];

    const rawDocuments: MemoryDocumentItem[] = pages
      .flatMap((p) => p?.items ?? [])
      .map((m, idx) => {
        const ingestionJobId = String(m?.job_id ?? "");
        const ingestionTimestamp = String(m?.ingestion_timestamp ?? "");
        const timestamp = String(m?.timestamp ?? "");
        const sender = String(m?.sender ?? "");
        const sessionIdFromMessage = String(m?.session_id ?? "");
        // Include idx as a tiebreaker so messages sharing sender/timestamp/job are distinct.
        const messageId = [
          sessionIdFromMessage,
          ingestionJobId,
          timestamp,
          sender,
          String(idx),
        ]
          .filter(Boolean)
          .join(":");

        return {
          message_id: messageId,
          session_id: sessionIdFromMessage,
          sender,
          content: String(m?.text ?? ""),
          timestamp,
          ...(ingestionJobId ? { job_id: ingestionJobId } : {}),
          ...(ingestionTimestamp
            ? { ingestion_timestamp: ingestionTimestamp }
            : {}),
        };
      })
      .filter((d) => d.content);

    const sessions = Array.from(
      new Set(
        (memorySessions ?? [])
          .map((s) => s.session_id)
          .filter((sid): sid is string => !!sid),
      ),
    );

    const totalFromApi =
      memoryMessagesInfinite?.pages?.[0]?.total ?? rawDocuments.length;

    return {
      documents: rawDocuments,
      total: totalFromApi,
      sessions,
    };
  }, [memoryMessagesInfinite, memorySessions]);

  return {
    docsData,
    memoryMessagesLoading,
    fetchNextMessagesPage,
    hasNextMessagesPage,
    isFetchingNextMessagesPage,
    refetchMessages,
  };
};
