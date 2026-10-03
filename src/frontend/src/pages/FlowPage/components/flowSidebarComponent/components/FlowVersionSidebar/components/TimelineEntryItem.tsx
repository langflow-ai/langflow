import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import type { RevisionEntry } from "@/types/flow/revision";
import type { DescribeOptions } from "@/utils/flow-operations/describe";
import { cn } from "@/utils/utils";
import { revisionSelectionId } from "../constants";
import { describeChanges, foldedSummary, summarizeEntry } from "../fold";
import { formatTime } from "../utils";
import AuthorAvatar from "./AuthorAvatar";

interface TimelineEntryItemProps {
  entry: RevisionEntry;
  isSelected: boolean;
  onSelect: (id: string) => void;
  fieldLabel?: DescribeOptions["fieldLabel"];
}

/**
 * One recorded batch of changes: who made it and when, what changed, and any
 * saved versions it holds. Selecting it previews the flow as it was right
 * after the batch.
 */
export default function TimelineEntryItem({
  entry,
  isSelected,
  onSelect,
  fieldLabel,
}: TimelineEntryItemProps) {
  const { t } = useTranslation();
  const authors = entry.actors
    .map((actor) => actor.username ?? t("flowHistory.unknownAuthor"))
    .join(", ");
  const [firstActor] = entry.actors;
  // An entry one action caused (a component update, a restore) reads as that
  // action; its individual changes stay one click away.
  const folded = foldedSummary(entry, t);
  const [showChanges, setShowChanges] = useState(false);
  const changesId = useId();

  return (
    <SidebarMenuItem className="relative before:absolute before:bottom-0 before:left-[23px] before:top-0 before:w-px before:bg-border">
      <SidebarMenuButton
        isActive={isSelected}
        onClick={() => onSelect(revisionSelectionId(entry.end_revision))}
        className={cn(
          "relative h-auto items-start gap-2.5 rounded-none py-2.5 pl-3 pr-3 font-normal data-[active=true]:font-normal",
          isSelected && "!bg-[#6366F1]/10 shadow-[inset_2px_0_0_#6366F1]",
        )}
      >
        <AuthorAvatar
          id={firstActor?.id ?? entry.id}
          name={firstActor?.username ?? null}
          className="mt-0.5"
        />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="truncate font-medium text-foreground">
              {authors}
            </span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {entry.created_at ? formatTime(entry.created_at) : ""}
            </span>
          </div>
          <p className="line-clamp-2 whitespace-normal break-words text-xs leading-snug text-muted-foreground">
            {entry.operations
              ? summarizeEntry(entry, t, { fieldLabel })
              : t("flowHistory.changes", {
                  count: entry.end_revision - entry.start_revision + 1,
                })}
          </p>
          {entry.versions.map((version) => (
            <span
              key={version.id}
              className="flex w-fit max-w-full items-center gap-1 rounded-full border border-border bg-background px-2 py-0.5 text-[11px] text-foreground"
            >
              <ForwardedIconComponent
                name="Bookmark"
                className="h-3 w-3 shrink-0 text-[#6366F1]"
              />
              <span className="font-medium">{version.version_tag}</span>
              {version.description && (
                <span className="truncate text-muted-foreground">
                  {version.description}
                </span>
              )}
            </span>
          ))}
        </div>
      </SidebarMenuButton>
      {folded && entry.operations && (
        <div className="relative pb-2 pl-[46px] pr-3 text-xs">
          <button
            type="button"
            className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
            aria-expanded={showChanges}
            aria-controls={changesId}
            onClick={() => setShowChanges((shown) => !shown)}
          >
            <ForwardedIconComponent
              name={showChanges ? "ChevronDown" : "ChevronRight"}
              className="h-3 w-3"
            />
            {showChanges
              ? t("flowHistory.fold.hideChanges")
              : t("flowHistory.fold.showChanges")}
          </button>
          {showChanges && (
            <ul
              id={changesId}
              className="mt-1 flex flex-col gap-0.5 break-words text-muted-foreground"
            >
              {(() => {
                const sentences = describeChanges(entry.operations, t, {
                  fieldLabel,
                });
                return sentences.length > 0
                  ? sentences.map((sentence, index) => (
                      // biome-ignore lint/suspicious/noArrayIndexKey: sentences can repeat; the list never reorders
                      <li key={index}>{sentence}</li>
                    ))
                  : [<li key="none">{t("flowHistory.op.noChanges")}</li>];
              })()}
            </ul>
          )}
        </div>
      )}
    </SidebarMenuItem>
  );
}
