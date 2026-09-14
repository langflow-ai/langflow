import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { ChangeGroup, FlowChange } from "@/utils/flow-diff";
import { cn } from "@/utils/utils";

const BADGE_VARIANT = {
  added: "conflictAdded",
  removed: "conflictRemoved",
  modified: "conflictModified",
} as const;

// A component's `code` field is its whole Python source, and it went into the
// dialog twice over, inside a box capped at 55vh. The decision the dialog exists
// for was then somewhere below the fold of a file listing.
const DIFF_LINE_LIMIT = 12;
const DIFF_CHAR_LIMIT = 800;

/** The head of a value, and whether anything was left off. */
function clampValue(value: string): { text: string; truncated: boolean } {
  const withinChars = value.slice(0, DIFF_CHAR_LIMIT);
  const lines = withinChars.split(/\r\n|\r|\n/);
  const text = lines.slice(0, DIFF_LINE_LIMIT).join("\n");
  return { text, truncated: text.length < value.length };
}

/** One side of the raw comparison, cut down to what can be read at a glance. */
function DiffSide({
  value,
  sign,
  placeholder,
  tone,
}: {
  value: string;
  sign: string;
  placeholder: string;
  tone: "before" | "after";
}) {
  const { t } = useTranslation();
  const { text, truncated } = clampValue(value);
  const colour =
    tone === "before"
      ? "text-error-foreground"
      : "text-accent-emerald-foreground";

  return (
    <div
      className={cn(
        "px-3 py-2",
        tone === "before"
          ? "border-b border-muted bg-error-background/40"
          : "bg-accent-emerald/30",
      )}
    >
      <span className={cn("mr-2 select-none", colour)}>{sign}</span>
      <span className={cn("whitespace-pre-wrap break-words", colour)}>
        {text || placeholder}
      </span>
      {truncated && (
        <p className="pt-1 text-[11px] leading-[16.5px] text-muted-foreground">
          {t("multiEdit.dialog.diffTruncated")}
        </p>
      )}
    </div>
  );
}

/** Raw before/after, for values a sentence cannot honestly summarise. */
export function RawDiff({ before, after }: { before: string; after: string }) {
  const { t } = useTranslation();
  return (
    <div className="mt-2 overflow-x-auto rounded-md border border-muted font-mono text-[12px] leading-[19.5px]">
      <DiffSide
        value={before}
        sign="-"
        placeholder={t("multiEdit.dialog.before")}
        tone="before"
      />
      <DiffSide
        value={after}
        sign="+"
        placeholder={t("multiEdit.dialog.after")}
        tone="after"
      />
    </div>
  );
}

/** One change inside a component, as a sentence. */
function ChangeLine({ change }: { change: FlowChange }) {
  const { t } = useTranslation();
  return (
    <li className="text-[12px] font-medium leading-[19.5px] text-muted-foreground">
      {t(change.sentence.key, change.sentence.params)}
    </li>
  );
}

type ChangeRowProps = {
  group: ChangeGroup;
  checked: boolean;
  disabled?: boolean;
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
            <span className="truncate">{group.label}</span>
            {/* Beside the name, not out on the right edge: the design pairs the
                badge with the component it describes. Both sides carry it —
                what changed is as worth stating for my own rows as for theirs. */}
            <Badge variant={BADGE_VARIANT[group.badge]} size="change">
              {t(`multiEdit.badge.${group.badge}`)}
            </Badge>
          </label>
          <ul className="pt-0.5">
            {group.changes.map((change) => (
              <ChangeLine key={change.id} change={change} />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default ChangeRow;
