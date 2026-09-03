import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { FlowChange } from "@/utils/flow-diff";
import { cn } from "@/utils/utils";

const BADGE_VARIANT = {
  added: "successStatic",
  removed: "errorStatic",
  modified: "purpleStatic",
} as const;

/** Raw before/after, for values a sentence cannot honestly summarise. */
function RawDiff({ before, after }: { before: string; after: string }) {
  const { t } = useTranslation();
  return (
    <div className="mt-2 overflow-x-auto rounded-md border border-border font-mono text-xs">
      <div className="border-b border-border bg-error-background/40 px-3 py-2">
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

type ChangeRowProps = {
  change: FlowChange;
  checked: boolean;
  disabled?: boolean;
  /** Shown under the description; explains a trade the reader is making. */
  note?: string;
  /** This change lost a component-level choice and will not reach the copy. */
  muted?: boolean;
  /** Whose list this row is in. The same change can appear on both sides. */
  side: "mine" | "theirs";
  onToggle?: (id: string) => void;
};

export function ChangeRow({
  change,
  checked,
  disabled,
  note,
  muted,
  side,
  onToggle,
}: ChangeRowProps) {
  const { t } = useTranslation();
  const [showDiff, setShowDiff] = useState(false);
  const checkboxId = useId();
  const hasDetail = Boolean(change.detail);

  return (
    <div
      className={cn(
        "rounded-lg border px-4 py-3",
        checked && !disabled ? "border-primary" : "border-border",
        // Not opacity: it composites into contrast and drops this text to 2.34:1.
        (disabled || muted) && "bg-muted/40",
      )}
      data-testid={`conflict-change-${side}-${change.id}`}
    >
      <div className="flex items-start gap-3">
        <Checkbox
          id={checkboxId}
          checked={checked}
          disabled={disabled}
          onCheckedChange={() => onToggle?.(change.id)}
          aria-describedby={note ? `${checkboxId}-note` : undefined}
          className="mt-0.5"
        />
        <div className="min-w-0 flex-1">
          <label
            htmlFor={checkboxId}
            className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground"
          >
            <Badge variant={BADGE_VARIANT[change.badge]} size="xq">
              {t(`multiEdit.badge.${change.badge}`)}
            </Badge>
            <span className={cn("truncate", muted && "line-through")}>
              {change.label}
            </span>
          </label>
          <p className="mt-1 text-mmd text-muted-foreground">
            {t(change.sentence.key, change.sentence.params)}
          </p>
          {note && (
            <p
              id={`${checkboxId}-note`}
              className="mt-1 text-mmd text-accent-amber-foreground"
            >
              {note}
            </p>
          )}
          {hasDetail && (
            <>
              <button
                type="button"
                onClick={() => setShowDiff((open) => !open)}
                aria-expanded={showDiff}
                className="mt-2 flex items-center gap-1 text-mmd text-muted-foreground underline-offset-2 hover:underline"
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
              {showDiff && change.detail && (
                <RawDiff
                  before={change.detail.before}
                  after={change.detail.after}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChangeRow;
