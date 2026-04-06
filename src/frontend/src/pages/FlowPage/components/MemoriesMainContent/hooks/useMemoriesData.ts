import { useEffect, useMemo, useRef, useState } from "react";
import useAlertStore from "@/stores/alertStore";
import { useGetMemories } from "@/controllers/API/queries/memories/use-get-memories";
import { useGetMemory } from "@/controllers/API/queries/memories/use-get-memory";
import { useGetMemorySessions } from "@/controllers/API/queries/memories/use-get-memory-sessions";
import { useDeleteMemory } from "@/controllers/API/queries/memories/use-delete-memory";
import { useUpdateMemory } from "@/controllers/API/queries/memories/use-update-memory";
import { useGetMemorySessionMessages } from "@/controllers/API/queries/memories/use-get-memory-session-messages";
import { UseMemoriesDataProps } from "../types";
import type {
  MemoryDocumentItem,
  MemoryInfo,
  MemorySessionInfo,
} from "@/controllers/API/queries/memories/types";

const EMPTY_MEMORIES: MemoryInfo[] = [];

export function useMemoriesData({
  currentFlowId,
  selectedMemoryId,
  onSelectMemory,
}: UseMemoriesDataProps) {
  const { setErrorData, setSuccessData } = useAlertStore();

  const AUTO_CAPTURE_DEBOUNCE_MS = 300;
  const autoCaptureTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const committedIsActiveRef = useRef<boolean | null>(null);

  const [memoriesSearch, setMemoriesSearch] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [documentPanelOpen, setDocumentPanelOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] =
    useState<MemoryDocumentItem | null>(null);
  const [autoCaptureDraft, setAutoCaptureDraft] = useState<boolean | null>(
    null,
  );

  const {
    data: memoriesInfinite,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useGetMemories(
    { flowId: currentFlowId ?? undefined },
    { enabled: !!currentFlowId },
  );

  const memories = useMemo(() => {
    const pages = memoriesInfinite?.pages ?? [];
    if (pages.length === 0) return EMPTY_MEMORIES;
    const items = pages.flatMap((p) => p?.items ?? []);
    return items.length ? items : EMPTY_MEMORIES;
  }, [memoriesInfinite]);

  useEffect(() => {
    if (memories.length === 0) {
      if (selectedMemoryId) onSelectMemory?.(null);
      return;
    }

    if (!selectedMemoryId || !memories.some((m) => m.id === selectedMemoryId)) {
      const nextId = memories[0].id;
      if (selectedMemoryId !== nextId) {
        onSelectMemory?.(nextId);
      }
    }
  }, [memories, selectedMemoryId, onSelectMemory]);

  useEffect(() => {
    setSelectedSession(null);
    setSelectedDocument(null);
    setDocumentPanelOpen(false);
  }, [selectedMemoryId]);

  const filteredMemories = useMemo(() => {
    const q = memoriesSearch.trim().toLowerCase();
    if (!q) return memories;
    return memories.filter((m) => {
      const name = (m.name ?? "").toLowerCase();
      return name.includes(q);
    });
  }, [memories, memoriesSearch]);

  const {
    data: memory,
    isLoading,
    isError,
  } = useGetMemory(
    { memoryId: selectedMemoryId ?? "" },
    {
      enabled: !!selectedMemoryId,
      retry: false,
    },
  );

  const { data: memorySessions = [] } = useGetMemorySessions(
    { memoryId: selectedMemoryId ?? "" },
    {
      enabled: !!selectedMemoryId,
      retry: false,
    },
  );

  const resolveDefaultSessionId = (sessions: MemorySessionInfo[]) => {
    if (!sessions.length) return null;
    const toTime = (value: string | null | undefined) =>
      value ? new Date(value).getTime() : 0;

    const sorted = [...sessions].sort((a, b) => {
      const timeDiff = toTime(b.last_sync_at) - toTime(a.last_sync_at);
      if (timeDiff !== 0) return timeDiff;
      const pendingDiff = (b.pending_count ?? 0) - (a.pending_count ?? 0);
      if (pendingDiff !== 0) return pendingDiff;
      return (a.session_id ?? "").localeCompare(b.session_id ?? "");
    });
    return sorted[0]?.session_id ?? null;
  };

  const effectiveSessionId = useMemo(() => {
    const candidate = selectedSession?.trim();
    if (candidate) {
      const exists = memorySessions.some((s) => s.session_id === candidate);
      if (exists) return candidate;
    }

    const fallback = resolveDefaultSessionId(memorySessions);
    return fallback && fallback.trim() ? fallback : null;
  }, [selectedSession, memorySessions]);

  const {
    data: memoryMessagesInfinite,
    isLoading: memoryMessagesLoading,
    fetchNextPage: fetchNextMessagesPage,
    hasNextPage: hasNextMessagesPage,
    isFetchingNextPage: isFetchingNextMessagesPage,
  } = useGetMemorySessionMessages(
    {
      memoryId: selectedMemoryId ?? "",
      sessionId: effectiveSessionId ?? "",
      size: 50,
    },
    {
      enabled: !!selectedMemoryId && !!effectiveSessionId,
    },
  );

  useEffect(() => {
    if (!selectedMemoryId) return;
    if (!memorySessions.length) return;

    const sessionIds = memorySessions
      .map((s) => s.session_id)
      .filter((sid): sid is string => !!sid);
    if (!sessionIds.length) return;

    setSelectedSession((prev) => {
      if (prev && sessionIds.includes(prev)) return prev;
      return resolveDefaultSessionId(memorySessions);
    });
  }, [selectedMemoryId, memorySessions]);

  useEffect(() => {
    if (isError && selectedMemoryId) {
      onSelectMemory?.(null);
    }
  }, [isError, selectedMemoryId, onSelectMemory]);

  useEffect(() => {
    committedIsActiveRef.current = memory?.is_active ?? null;
  }, [memory?.is_active]);

  useEffect(() => {
    setSelectedSession(null);
    setSelectedDocument(null);
    setDocumentPanelOpen(false);

    setAutoCaptureDraft(null);
    committedIsActiveRef.current = null;
    if (autoCaptureTimerRef.current) {
      clearTimeout(autoCaptureTimerRef.current);
      autoCaptureTimerRef.current = null;
    }
  }, [selectedMemoryId]);

  useEffect(() => {
    return () => {
      if (autoCaptureTimerRef.current) {
        clearTimeout(autoCaptureTimerRef.current);
        autoCaptureTimerRef.current = null;
      }
    };
  }, []);

  const docsData = useMemo(() => {
    const pages = memoryMessagesInfinite?.pages ?? [];
    const rawDocuments: MemoryDocumentItem[] = pages
      .flatMap((p) => p?.items ?? [])
      .map((m) => {
        const ingestionJobId = String(m?.ingestion_job_id ?? "");
        const timestamp = String(m?.timestamp ?? "");
        const sender = String(m?.sender ?? "");
        const sessionId = String(m?.session_id ?? "");
        const messageId =
          ingestionJobId || timestamp || sender
            ? [ingestionJobId, timestamp, sender].filter(Boolean).join(":")
            : "";

        return {
          message_id: messageId,
          session_id: sessionId,
          sender,
          content: String(m?.text ?? ""),
          timestamp,
        };
      })
      .filter((d) => d.content);

    const sessionScopedDocuments = effectiveSessionId
      ? rawDocuments.filter((doc) => doc.session_id === effectiveSessionId)
      : rawDocuments;

    const sessionsFromApi = Array.from(
      new Set(
        (memorySessions ?? [])
          .map((s) => s.session_id)
          .filter((sid): sid is string => !!sid && sid !== "(no session)"),
      ),
    );

    const sessions = sessionsFromApi;

    const totalFromApi =
      memoryMessagesInfinite?.pages?.[0]?.total ?? sessionScopedDocuments.length;

    return {
      documents: sessionScopedDocuments,
      total: totalFromApi,
      sessions,
    };
  }, [
    memoryMessagesInfinite,
    memorySessions,
    effectiveSessionId,
  ]);

  const docsLoading = isLoading || memoryMessagesLoading;

  const deleteMutation = useDeleteMemory({
    onSuccess: () => {
      setSuccessData({ title: "Memory deleted" });
      onSelectMemory?.(null);
    },
    onError: (error: any) =>
      setErrorData({
        title: "Failed to delete memory",
        list: [error?.response?.data?.detail || error?.message],
      }),
  });

  const updateMemoryMutation = useUpdateMemory({
    onSuccess: () => {
      setAutoCaptureDraft(null);
    },
    onError: (error: any) =>
      setErrorData({
        title: "Failed to update memory",
        list: [error?.response?.data?.detail || error?.message],
      }),
  });

  const resolvedMemory = useMemo(() => {
    if (!memory) return memory;

    const selectedStats = effectiveSessionId
      ? (memorySessions ?? []).find((s) => s.session_id === effectiveSessionId)
      : null;

    const nextMemory: MemoryInfo = {
      ...memory,
      ...(autoCaptureDraft === null ? {} : { is_active: autoCaptureDraft }),
      ...(selectedStats
        ? {
            total_messages_processed: selectedStats.total_processed ?? 0,
            pending_messages_count: selectedStats.pending_count ?? 0,
            last_generated_at: selectedStats.last_sync_at ?? undefined,
          }
        : {}),
    };

    return nextMemory;
  }, [memory, autoCaptureDraft, effectiveSessionId, memorySessions]);

  const handleToggleActive = (nextIsActive: boolean) => {
    if (!memory) return;
    const committedIsActive = committedIsActiveRef.current ?? memory.is_active;
    if (committedIsActive === nextIsActive) {
      if (autoCaptureTimerRef.current) {
        clearTimeout(autoCaptureTimerRef.current);
        autoCaptureTimerRef.current = null;
      }
      setAutoCaptureDraft(null);
      return;
    }

    setAutoCaptureDraft(nextIsActive);

    if (autoCaptureTimerRef.current) {
      clearTimeout(autoCaptureTimerRef.current);
      autoCaptureTimerRef.current = null;
    }

    autoCaptureTimerRef.current = setTimeout(() => {
      // If the committed value already matches, skip a no-op update.
      if ((committedIsActiveRef.current ?? memory.is_active) === nextIsActive) {
        setAutoCaptureDraft(null);
        autoCaptureTimerRef.current = null;
        return;
      }

      updateMemoryMutation.mutate({
        memoryId: memory.id,
        auto_capture: nextIsActive,
      });
      autoCaptureTimerRef.current = null;
    }, AUTO_CAPTURE_DEBOUNCE_MS);
  };

  const handleOpenDocumentPanel = (doc: MemoryDocumentItem) => {
    setSelectedDocument(doc);
    setDocumentPanelOpen(true);
  };

  const groupedBySession = useMemo(() => {
    if (!docsData.documents) return new Map<string, MemoryDocumentItem[]>();
    const map = new Map<string, MemoryDocumentItem[]>();
    for (const doc of docsData.documents) {
      const sid = doc.session_id || "(no session)";
      if (effectiveSessionId && sid !== effectiveSessionId) continue;
      const list = map.get(sid) || [];
      list.push(doc);
      map.set(sid, list);
    }
    return map;
  }, [docsData, effectiveSessionId]);

  return {
    memories,
    filteredMemories,
    memoriesSearch,
    setMemoriesSearch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    memory: resolvedMemory,
    isLoading,
    docsData,
    docsLoading,
    fetchNextMessagesPage,
    hasNextMessagesPage,
    isFetchingNextMessagesPage,
    selectedSession,
    setSelectedSession,
    groupedBySession,
    documentPanelOpen,
    setDocumentPanelOpen,
    selectedDocument,
    setSelectedDocument,
    handleOpenDocumentPanel,
    deleteMutation,
    updateMemoryMutation,
    handleToggleActive,
    createModalOpen,
    setCreateModalOpen,
  };
}
