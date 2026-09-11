import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { ChangeGroup, FlowChange } from "@/utils/flow-diff";
import { cn } from "@/utils/utils";

const BADGE_VARIANT = {
  added: "conflictAdded",
  removed: "conflictRemoved",
  modified: "conflictModified",
} as const;

/** Raw before/after, for values a sentence cannot honestly summarise. */
function RawDiff({ before, after }: { before: string; after: string }) {
  const { t } = useTranslation();
  return (
    <div className="mt-2 overflow-x-auto rounded-md border border-muted font-mono text-[12px] leading-[19.5px]">
      <div className="border-b border-muted bg-error-background/40 px-3 py-2">
        <span className="mr-2 select-none text-error-foreground">-</span>
        <span className="whitespace-pre-wrap break-words text-error-foreground">
          {before || t("multiEdit.dialog.before")}
        </span>
      </div>
      <div className="bg-accent-emerald/30 px-3 py-2">
        <span className="mr-2 select-none text-accent-emerald-foreground">
          +
        </span>
        <span className="whitespace-pre-wrap break-words text-accent-emerald-foreground">
          {after || t("multiEdit.dialog.after")}
        </span>
      </div>
    </div>
  );
}

/** One change inside a component: the sentence, and its diff on demand. */
function ChangeLine({
  change,
  expandable,
}: {
  change: FlowChange;
  expandable: boolean;
}) {
  const { t } = useTranslation();
  const [showDiff, setShowDiff] = useState(false);

  return (
    <li className="text-[12px] font-medium leading-[19.5px] text-muted-foreground">
      {t(change.sentence.key, change.sentence.params)}
      {expandable && change.detail && (
        <>
          {/* Its own line rather than trailing the sentence: inline, it landed
              at a different place under every sentence length. */}
          <button
            type="button"
            onClick={() => setShowDiff((open) => !open)}
            aria-expanded={showDiff}
            className="flex items-center gap-1 text-[12px] font-medium leading-[19.5px] text-muted-foreground underline-offset-2 hover:underline"
          >
            <ForwardedIconComponent
              name={showDiff ? "ChevronDown" : "ChevronRight"}
              className="h-3 w-3"
              aria-hidden="true"
            />
            {showDiff
              ? t("multiEdit.dialog.hideChanges")
              : t("multiEdit.dialog.showChanges")}
          </button>
          {showDiff && (
            <RawDiff
              before={change.detail.before}
              after={change.detail.after}
            />
          )}
        </>
      )}
    </li>
  );
}

type ChangeRowProps = {
  group: ChangeGroup;
  /** Shown when this component was replaced by the other person's version. */
  replacedBy?: string;
  checked: boolean;
  disabled?: boolean;
  /** Whether the raw before/after may be opened. Only a contested component
   * asks the reader to compare two versions; everywhere else the sentence is
   * the whole story and the control is noise. */
  expandable?: boolean;
  /** Whose list this row is in. The same component can appear on both sides. */
  side: "mine" | "theirs";
  onToggle?: (targetKey: string) => void;
};

/**
 * One component, one checkbox, however many things changed inside it.
 *
 * A component is adopted whole or not at all, so a row per change handed the
 * reader several checkboxes that all moved together — a choice the merge was
 * never able to offer.
 */
export function ChangeRow({
  group,
  checked,
  disabled,
  expandable = false,
  replacedBy,
  side,
  onToggle,
}: ChangeRowProps) {
  const { t } = useTranslation();
  const checkboxId = useId();

  return (
    <div
      className={cn(
        "rounded-[10px] border border-muted bg-muted/40 px-3 py-2.5",
        // Dimmed only while it is not a choice: a row that can be ticked has to
        // look like one.
        disabled && "opacity-60",
      )}
      data-testid={`conflict-change-${side}-${group.targetKey}`}
    >
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkboxId}
          checked={checked}
          disabled={disabled}
          onCheckedChange={() => onToggle?.(group.targetKey)}
          className="mt-0.5"
        />
        <div className="min-w-0 flex-1">
          <label
            htmlFor={checkboxId}
            className="flex flex-wrap items-center gap-2 text-[13px] font-medium leading-[19.5px] text-secondary-foreground"
          >
            {side === "theirs" && (
              <Badge variant={BADGE_VARIANT[group.badge]} size="change">
                {t(`multiEdit.badge.${group.badge}`)}
              </Badge>
            )}
            <span
              className={cn(
                "truncate",
                replacedBy && "line-through opacity-70",
              )}
            >
              {group.label}
            </span>
            {replacedBy && (
              <Badge variant="conflictContested" size="change">
                {replacedBy}
              </Badge>
            )}
          </label>
          <ul className="pt-0.5">
            {group.changes.map((change) => (
              <ChangeLine
                key={change.id}
                change={change}
                expandable={expandable}
              />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default ChangeRow;
