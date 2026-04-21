import { useEffect, useMemo, useState } from "react";
import useAlertStore from "@/stores/alertStore";
import { useGetMemories } from "@/controllers/API/queries/memories/use-get-memories";
import { useGetMemory } from "@/controllers/API/queries/memories/use-get-memory";
import { useDeleteMemory } from "@/controllers/API/queries/memories/use-delete-memory";
import { useUpdateMemory } from "@/controllers/API/queries/memories/use-update-memory";
import { UseMemoriesDataProps } from "../types";
import type {
  MemoryDocumentItem,
  MemoryInfo,
} from "@/controllers/API/queries/memories/types";
import { useMemorySessionResolver } from "./useMemorySessionResolver";
import { useAutoCaptureDebouncedToggle } from "./useAutoCaptureDebouncedToggle";
import { useMemoryDocuments } from "./useMemoryDocuments";
import { AUTO_CAPTURE_DEBOUNCE_MS } from "../MemoriesMainContent.constants";
import { extractApiErrorMessages } from "@/utils/apiError";

const EMPTY_MEMORIES: MemoryInfo[] = [];

export function useMemoriesData({
  currentFlowId,
  selectedMemoryId,
  onSelectMemory,
}: UseMemoriesDataProps) {
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
      retry: false,
    },
  );

  const {
    memorySessions,
    selectedSession,
    setSelectedSession,
    effectiveSessionId,
  } = useMemorySessionResolver({ memoryId: selectedMemoryId });

  const deleteMutation = useDeleteMemory({
    onSuccess: () => {
      setSuccessData({ title: "Memory deleted" });
      onSelectMemory?.(null);
    },
    onError: (error: unknown) =>
      setErrorData({
        title: "Failed to delete memory",
        list: extractApiErrorMessages(error),
      }),
  });

  const updateMemoryMutation = useUpdateMemory({
    onError: (error: unknown) =>
      setErrorData({
        title: "Failed to update memory",
        list: extractApiErrorMessages(error),
      }),
  });

  const { autoCaptureDraft, handleToggleActive } =
    useAutoCaptureDebouncedToggle({
      memory,
      updateMemoryMutation,
      debounceMs: AUTO_CAPTURE_DEBOUNCE_MS,
    });

  const {
    docsData,
    memoryMessagesLoading,
    fetchNextMessagesPage,
    hasNextMessagesPage,
    isFetchingNextMessagesPage,
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
