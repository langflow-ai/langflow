import { useId } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { ChangeGroup } from "@/utils/flow-diff";
import { cn } from "@/utils/utils";

type ConflictResolveRowProps = {
  /** The same component as both people left it. */
  mine: ChangeGroup;
  theirs: ChangeGroup;
  authorName: string;
  takingTheirs: boolean;
  onChoose: (targetKey: string) => void;
};

/** The one line of each side, so the choice reads as a comparison. */
function summarise(group: ChangeGroup, t: (k: string, p?: object) => string) {
  return group.changes
    .map((change) => t(change.sentence.key, change.sentence.params))
    .join(" ");
}

/** The fields both people touched, named after the component. */
function fieldsOf(group: ChangeGroup): string {
  const fields = group.changes
    .map((change) => change.sentence.params.field)
    .filter(Boolean);
  return [...new Set(fields)].join(", ");
}

/**
 * A component both people edited, and the choice between their two versions.
 *
 * Raised above the rest of their changes and given radios rather than a
 * checkbox: this is the only place in the dialog where taking something costs
 * something, and a checkbox cannot say what is being given up.
 */
export function ConflictResolveRow({
  mine,
  theirs,
  authorName,
  takingTheirs,
  onChoose,
}: ConflictResolveRowProps) {
  const { t } = useTranslation();
  const name = useId();
  const field = fieldsOf(theirs) || fieldsOf(mine);

  return (
    <div
      className="overflow-hidden rounded-[10px] border border-conflict-outline bg-muted/40"
      data-testid={`conflict-resolve-${theirs.targetKey}`}
    >
      <div className="flex items-center gap-2 border-b border-muted px-3 py-2.5">
        <Badge variant="conflictContested" size="change">
          {t("multiEdit.badge.conflict")}
        </Badge>
        <span className="text-[13px] font-medium leading-[19.5px] text-secondary-foreground">
          {theirs.label}
        </span>
        {field && (
          <span className="truncate text-[13px] leading-[19.5px] text-muted-foreground">
            {t("multiEdit.dialog.conflictField", { field })}
          </span>
        )}
        <span className="ml-auto shrink-0 text-xs leading-[18px] text-muted-foreground">
          {t("multiEdit.dialog.chooseVersion")}
        </span>
      </div>
      <RadioGroup
        value={takingTheirs ? "theirs" : "mine"}
        onValueChange={(value) => {
          if ((value === "theirs") !== takingTheirs) onChoose(theirs.targetKey);
        }}
        className="gap-0"
      >
        {(
          [
            ["mine", t("multiEdit.dialog.keepMine"), mine],
            [
              "theirs",
              t("multiEdit.dialog.keepTheirs", { name: authorName }),
              theirs,
            ],
          ] as const
        ).map(([side, label, group], index) => (
          <label
            key={side}
            htmlFor={`${name}-${side}`}
            className={cn(
              "flex cursor-pointer items-start gap-3 px-3 py-2.5",
              index === 0 && "border-b border-muted",
              // The standing answer is lifted off the card, the way the design
              // separates the choice already made from the one still offered.
              (side === "theirs") === takingTheirs && "bg-muted/60",
            )}
          >
            <RadioGroupItem
              id={`${name}-${side}`}
              value={side}
              className="mt-0.5"
            />
            <span className="flex min-w-0 flex-col">
              <span className="text-[13px] font-medium leading-[19.5px] text-secondary-foreground">
                {label}
              </span>
              <span className="text-[12px] font-medium leading-[19.5px] text-muted-foreground">
                {summarise(group, t)}
              </span>
            </span>
          </label>
        ))}
      </RadioGroup>
    </div>
  );
}

export default ConflictResolveRow;
