import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import useAlertStore from "@/stores/alertStore";
import { useGetMemories } from "@/controllers/API/queries/memories/use-get-memories";
import { useGetMemory } from "@/controllers/API/queries/memories/use-get-memory";
import { useDeleteMemory } from "@/controllers/API/queries/memories/use-delete-memory";
import { useUpdateMemory } from "@/controllers/API/queries/memories/use-update-memory";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { UseMemoriesDataProps } from "../types";
import type {
  MemoryDocumentItem,
  MemoryInfo,
} from "@/controllers/API/queries/memories/types";
import {
  FIXED_PREFILL_MESSAGES,
  type PrefillFlowMessage,
} from "./fixedPrefillMessages";

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
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
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
      refetchInterval: (query) => {
        const data = query.state.data as MemoryInfo | undefined;
        return data?.status === "generating" || data?.status === "updating"
          ? 2000
          : false;
      },
      retry: false,
    },
  );

  const { data: flowMessages = [] } = useQuery({
    queryKey: ["useGetFlowMessagesForMemoriesPrefill", currentFlowId],
    enabled: !!currentFlowId,
    queryFn: async () => {
      const res = await api.get<PrefillFlowMessage[]>(getURL("MESSAGES"), {
        params: { flow_id: currentFlowId },
      });
      return Array.isArray(res.data) ? res.data : [];
    },
    refetchOnWindowFocus: false,
    retry: false,
  });

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
    setActiveSearch("");
    setSearchQuery("");

    setAutoCaptureDraft(null);
    committedIsActiveRef.current = memory?.is_active ?? null;
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
    const memoryDocuments = Array.isArray((memory as any)?.documents)
      ? (((memory as any).documents as MemoryDocumentItem[]) ?? [])
      : null;

    const prefillMessages = FIXED_PREFILL_MESSAGES;

    const rawDocuments: MemoryDocumentItem[] =
      memoryDocuments && memoryDocuments.length > 0
        ? memoryDocuments
        : prefillMessages
            .filter((m) => m && typeof m === "object")
            .map((m) => ({
              message_id: String(m.id ?? ""),
              session_id: String(m.session_id ?? ""),
              sender: String(m.sender ?? ""),
              content: String(m.text ?? ""),
              timestamp: String(m.timestamp ?? ""),
            }))
            .filter((d) => d.message_id && d.content);

    const q = activeSearch.trim().toLowerCase();

    const filteredDocuments = !q
      ? rawDocuments
      : rawDocuments.filter((doc) => {
          const content = (doc.content ?? "").toLowerCase();
          const sender = (doc.sender ?? "").toLowerCase();
          const sessionId = (doc.session_id ?? "").toLowerCase();
          const messageId = (doc.message_id ?? "").toLowerCase();
          return (
            content.includes(q) ||
            sender.includes(q) ||
            sessionId.includes(q) ||
            messageId.includes(q)
          );
        });

    const sessions = Array.from(
      new Set(
        rawDocuments
          .map((d) => d.session_id)
          .filter((sid): sid is string => !!sid && sid !== "(no session)"),
      ),
    );

    return {
      documents: filteredDocuments,
      total: filteredDocuments.length,
      sessions,
    };
  }, [memory, flowMessages, activeSearch]);

  const docsLoading = isLoading;

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
    if (autoCaptureDraft === null) return memory;
    return { ...memory, is_active: autoCaptureDraft };
  }, [memory, autoCaptureDraft]);

  const handleToggleActive = (nextIsActive: boolean) => {
    if (!memory) return;
    if (committedIsActiveRef.current === nextIsActive) {
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
      if (committedIsActiveRef.current === nextIsActive) {
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

  const handleSearch = () => {
    setActiveSearch(searchQuery);
    setSelectedSession(null);
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
      if (selectedSession && sid !== selectedSession) continue;
      const list = map.get(sid) || [];
      list.push(doc);
      map.set(sid, list);
    }
    return map;
  }, [docsData, selectedSession]);

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
    searchQuery,
    setSearchQuery,
    activeSearch,
    setActiveSearch,
    selectedSession,
    setSelectedSession,
    handleSearch,
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
