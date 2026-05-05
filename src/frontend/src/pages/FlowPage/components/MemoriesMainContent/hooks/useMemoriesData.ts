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

export function useMemoriesData({
  currentFlowId,
  selectedMemoryId,
  onSelectMemory,
}: UseMemoriesDataProps) {
  const { setErrorData, setSuccessData } = useAlertStore();

  const [memoriesSearch, setMemoriesSearch] = useState("");
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [documentPanelOpen, setDocumentPanelOpen] = useState(false);
  const [selectedDocument, setSelectedDocument] =
    useState<MemoryDocumentItem | null>(null);

  const { data: memories } = useGetMemories(
    { flowId: currentFlowId ?? undefined },
    { enabled: !!currentFlowId },
  );

  useEffect(() => {
    if (!memories || memories.length === 0) {
      if (selectedMemoryId) onSelectMemory?.(null);
      return;
    }

    if (!selectedMemoryId || !memories.some((m) => m.id === selectedMemoryId)) {
      onSelectMemory?.(memories[0].id);
    }
  }, [memories, selectedMemoryId, onSelectMemory]);

  useEffect(() => {
    setSelectedSession(null);
    setSelectedDocument(null);
    setDocumentPanelOpen(false);
  }, [selectedMemoryId]);

  const filteredMemories = useMemo(() => {
    const list = memories ?? [];
    const q = memoriesSearch.trim().toLowerCase();
    if (!q) return list;
    return list.filter((m) => {
      const name = (m.name ?? "").toLowerCase();
      const description = (m.description ?? "").toLowerCase();
      return name.includes(q) || description.includes(q);
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

  useEffect(() => {
    if (isError && selectedMemoryId) {
      onSelectMemory?.(null);
    }
  }, [isError, selectedMemoryId, onSelectMemory]);

  const docsData = useMemo(() => {
    const rawDocuments = memory?.documents ?? [];
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

    const sessions =
      memory?.document_sessions ??
      Array.from(
        new Set(rawDocuments.map((doc) => doc.session_id).filter(Boolean)),
      );

    return {
      documents: filteredDocuments,
      total: filteredDocuments.length,
      sessions,
    };
  }, [memory, activeSearch]);

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
    onError: (error: any) =>
      setErrorData({
        title: "Failed to update memory",
        list: [error?.response?.data?.detail || error?.message],
      }),
  });

  const handleToggleActive = () => {
    if (!memory) return;
    updateMemoryMutation.mutate({
      memoryId: memory.id,
      is_active: !memory.is_active,
    });
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
    memory,
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
