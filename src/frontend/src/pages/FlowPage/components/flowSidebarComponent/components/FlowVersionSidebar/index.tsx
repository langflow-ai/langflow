import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import type { RevisionEntry } from "@/types/flow/revision";
import DeleteConfirmDialog from "./components/DeleteConfirmDialog";
import TimelineEntryItem from "./components/TimelineEntryItem";
import VersionListItem from "./components/VersionListItem";
import { CURRENT_DRAFT_ID } from "./constants";
import type { FlowVersionSidebarContentProps } from "./types";
import { useFlowVersionSidebar } from "./use-flow-version-sidebar";
import { dayLabel } from "./utils";

function groupByDay(
  entries: RevisionEntry[],
  label: (dateStr: string | null) => string,
): { day: string; entries: RevisionEntry[] }[] {
  const groups: { day: string; entries: RevisionEntry[] }[] = [];
  for (const entry of entries) {
    const day = label(entry.created_at);
    const last = groups[groups.length - 1];
    if (last?.day === day) last.entries.push(entry);
    else groups.push({ day, entries: [entry] });
  }
  return groups;
}

export default function FlowVersionSidebarContent({
  flowId,
}: FlowVersionSidebarContentProps) {
  const { t } = useTranslation();
  const {
    selectedId,
    deleteDialogEntry,
    setDeleteDialogEntry,
    animatingId,
    versions,
    maxEntries,
    timelineEntries,
    selectedTimelineEntryId,
    fieldLabel,
    olderVersions,
    hasOlderEntries,
    isLoadingOlderEntries,
    loadOlderEntries,
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
          <span>{t("sidebar.nav.versionHistory")}</span>
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
              {t("flowVersion.failedToLoadData")}
            </span>
          </div>
        )}

        {processedPreview?.error && (
          <div className="flex items-center gap-2 bg-destructive/10 px-2 py-2">
            <span className="text-xs text-destructive">
              {t("flowVersion.dataCannotBeRendered")}
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
                    <span className="font-medium text-sm pb-1">
                      {t("flowVersion.currentLabel")}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {t("flowVersion.workingVersion")}
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
                {t("flowVersion.failedToLoadVersions")}
              </div>
            )}
            {!isLoading &&
              !isListError &&
              timelineEntries.length === 0 &&
              (!versions || versions.length === 0) && (
                <div className="px-2 py-6 text-center text-xs text-muted-foreground">
                  {t("flowVersion.noSavedVersions")}
                </div>
              )}

            {groupByDay(timelineEntries, (dateStr) => dayLabel(dateStr, t)).map(
              (group) => (
                <div key={group.day} role="group" aria-label={group.day}>
                  <div className="sticky top-0 z-10 bg-background/95 px-3 pb-1.5 pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground backdrop-blur">
                    {group.day}
                  </div>
                  {group.entries.map((entry) => (
                    <TimelineEntryItem
                      key={entry.id}
                      entry={entry}
                      isSelected={entry.id === selectedTimelineEntryId}
                      onSelect={handleSelectEntry}
                      fieldLabel={fieldLabel}
                    />
                  ))}
                </div>
              ),
            )}

            {hasOlderEntries && (
              <button
                type="button"
                className="w-full px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => loadOlderEntries()}
                disabled={isLoadingOlderEntries}
              >
                {t("flowHistory.loadOlder")}
              </button>
            )}

            {olderVersions.length > 0 && timelineEntries.length > 0 && (
              <div className="px-3 pb-1.5 pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("flowHistory.olderHistory")}
              </div>
            )}

            {olderVersions.map((entry) => (
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
