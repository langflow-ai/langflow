import { useMemo } from "react";
import { useGetMemorySessionMessages } from "@/controllers/API/queries/memories/use-get-memory-session-messages";
import type {
  MemoryDocumentItem,
  MemorySessionInfo,
} from "@/controllers/API/queries/memories/types";

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
  } = useGetMemorySessionMessages(
    {
      memoryId: memoryId ?? "",
      sessionId: sessionId ?? "",
      size: DEFAULT_PAGE_SIZE,
    },
    {
      enabled: !!memoryId && !!sessionId,
    },
  );

  const docsData = useMemo(() => {
    const pages = memoryMessagesInfinite?.pages ?? [];

    const rawDocuments: MemoryDocumentItem[] = pages
      .flatMap((p) => p?.items ?? [])
      .map((m) => {
        const ingestionJobId = String(m?.ingestion_job_id ?? "");
        const ingestionTimestamp = String(m?.ingestion_timestamp ?? "");
        const timestamp = String(m?.timestamp ?? "");
        const sender = String(m?.sender ?? "");
        const sessionIdFromMessage = String(m?.session_id ?? "");
        const messageId =
          ingestionJobId || timestamp || sender
            ? [ingestionJobId, timestamp, sender].filter(Boolean).join(":")
            : "";

        return {
          message_id: messageId,
          session_id: sessionIdFromMessage,
          sender,
          content: String(m?.text ?? ""),
          timestamp,
          ...(ingestionJobId ? { ingestion_job_id: ingestionJobId } : {}),
          ...(ingestionTimestamp
            ? { ingestion_timestamp: ingestionTimestamp }
            : {}),
        };
      })
      .filter((d) => d.content);

    const sessionScopedDocuments = sessionId
      ? rawDocuments.filter((doc) => doc.session_id === sessionId)
      : rawDocuments;

    const sessions = Array.from(
      new Set(
        (memorySessions ?? [])
          .map((s) => s.session_id)
          .filter((sid): sid is string => !!sid),
      ),
    );

    const totalFromApi =
      memoryMessagesInfinite?.pages?.[0]?.total ??
      sessionScopedDocuments.length;

    return {
      documents: sessionScopedDocuments,
      total: totalFromApi,
      sessions,
    };
  }, [memoryMessagesInfinite, memorySessions, sessionId]);

  return {
    docsData,
    memoryMessagesLoading,
    fetchNextMessagesPage,
    hasNextMessagesPage,
    isFetchingNextMessagesPage,
  };
};
