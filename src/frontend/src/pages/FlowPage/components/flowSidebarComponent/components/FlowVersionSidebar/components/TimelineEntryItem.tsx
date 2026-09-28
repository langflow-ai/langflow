import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import type { RevisionEntry } from "@/types/flow/revision";
import { summarizeOperations } from "@/utils/flow-operations/describe";
import { cn } from "@/utils/utils";
import { revisionSelectionId } from "../constants";
import { formatTime } from "../utils";

interface TimelineEntryItemProps {
  entry: RevisionEntry;
  isSelected: boolean;
  onSelect: (id: string) => void;
}

/**
 * One recorded batch of changes: when, by whom, and what changed, with any
 * saved versions it holds shown as labels. Selecting it previews the flow as
 * it was right after the batch.
 */
export default function TimelineEntryItem({
  entry,
  isSelected,
  onSelect,
}: TimelineEntryItemProps) {
  const { t } = useTranslation();
  const authors = entry.actors
    .map((actor) => actor.username ?? t("flowHistory.unknownAuthor"))
    .join(", ");

  return (
    <SidebarMenuItem className="relative flex items-center border-b border-border">
      <SidebarMenuButton
        isActive={isSelected}
        onClick={() => onSelect(revisionSelectionId(entry.end_revision))}
        className={cn(
          "flex h-auto flex-1 flex-col items-start gap-1 rounded-none py-2 pl-3",
          isSelected && "border-l-2 border-l-[#6366F1] !bg-[#6366F1]/10",
        )}
      >
        <div className="flex w-full items-center gap-2 text-xs">
          <span className="text-muted-foreground">
            {entry.created_at ? formatTime(entry.created_at) : ""}
          </span>
          <span className="truncate font-medium">{authors}</span>
        </div>
        <span className="line-clamp-2 text-left text-xs text-foreground/80">
          {entry.operations
            ? summarizeOperations(entry.operations, t)
            : t("flowHistory.changes", {
                count: entry.end_revision - entry.start_revision + 1,
              })}
        </span>
        {entry.versions.map((version) => (
          <span
            key={version.id}
            className="flex items-center gap-1 text-xs text-muted-foreground"
          >
            <ForwardedIconComponent name="Bookmark" className="h-3 w-3" />
            <span className="font-medium">{version.version_tag}</span>
            {version.description && (
              <span className="truncate">{version.description}</span>
            )}
          </span>
        ))}
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}
