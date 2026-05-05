import { formatDate } from "../helpers";
import { MemoryDetailsProps } from "../types";
import { MemoryDetailsHeader } from "./MemoryDetailsHeader";
import { MemoryKnowledgeBaseSection } from "./MemoryKnowledgeBaseSection";
import { SummaryCard } from "./SummaryCard";

export function MemoryDetails({
  memory,
  docsData,
  docsLoading,
  fetchNextMessagesPage,
  hasNextMessagesPage,
  isFetchingNextMessagesPage,
  selectedSession,
  setSelectedSession,
  groupedBySession,
  handleOpenDocumentPanel,
  deleteMutation,
  handleToggleActive,
  onRefresh,
  fetchNextSessionsPage,
  hasNextSessionsPage,
  isFetchingNextSessionsPage,
}: MemoryDetailsProps) {
  const pendingLabel =
    memory.batch_size > 1 ? "Pending (this batch)" : "Pending Messages";
  const pendingValue =
    memory.batch_size > 1
      ? `${memory.pending_messages_count}/${memory.batch_size}`
      : memory.pending_messages_count;

  return (
    <>
      <MemoryDetailsHeader
        memory={memory}
        sessions={docsData?.sessions}
        selectedSession={selectedSession}
        setSelectedSession={setSelectedSession}
        deleteMutation={deleteMutation}
        handleToggleActive={handleToggleActive}
        onRefresh={onRefresh}
        fetchNextSessionsPage={fetchNextSessionsPage}
        hasNextSessionsPage={hasNextSessionsPage}
        isFetchingNextSessionsPage={isFetchingNextSessionsPage}
      />

      <div className="flex flex-1 flex-col overflow-auto p-4">
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
          <SummaryCard
            label="Processed Messages"
            value={memory.total_messages_processed}
            icon="MessageSquare"
          />
          <SummaryCard label={pendingLabel} value={pendingValue} icon="Timer" />
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
          {memory.embedding_provider && (
            <>
              <span>&middot;</span>
              <span>
                <span className="font-medium text-foreground">Provider:</span>{" "}
                {memory.embedding_provider}
              </span>
            </>
          )}
          {memory.batch_size > 1 && (
            <>
              <span>&middot;</span>
              <span>
                <span className="font-medium text-foreground">
                  Messages per batch:
                </span>{" "}
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
          fetchNextMessagesPage={fetchNextMessagesPage}
          hasNextMessagesPage={hasNextMessagesPage}
          isFetchingNextMessagesPage={isFetchingNextMessagesPage}
          groupedBySession={groupedBySession}
          handleOpenDocumentPanel={handleOpenDocumentPanel}
        />
      </div>
    </>
  );
}
