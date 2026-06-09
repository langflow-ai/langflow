import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/utils/utils";
import { formatDate } from "../helpers";
import { ALL_SESSIONS_VALUE } from "../hooks/useMemorySessionResolver";
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
  const [configOpen, setConfigOpen] = useState(false);
  const { t } = useTranslation();
  const isAllSessions =
    !selectedSession || selectedSession === ALL_SESSIONS_VALUE;
  const pendingLabel =
    memory.batch_size > 1
      ? t("memory.pendingThisBatch")
      : t("memory.pendingMessages");
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
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <SummaryCard
            label={t("memory.processedMessages")}
            value={isAllSessions ? "—" : memory.total_messages_processed}
            icon="MessageSquare"
          />
          <SummaryCard
            label={pendingLabel}
            value={isAllSessions ? "—" : pendingValue}
            icon="Timer"
          />
          <SummaryCard
            label={t("memory.lastGenerated")}
            value={isAllSessions ? "—" : formatDate(memory.last_generated_at)}
            icon="Clock"
          />
          <Popover open={configOpen} onOpenChange={setConfigOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="flex w-full cursor-pointer items-center gap-3 rounded-lg border border-border bg-background p-3 text-left transition-colors hover:bg-muted/50"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted">
                  <IconComponent
                    name="Settings2"
                    className="h-4 w-4 text-muted-foreground"
                  />
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="text-xs text-muted-foreground">
                    {t("memory.configLabel")}
                  </span>
                  <span className="truncate text-sm font-medium">
                    {memory.embedding_model}
                  </span>
                </div>
                <IconComponent
                  name="ChevronDown"
                  className={cn(
                    "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                    configOpen && "rotate-180",
                  )}
                />
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-72 p-4">
              <div className="flex flex-col gap-3 text-xs">
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium text-muted-foreground">
                    {t("memory.modelLabel")}
                  </span>
                  <span className="text-foreground">
                    {memory.embedding_model}
                  </span>
                </div>
                {memory.embedding_provider && (
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium text-muted-foreground">
                      {t("memory.providerLabel")}
                    </span>
                    <span className="text-foreground">
                      {memory.embedding_provider}
                    </span>
                  </div>
                )}
                {memory.batch_size > 1 && (
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium text-muted-foreground">
                      {t("memory.messagesPerBatch")}
                    </span>
                    <span className="text-foreground">{memory.batch_size}</span>
                  </div>
                )}
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium text-muted-foreground">
                    {t("memory.preprocessing")}
                  </span>
                  <span className="text-foreground">
                    {memory.preprocessing_enabled
                      ? t("memory.enabled")
                      : t("memory.disabled")}
                  </span>
                </div>
                {memory.preprocessing_enabled && memory.preprocessing_model && (
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium text-muted-foreground">
                      {t("memory.preprocessingModel")}
                    </span>
                    <span className="text-foreground">
                      {memory.preprocessing_model}
                    </span>
                  </div>
                )}
                {memory.preprocessing_enabled && (
                  <div className="flex flex-col gap-0.5 border-t border-border pt-3">
                    <span className="font-medium text-muted-foreground">
                      {t("memory.preprocessingInstructions")}
                    </span>
                    <p className="leading-relaxed text-foreground">
                      {memory.preproc_instructions}
                    </p>
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>
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
