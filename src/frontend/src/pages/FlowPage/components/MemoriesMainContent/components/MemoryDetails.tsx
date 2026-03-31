import { SummaryCard } from "./SummaryCard";
import { formatDate } from "../helpers";
import { MemoryDetailsProps } from "../types";
import { MemoryDetailsHeader } from "./MemoryDetailsHeader";
import { MemoryKnowledgeBaseSection } from "./MemoryKnowledgeBaseSection";

export function MemoryDetails({
  memory,
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
  handleOpenDocumentPanel,
  deleteMutation,
  handleToggleActive,
}: MemoryDetailsProps) {

  return (
    <>
      <MemoryDetailsHeader
        memory={memory}
        deleteMutation={deleteMutation}
        handleToggleActive={handleToggleActive}
      />

      <div className="flex flex-1 flex-col overflow-auto p-4">
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <SummaryCard
            label="Messages Processed"
            value={memory.total_messages_processed}
            icon="MessageSquare"
          />
          <SummaryCard
            label="Total Chunks"
            value={memory.total_chunks}
            icon="Layers"
          />
          <SummaryCard
            label="Sessions Captured"
            value={memory.sessions_count}
            icon="Users"
          />
          <SummaryCard
            label="Pending Messages"
            value={
              memory.batch_size > 1
                ? `${memory.pending_messages_count}/${memory.batch_size}`
                : memory.pending_messages_count
            }
            icon="Timer"
          />
          <SummaryCard
            label="Last Generated"
            value={formatDate(memory.last_generated_at)}
            icon="Clock"
          />
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <span>
            <span className="font-medium text-foreground">Model:</span>{" "}
            {memory.embedding_model}
          </span>
          <span>&middot;</span>
          <span>
            <span className="font-medium text-foreground">Provider:</span>{" "}
            {memory.embedding_provider}
          </span>
          {memory.batch_size > 1 && (
            <>
              <span>&middot;</span>
              <span>
                <span className="font-medium text-foreground">Batch Size:</span>{" "}
                {memory.batch_size}
              </span>
            </>
          )}
          {memory.preprocessing_enabled && (
            <>
              <span>&middot;</span>
              <span>
                <span className="font-medium text-foreground">
                  Preprocessing:
                </span>{" "}
                enabled
              </span>
            </>
          )}
        </div>

        <MemoryKnowledgeBaseSection
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
          totalChunks={memory.total_chunks}
        />
      </div>
    </>
  );
}
