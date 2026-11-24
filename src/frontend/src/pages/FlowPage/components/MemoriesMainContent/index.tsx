import { useCallback, useEffect, useState } from "react";
import Loading from "@/components/ui/loading";
import CreateMemoryModal from "@/modals/createMemoryModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { MemoriesSidebar } from "./components/MemoriesSidebar";
import { MemoryDetails } from "./components/MemoryDetails";
import { MemoryDocumentPanel } from "./components/MemoryDocumentPanel";
import { NoMemorySelected } from "./components/NoMemorySelected";
import { useMemoriesData } from "./hooks/useMemoriesData";

export default function MemoriesMainContent() {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowName = useFlowsManagerStore(
    (state) => state.currentFlow?.name,
  );

  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);
  const onSelectMemory = useCallback((id: string | null) => {
    setSelectedMemoryId(id);
  }, []);

  useEffect(() => {
    setSelectedMemoryId(null);
  }, [currentFlowId]);

  const {
    filteredMemories,
    memoriesSearch,
    setMemoriesSearch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    memory,
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
    handleToggleActive,
    onRefresh,
    fetchNextSessionsPage,
    hasNextSessionsPage,
    isFetchingNextSessionsPage,
    createModalOpen,
    setCreateModalOpen,
  } = useMemoriesData({
    currentFlowId,
    selectedMemoryId,
    onSelectMemory,
  });

  return (
    <div className="flex h-full w-full overflow-hidden bg-muted/30">
      <MemoriesSidebar
        filteredMemories={filteredMemories}
        memoriesSearch={memoriesSearch}
        setMemoriesSearch={setMemoriesSearch}
        fetchNextPage={fetchNextPage}
        hasNextPage={hasNextPage}
        isFetchingNextPage={isFetchingNextPage}
        selectedMemoryId={selectedMemoryId}
        currentFlowId={currentFlowId ?? undefined}
        onSelectMemory={onSelectMemory}
        onCreateMemory={() => setCreateModalOpen(true)}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        {!selectedMemoryId ? (
          <NoMemorySelected />
        ) : isLoading ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading size={64} className="text-primary" />
          </div>
        ) : !memory ? (
          <NoMemorySelected />
        ) : (
          <MemoryDetails
            memory={memory}
            docsData={docsData}
            docsLoading={docsLoading}
            fetchNextMessagesPage={fetchNextMessagesPage}
            hasNextMessagesPage={hasNextMessagesPage}
            isFetchingNextMessagesPage={isFetchingNextMessagesPage}
            selectedSession={selectedSession}
            setSelectedSession={setSelectedSession}
            groupedBySession={groupedBySession}
            handleOpenDocumentPanel={handleOpenDocumentPanel}
            deleteMutation={deleteMutation}
            handleToggleActive={handleToggleActive}
            onRefresh={onRefresh}
            fetchNextSessionsPage={fetchNextSessionsPage}
            hasNextSessionsPage={hasNextSessionsPage}
            isFetchingNextSessionsPage={isFetchingNextSessionsPage}
          />
        )}
      </div>

      <MemoryDocumentPanel
        open={documentPanelOpen}
        onOpenChange={(open) => {
          setDocumentPanelOpen(open);
          if (!open) setSelectedDocument(null);
        }}
        selectedDocument={selectedDocument}
      />

      <CreateMemoryModal
        open={createModalOpen}
        setOpen={setCreateModalOpen}
        flowId={currentFlowId ?? ""}
        flowName={currentFlowName ?? ""}
        onSuccess={(memoryId) => {
          onSelectMemory(memoryId);
        }}
      />
    </div>
  );
}
