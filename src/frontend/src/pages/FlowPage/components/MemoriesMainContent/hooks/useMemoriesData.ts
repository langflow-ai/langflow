import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type {
  MemoryDocumentItem,
  MemoryInfo,
} from "@/controllers/API/queries/memories/types";
import { useDeleteMemory } from "@/controllers/API/queries/memories/use-delete-memory";
import { useGetMemories } from "@/controllers/API/queries/memories/use-get-memories";
import { useGetMemory } from "@/controllers/API/queries/memories/use-get-memory";
import { useUpdateMemory } from "@/controllers/API/queries/memories/use-update-memory";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { UseMemoriesDataProps } from "../types";
import { useAutoCaptureDebouncedToggle } from "./useAutoCaptureDebouncedToggle";
import { useMemoryDocuments } from "./useMemoryDocuments";
import { useMemorySessionResolver } from "./useMemorySessionResolver";

const EMPTY_MEMORIES: MemoryInfo[] = [];

export function useMemoriesData({
  currentFlowId,
  selectedMemoryId,
  onSelectMemory,
}: UseMemoriesDataProps) {
  const { t } = useTranslation();
  const { setErrorData, setSuccessData } = useAlertStore();

  const [memoriesSearch, setMemoriesSearch] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [documentPanelOpen, setDocumentPanelOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] =
    useState<MemoryDocumentItem | null>(null);

  const {
    data: memoriesInfinite,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch: refetchMemories,
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
    },
  );

  const {
    memorySessions,
    selectedSession,
    setSelectedSession,
    effectiveSessionId,
    refetchMemorySessions,
    fetchNextSessionsPage,
    hasNextSessionsPage,
    isFetchingNextSessionsPage,
  } = useMemorySessionResolver({ memoryId: selectedMemoryId });

  const deleteMutation = useDeleteMemory({
    onSuccess: () => {
      setSuccessData({ title: t("memory.deletedSuccess") });
      onSelectMemory?.(null);
    },
    onError: (error: unknown) =>
      setErrorData({
        title: t("memory.deleteError"),
        list: extractApiErrorMessages(error),
      }),
  });

  const updateMemoryMutation = useUpdateMemory();

  const { autoCaptureDraft, handleToggleActive } =
    useAutoCaptureDebouncedToggle({
      memory,
      updateMemoryMutation,
    });

  const {
    docsData,
    memoryMessagesLoading,
    fetchNextMessagesPage,
    hasNextMessagesPage,
    isFetchingNextMessagesPage,
    refetchMessages,
  } = useMemoryDocuments({
    memoryId: selectedMemoryId,
    sessionId: effectiveSessionId,
    memorySessions,
  });

  useEffect(() => {
    if (isError && selectedMemoryId) {
      onSelectMemory?.(null);
    }
  }, [isError, selectedMemoryId, onSelectMemory]);

  const docsLoading = isLoading || memoryMessagesLoading;

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

  const onRefresh = useCallback(async () => {
    await Promise.all([
      refetchMemories(),
      refetchMemorySessions(),
      refetchMessages(),
    ]);
  }, [refetchMemories, refetchMemorySessions, refetchMessages]);

  const handleOpenDocumentPanel = (doc: MemoryDocumentItem) => {
    setSelectedDocument(doc);
    setDocumentPanelOpen(true);
  };

  const groupedBySession = useMemo(() => {
    if (!docsData.documents) return new Map<string, MemoryDocumentItem[]>();
    const map = new Map<string, MemoryDocumentItem[]>();
    for (const doc of docsData.documents) {
      const sid = doc.session_id || "(no session)";
      const list = map.get(sid) || [];
      list.push(doc);
      map.set(sid, list);
    }
    return map;
  }, [docsData]);

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
    onRefresh,
    fetchNextSessionsPage,
    hasNextSessionsPage,
    isFetchingNextSessionsPage,
    createModalOpen,
    setCreateModalOpen,
  };
}
