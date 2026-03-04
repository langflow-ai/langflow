import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import DeleteConfirmDialog from "./components/DeleteConfirmDialog";
import VersionListItem from "./components/VersionListItem";
import { CURRENT_DRAFT_ID } from "./constants";
import type { FlowVersionSidebarContentProps } from "./types";
import { useFlowVersionSidebar } from "./use-flow-version-sidebar";

export default function FlowVersionSidebarContent({
  flowId,
}: FlowVersionSidebarContentProps) {
  const {
    selectedId,
    deleteDialogEntry,
    setDeleteDialogEntry,
    animatingId,
    versions,
    maxEntries,
    isLoading,
    isListError,
    isEntryError,
    processedPreview,
    isDeleting,
    isViewingDraft,
    handleSelectEntry,
    handleExport,
    handleDelete,
  } = useFlowVersionSidebar(flowId);

  return (
    <>
      <div className="flex h-full flex-col">
        <SidebarGroupLabel className="flex items-center justify-between px-3 pt-3">
          <span>Version History</span>
          {versions && versions.length > 0 && (
            <span className="font-normal text-foreground/50">
              {versions.length}
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

        <div className="min-h-0 flex-1 overflow-y-auto">
          <SidebarMenu className="gap-0">
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={isViewingDraft}
                onClick={() => handleSelectEntry(CURRENT_DRAFT_ID)}
                className={`h-auto flex flex-col items-start p-3 border-t border-b border-border rounded-none ${isViewingDraft ? "border-l-2 border-l-[#6366F1] !bg-[#6366F1]/10" : ""}`}
              >
                <div className="flex w-full items-center justify-between">
                  <div className="flex flex-col items-start">
                    <span className="font-medium text-sm pb-1">Current</span>
                    <span className="text-xs text-muted-foreground">
                      Working version
                    </span>
                  </div>
                  {isViewingDraft && (
                    <span className="h-2 w-2 shrink-0 rounded-full bg-[#6366F1]" />
                  )}
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
              (!versions || versions.length === 0) && (
                <div className="px-2 py-6 text-center text-xs text-muted-foreground">
                  No saved versions yet
                </div>
              )}

            {versions?.map((entry) => (
              <VersionListItem
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

      <DeleteConfirmDialog
        entry={deleteDialogEntry}
        onClose={() => setDeleteDialogEntry(null)}
        onConfirm={handleDelete}
        isDeleting={isDeleting}
      />
    </>
  );
}
