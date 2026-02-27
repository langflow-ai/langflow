import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import DeleteConfirmDialog from "./components/DeleteConfirmDialog";
import HistoryListItem from "./components/HistoryListItem";
import PruneWarningDialog from "./components/PruneWarningDialog";
import RestoreConfirmDialog from "./components/RestoreConfirmDialog";
import { CURRENT_DRAFT_ID } from "./constants";
import type { FlowHistorySidebarContentProps } from "./types";
import { useFlowHistorySidebar } from "./use-flow-history-sidebar";

export default function FlowHistorySidebarContent({
  flowId,
}: FlowHistorySidebarContentProps) {
  const {
    selectedId,
    pruneWarning,
    setPruneWarning,
    restoreDialogEntry,
    setRestoreDialogEntry,
    deleteDialogEntry,
    setDeleteDialogEntry,
    animatingId,
    isRestoring,
    history,
    maxEntries,
    isLoading,
    isListError,
    isEntryError,
    processedPreview,
    isCreating,
    isDeleting,
    isViewingDraft,
    handleSelectEntry,
    doCreateSnapshot,
    handleRestore,
    handleExport,
    handleDelete,
  } = useFlowHistorySidebar(flowId);

  return (
    <>
      <div className="flex h-full flex-col">
        <SidebarGroupLabel className="flex items-center justify-between px-3 pt-3">
          <span>Version History</span>
          {history && history.length > 0 && (
            <span className="font-normal text-foreground/50">
              {history.length}
              {maxEntries ? ` / ${maxEntries}` : ""}
            </span>
          )}
        </SidebarGroupLabel>

        {isEntryError && (
          <div className="flex items-center gap-2 bg-destructive/10 px-2 py-2">
            <span className="text-xs text-destructive">
              Failed to load version data
            </span>
          </div>
        )}

        {processedPreview?.error && (
          <div className="flex items-center gap-2 bg-destructive/10 px-2 py-2">
            <span className="text-xs text-destructive">
              This version's data could not be rendered for preview
            </span>
          </div>
        )}

        <div className="flex-1">
          <SidebarMenu className="gap-0">
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={isViewingDraft}
                onClick={() => handleSelectEntry(CURRENT_DRAFT_ID)}
                className="h-auto flex flex-col items-start p-3 border-t border-b border-border rounded-none"
              >
                <div className="flex flex-col items-start">
                  <span className="font-medium text-sm pb-1">Current</span>
                  <span className="text-xs text-muted-foreground">
                    Working version
                  </span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>

            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <ForwardedIconComponent
                  name="Loader2"
                  className="h-5 w-5 animate-spin text-muted-foreground"
                />
              </div>
            )}
            {isListError && (
              <div className="px-2 py-6 text-center text-xs text-destructive">
                Failed to load versions
              </div>
            )}
            {!isLoading &&
              !isListError &&
              (!history || history.length === 0) && (
                <div className="px-2 py-6 text-center text-xs text-muted-foreground">
                  No saved versions yet
                </div>
              )}

            {history?.map((entry) => (
              <HistoryListItem
                key={entry.id}
                entry={entry}
                isSelected={entry.id === selectedId}
                isAnimating={entry.id === animatingId}
                onSelect={handleSelectEntry}
                onExport={handleExport}
                onDeleteClick={setDeleteDialogEntry}
              />
            ))}
          </SidebarMenu>
        </div>
      </div>

      <PruneWarningDialog
        open={pruneWarning}
        onClose={() => setPruneWarning(false)}
        onConfirm={doCreateSnapshot}
        isCreating={isCreating}
        historyLength={history?.length ?? 0}
        maxEntries={maxEntries ?? 0}
      />

      <RestoreConfirmDialog
        entry={restoreDialogEntry}
        onClose={() => setRestoreDialogEntry(null)}
        onConfirm={handleRestore}
        isRestoring={isRestoring}
      />

      <DeleteConfirmDialog
        entry={deleteDialogEntry}
        onClose={() => setDeleteDialogEntry(null)}
        onConfirm={handleDelete}
        isDeleting={isDeleting}
      />
    </>
  );
}
