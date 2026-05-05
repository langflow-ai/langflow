import Loading from "@/components/ui/loading";
import CreateMemoryModal from "@/modals/createMemoryModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMemoriesData } from "./hooks/useMemoriesData";
import { NoMemorySelected } from "./components/NoMemorySelected";
import { MemoriesSidebar } from "./components/MemoriesSidebar";
import { MemoryDetails } from "./components/MemoryDetails";
import { MemoryDocumentPanel } from "./components/MemoryDocumentPanel";
import { MemoriesMainContentProps } from "./types";

export default function MemoriesMainContent({
  selectedMemoryId,
  onSelectMemory,
}: MemoriesMainContentProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowName = useFlowsManagerStore(
    (state) => state.currentFlow?.name,
  );

  const {
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
  } = useMemoriesData({
    currentFlowId,
    selectedMemoryId,
    onSelectMemory,
  });

  return (
    <div className="flex h-full w-full overflow-hidden bg-muted/30">
      <MemoriesSidebar
        memories={memories}
        filteredMemories={filteredMemories}
        memoriesSearch={memoriesSearch}
        setMemoriesSearch={setMemoriesSearch}
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
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            activeSearch={activeSearch}
            setActiveSearch={setActiveSearch}
            selectedSession={selectedSession}
            setSelectedSession={setSelectedSession}
            handleSearch={handleSearch}
            groupedBySession={groupedBySession}
            handleOpenDocumentPanel={handleOpenDocumentPanel}
            deleteMutation={deleteMutation}
            updateMemoryMutation={updateMemoryMutation}
            handleToggleActive={handleToggleActive}
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
          onSelectMemory?.(memoryId);
        }}
      />
    </div>
  );
}
